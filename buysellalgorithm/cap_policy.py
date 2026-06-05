"""Forecast-aware supercap dispatcher (Smart V1).

Strategy in one paragraph: stored-energy-in-the-cap has a *future value*
equal to the best leakage-discounted price it can be discharged into.
At every tick we compare current actions against that best future value:

  * **arb_discharge** — current sell-price > best-future-discharge-value
    → discharge now, no point holding.
  * **arb_charge** — best-future-discharge-value (×η_RT) > current
    charge-cost → put energy in.
  * **passive** — fall back to the naive reactive rule otherwise.
  * **hold** — neither side beats threshold; leave the cap alone.

Leakage model from §4.3.4 of the Y2 report (Figure 4.5). η_RT drops
from 88.3% with no hold to 64.1% after 300 s of hold at peak charge.
Two components dominate: a fast dielectric-absorption step (~12% loss
in the first minute = 12 ticks), then a slow ohmic leakage of ~3 pp/min
(~0.25%/tick) thereafter. The piecewise ``retain_fraction()`` below
captures that shape — using a flat per-tick rate (the obvious naive
choice) under-counts the early loss by ~4×.
"""

from dataclasses import dataclass
from typing import Optional, Tuple

from . import forecast


# --- Cap physics (mirror firmware) ---
V_CAP_CHARGE_STOP     = 15.7
V_CAP_DISCHARGE_TAPER = 11.0
V_CAP_DISCHARGE_STOP  = 10.5
I_CAP_MAX             = 0.60
ETA_RT                = 0.88        # round-trip, §4.3.3
ETA_CAP_SMPS          = 0.90        # one-way (matches naive.ETA_CAP_SMPS)

# Horizon over which we look for arbitrage. The full day = 60 ticks; we
# go that far so a morning tick can see the evening peak. The leakage
# discount erodes far-future values automatically.
HORIZON_TICKS         = 60

# Threshold for "significantly better" — the expected gain (after η_RT ×
# leakage) has to clear this many ¢/J of expected value before we commit
# to a non-passive action. Tuned to the spread of the day (~20–80 ¢/J).
ARB_TRIGGER_CENTS_PER_J = 8.0

# Floor on import-to-charge: only let the cap "buy from the grid for
# storage" when the spread is strong enough to be worth the risk of
# noise reversing the bet. Twice the trigger.
IMPORT_CHARGE_TRIGGER   = 2 * ARB_TRIGGER_CENTS_PER_J


@dataclass
class CapAction:
    target_W:    float       # signed bus-side power (+charge / -discharge)
    reason:      str         # short tag for diagnostics
    arb_gain:    float = 0.0 # expected gain per J (¢/J)
    horizon_t:   int   = 0   # ticks until the arb counterparty tick


def retain_fraction(ticks: int) -> float:
    """Fraction of a stored joule still recoverable after waiting
    ``ticks`` Azure ticks (5 s each).

    Piecewise fit to Figure 4.5 in the Y2 report (η_RT vs hold duration):
      - First 12 ticks (60 s): fast dielectric absorption, ~12% loss
        linear over the window
      - After 12 ticks: slow ohmic leakage, ~0.25%/tick (~3 %/min)
    """
    if ticks <= 0:
        return 1.0
    if ticks <= 12:
        return max(0.0, 1.0 - 0.0102 * ticks)
    return max(0.0, 0.878 - 0.0025 * (ticks - 12))


def _cap_soc_headroom(v_cap: float) -> Tuple[float, float]:
    """Return (charge_headroom_J, discharge_available_J) using
    E = ½ C V² with C = 0.5 F."""
    C = 0.5
    e_now  = 0.5 * C * v_cap * v_cap
    e_full = 0.5 * C * V_CAP_CHARGE_STOP * V_CAP_CHARGE_STOP
    e_low  = 0.5 * C * V_CAP_DISCHARGE_TAPER * V_CAP_DISCHARGE_TAPER
    return max(0.0, e_full - e_now), max(0.0, e_now - e_low)


