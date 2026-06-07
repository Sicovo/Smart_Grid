"""Smart V1 — forecast-aware temporal arbitrage.

The naive baseline (``naive.py``) makes every decision from the
instantaneous snapshot alone: spread deferrables linearly, balance net
imbalance with the cap, let droop handle the residual. That's robust
but blind — it serves a 100 ¢/J evening tick just as eagerly as a 10
¢/J midday tick.

Smart V1 keeps every safety guard of the naive policy (LED 3 W/ch clamp,
cap taper, 0.6 A clamp, deadband, ETA_CAP_SMPS compensation) and adds
two forecast-aware overrides:

1. **Deferrable scheduling** (``scheduler.py``) — rank future ticks by
   marginal cost-to-serve and greedy-fill the cheapest. Replaces the
   naive linear smear.
2. **Cap dispatch** (``cap_policy.py``) — peak-shave the cap against
   the known evening price spike, charge during midday PV surplus,
   discount the leakage cost (3 pp/min, §4.3.4) over the wait horizon.

Both modules are pure-Python and rely only on the deterministic Azure
day shape (``forecast.py``), so V1 is testable offline.

Drop-in compatible with the naive's ``decide(state) -> Commands``
signature — the registry treats them as interchangeable.
"""

from . import naive, forecast, scheduler, cap_policy
from .naive import (
    Commands, CapCmd, LedCmd, GridCmd, ExportCmd, GridState,
    P_LED_MAX_PER_CH, I_CAP_MAX, ETA_CAP_SMPS, PV_EFFICIENCY,
    V_CAP_CHARGE_STOP, V_CAP_DISCHARGE_TAPER, V_CAP_DISCHARGE_STOP,
    POWER_DEADBAND_W, SECONDS_PER_TICK,
    _safe_vbus, _discharge_i_max,
)


ALGO_ID   = "smart_v1"
ALGO_NAME = "Smart V1 — Forecast-Aware"
ALGO_DESC = (
    "Forecasts the Azure day's PV, demand and price curves; schedules "
    "deferrables into the cheapest/surplus ticks first; peak-shaves the "
    "supercap against the known evening price spike with leakage-aware "
    "(3 pp/min) horizon discounting. Keeps every naive safety guard."
)