def decide(
    current_tick: int,
    current_net_W: float,
    v_cap: float,
    vbus: float,
) -> CapAction:
    """Decide the cap's target bus-side power for this tick.

    ``current_net_W`` is the imbalance after PV and scheduler-aware
    deferrable load. +ve = surplus, -ve = deficit.
    """
    p_now_sell = forecast.expected_sell_price(current_tick)
    p_now_buy  = forecast.expected_buy_price(current_tick)

    charge_headroom_J, discharge_avail_J = _cap_soc_headroom(v_cap)
    can_charge    = charge_headroom_J  > 1.0 and v_cap < V_CAP_CHARGE_STOP - 0.2
    can_discharge = discharge_avail_J > 1.0 and v_cap > V_CAP_DISCHARGE_TAPER + 0.2

    # --- Best future discharge value across the rest of the day ---
    # For each tick t in (now, end], compute leakage-discounted sell-price
    # — that is what a joule stored now would fetch if we discharged at t.
    best_future_t     = current_tick
    best_future_value = 0.0
    for t in range(current_tick + 1,
                   min(forecast.TICKS_PER_DAY, current_tick + HORIZON_TICKS + 1)):
        dt    = t - current_tick
        value = forecast.expected_sell_price(t) * retain_fraction(dt)
        if value > best_future_value:
            best_future_value = value
            best_future_t     = t

    # --- 1. Discharge decision: is *now* better than holding? ---
    # Compare current sell-price-equivalent against the best leakage-
    # discounted future price. If current beats the best future by the
    # threshold, dump the cap now.
    if can_discharge and p_now_sell > best_future_value + ARB_TRIGGER_CENTS_PER_J:
        target_W = -(I_CAP_MAX * vbus * ETA_CAP_SMPS)
        return CapAction(
            target_W   = target_W,
            reason     = "arb_discharge",
            arb_gain   = p_now_sell - best_future_value,
            horizon_t  = 0,
        )

    # --- 2. Charge decision: does best future yield > current charge cost? ---
    # Yield per J of bus-side energy put into the cap now:
    #   yield = sell(best_t) × η_RT × retain(best_t - now)
    # (η_RT folds in the round-trip charge+discharge η; retain folds in
    # leakage.)
    yield_per_J = (forecast.expected_sell_price(best_future_t)
                   * ETA_RT
                   * retain_fraction(best_future_t - current_tick))

    # Charge cost depends on regime:
    #   surplus  → cost = foregone export revenue = buy_price (low)
    #   deficit  → cost = import we'd have to do  = sell_price (high)
    if current_net_W > 0.5:
        charge_cost = p_now_buy
    else:
        charge_cost = p_now_sell

    charge_gain = yield_per_J - charge_cost

    # In surplus, charge if even a small gain. In deficit, demand a
    # bigger spread before importing-to-store (avoid round-tripping
    # cheap mid-day surplus through the grid).
    if can_charge and current_net_W > 0.5 and charge_gain > ARB_TRIGGER_CENTS_PER_J:
        target_W = min(I_CAP_MAX * vbus, max(current_net_W + 2.0, current_net_W))
        return CapAction(
            target_W   = target_W,
            reason     = "arb_charge",
            arb_gain   = charge_gain,
            horizon_t  = best_future_t - current_tick,
        )
    if can_charge and current_net_W <= 0.5 and charge_gain > IMPORT_CHARGE_TRIGGER:
        # Small forward-buy via import. Capped at ~3 W so a bad forecast
        # can't bleed us out.
        target_W = min(I_CAP_MAX * vbus, 3.0)
        return CapAction(
            target_W   = target_W,
            reason     = "arb_import_charge",
            arb_gain   = charge_gain,
            horizon_t  = best_future_t - current_tick,
        )

    # --- 3. Passive — naive reactive rule, within safe envelope ---
    if current_net_W > 1.0 and can_charge:
        target_W = min(I_CAP_MAX * vbus, current_net_W)
        return CapAction(target_W, "passive_charge")
    if current_net_W < -1.0 and can_discharge:
        target_W = -min(I_CAP_MAX * vbus * ETA_CAP_SMPS, -current_net_W)
        return CapAction(target_W, "passive_discharge")

    if current_net_W > 1.0:
        return CapAction(0.0, "ceiling")
    if current_net_W < -1.0:
        return CapAction(0.0, "floor")
    return CapAction(0.0, "idle")


# --- Sanity print ---
if __name__ == "__main__":  # pragma: no cover
    cases = [
        ("tick 0, cap half, mild deficit",          0,  -0.5, 13.0),
        ("tick 15, cap half, deficit",             15,  -2.0, 13.0),
        ("tick 25, cap empty-ish, surplus",        25,  +4.0, 12.0),
        ("tick 30, cap empty-ish, surplus",        30,  +5.0, 12.0),
        ("tick 35, cap half, surplus",             35,  +3.0, 14.0),
        ("tick 45, cap full, deficit",             45,  -2.0, 15.5),
        ("tick 50, cap half, deficit",             50,  -2.0, 13.0),
        ("tick 55, cap empty, deficit",            55,  -0.5, 11.0),
    ]
    for label, t, net, vc in cases:
        a = decide(t, net, vc, 10.0)
        print(f"{label:<42}  target={a.target_W:+6.2f} W  "
              f"reason={a.reason:<18}  gain={a.arb_gain:+6.1f} ¢/J  "
              f"horizon={a.horizon_t} ticks")