def decide(state: GridState) -> Commands:
    cmd  = Commands()
    vbus = _safe_vbus(state.vbus)

    # --- Step 1: derate PV to bus side (same as naive) ---
    pv_bus = max(0.0, state.pv_p) * PV_EFFICIENCY

    # --- Step 2: forecast-aware deferrable rate (replaces naive's linear smear) ---
    # ``state.deferrables_served_J`` is the per-day cumulative joules
    # already dispatched per deferable index — subtracted from each
    # d.energy so we don't over-serve (Azure publishes the original
    # obligation at every tick, never the remaining).
    def_rate_total, def_detail = scheduler.allocate_all(
        state.deferrables, state.tick, state.deferrables_served_J
    )

    # --- Step 3: effective load + net (same shape as naive) ---
    demand          = max(0.0, state.demand_p)
    effective_load  = demand + def_rate_total
    net             = pv_bus - effective_load

    # --- Step 4: LED dissipates the effective load (same as naive) ---
    led_each = effective_load / 3.0
    led_clamped_overflow = 0.0
    if led_each > P_LED_MAX_PER_CH:
        led_clamped_overflow = (led_each - P_LED_MAX_PER_CH) * 3.0
        led_each = P_LED_MAX_PER_CH
    cmd.led.p_red = led_each
    cmd.led.p_yel = led_each
    cmd.led.p_grn = led_each

    # --- Step 5: forecast-aware cap dispatch (replaces naive's reactive rule) ---
    # Pass through actual prices if the harness/poller populated them on
    # state — cap_policy will use them instead of forecast for the current
    # tick's economics (future ticks are still forecast-only).
    action = cap_policy.decide(
        current_tick=state.tick,
        current_net_W=net,
        v_cap=state.v_cap,
        vbus=vbus,
        actual_sell_price=getattr(state, "actual_sell_price", None),
        actual_buy_price =getattr(state, "actual_buy_price",  None),
    )
    target_W = action.target_W   # bus-side, signed

    cap_clamped = ""
    cap_p       = 0.0
    cap_headroom = 0.0

    if target_W > POWER_DEADBAND_W:
        # CHARGE the cap.
        cmd.regime = "surplus" if action.reason.startswith("passive") else "arb_charge"
        if state.v_cap >= V_CAP_CHARGE_STOP:
            cap_clamped = "ceiling"
        else:
            i_request = target_W / vbus
            i_charge  = min(I_CAP_MAX, i_request)
            if i_request > I_CAP_MAX:
                cap_clamped = "i_max"
            cmd.cap.i_cmd = i_charge
            cap_p         = i_charge * vbus
            cap_headroom  = I_CAP_MAX * vbus - cap_p

        residual = max(0.0, net - cap_p)
        cmd.surplus_W = residual
        cmd.deficit_W = 0.0

    elif target_W < -POWER_DEADBAND_W:
        # DISCHARGE the cap.
        cmd.regime = "deficit" if action.reason.startswith("passive") else "arb_discharge"
        want_bus_W   = -target_W                          # > 0
        i_max_now    = _discharge_i_max(state.v_cap)
        if i_max_now <= 0:
            cap_clamped = "floor"
        else:
            # Compensate for cap-side SMPS loss on discharge (same as naive).
            i_request   = want_bus_W / (vbus * ETA_CAP_SMPS)
            i_discharge = min(i_max_now, i_request)
            if state.v_cap < V_CAP_DISCHARGE_TAPER:
                cap_clamped = "taper"
            elif i_request > i_max_now:
                cap_clamped = "i_max"
            cmd.cap.i_cmd = -i_discharge
            cap_p         = -i_discharge * vbus * ETA_CAP_SMPS
            cap_headroom  = (i_max_now - i_discharge) * vbus * ETA_CAP_SMPS

        # Residual deficit = whatever was needed beyond what cap could supply.
        bus_deficit = max(0.0, -net)
        bus_supplied = -cap_p
        residual = max(0.0, bus_deficit - bus_supplied)
        cmd.deficit_W = residual
        cmd.surplus_W = 0.0

    else:
        # Cap policy chose idle. The naive's deadband rule still applies
        # to the residual net imbalance — droop handles it passively.
        cmd.regime = "idle"
        if net > POWER_DEADBAND_W:
            cmd.surplus_W = net
        elif net < -POWER_DEADBAND_W:
            cmd.deficit_W = -net

    # --- Fill diagnostics (stable shape + algo-specific extras) ---
    cmd.pv_panel_W         = state.pv_p
    cmd.pv_bus_W           = pv_bus
    cmd.pv_eta_used        = PV_EFFICIENCY
    cmd.demand_W           = demand
    cmd.def_rate_total_W   = def_rate_total
    cmd.effective_load_W   = effective_load
    cmd.net_W              = net
    cmd.active_deferrables = def_detail
    cmd.cap_p_W            = cap_p
    cmd.cap_clamped        = cap_clamped
    cmd.cap_headroom_W     = cap_headroom
    cmd.led_clamped_W      = led_clamped_overflow

    # Smart-V1-specific extras (rendered in the dashboard debug panel).
    cmd.algo_id = ALGO_ID
    cmd.algo_extras = {
        "cap_action_reason":  action.reason,
        "cap_action_target_W": round(target_W, 4),
        "cap_arb_gain":        round(action.arb_gain, 3),
        "cap_arb_horizon_t":   action.horizon_t,
        "forecast_now": {
            "sell_price":  round(forecast.expected_sell_price(state.tick), 3),
            "buy_price":   round(forecast.expected_buy_price(state.tick), 3),
            "pv_bus_W":    round(forecast.expected_pv_bus_W(state.tick), 3),
            "demand_W":    round(forecast.expected_demand_W(state.tick), 3),
        },
    }

    return cmd
