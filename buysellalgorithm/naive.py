"""Naive grid-balancing policy — v2.

Pure decision function: given a snapshot of the grid + bus state, return
the commands to issue to each firmware module. No DB, no HTTP, no globals.

================================================================
Goal
================================================================
Minimise grid import AND export. The supercap is the primary balancing
actuator; grid + export form the passive symmetric-droop safety net.

================================================================
Mental model
================================================================
1. **PV is derated to a bus-side value** before any balance math.
       pv_bus = pv_panel × η_pv   (η_pv = 0.80, conservative)
   This accounts for the boost converter loss between the panel and the
   bus. Without this, we'd over-command LED dissipation by ~20 % and the
   bus would sag, dragging grid in to make up the difference.

2. **Deferrables are first-class load** as soon as their window opens.
   Azure's deferrable .energy is in JOULES. Each Azure tick is 5 real
   seconds. So each active deferrable has a smooth required rate:
       seconds_remaining = (tick_end − tick + 1) × 5 s
       rate_W            = remaining_energy_J / seconds_remaining
   That spreads the energy linearly across the remaining REAL TIME,
   ADAPTIVE to any catch-up needed (if we under-served last tick, rate
   goes up). At the deadline tick (1 tick = 5 s left), rate equals
   remaining_energy / 5 W — last-chance dump.

3. **Effective load = base demand + Σ deferrable rates**.
   This is what the LED is commanded to dissipate.

4. **Balance:**
       net = pv_bus − effective_load
       net > +deadband → SURPLUS → cap charges (refused above 15.7 V),
                                   overflow exported by droop
       net < −deadband → DEFICIT → cap discharges (refused below 11.0 V),
                                   shortfall imported by droop
       |net| ≤ deadband → IDLE → cap idle, droop holds the bus

5. **Grid and export are ALWAYS enabled** at their droop targets
   (9.9 V / 10.1 V). They only flow current when cap saturates and the
   bus leaves the 9.9–10.1 V deadband.

================================================================
Why this minimises both import and export
================================================================
- Deferrables are smoothed across their window, not greedy. So a single
  big-energy deferrable (e.g. 50 J in 60 ticks) takes ~0.8 W instead of
  consuming the entire surplus on tick 0. The cap actually gets to charge.
- PV is derated, so we never over-command LED. Bus stays balanced.
- Cap is preferred over grid in deficit (discharges first).
- Cap is preferred over export in surplus (charges first).
- The deadband (1 W) prevents cap chatter on noise.
- Even if the auto-loop crashes, the droop holds the bus indefinitely.

================================================================
Firmware-matched constants (firmware/cap_smps/main.py)
================================================================
  V_CAP_CHARGE_STOP    = 15.7 V   (firmware hard charge cutoff)
  V_CAP_DISCHARGE_STOP = 11.0 V   (firmware starts tapering below this)
  I_CAP_MAX            = 0.60 A   (firmware clamp)
"""

import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional


# ---------------- Operating limits ----------------

# Cap operating window — full firmware-supported range.
#   V_CAP_CHARGE_STOP   = 15.7 V  (firmware V_CAP_CHARGE_CUTOFF — hard stop)
#   V_CAP_DISCHARGE_STOP= 10.5 V  (firmware V_CAP_MIN — hardware floor;
#                                  below this Va<Vb so the SMPS can't transfer)
#   V_CAP_DISCHARGE_TAPER=11.0 V  (firmware V_CAP_TAPER_LO — start of the
#                                  linear current-taper region; full discharge
#                                  current above, scales to 0 at V_CAP_MIN)
#   I_CAP_MAX           = 0.60 A  (firmware clamp on |i_cmd|)
#
# The algorithm now models the firmware taper internally (see
# _discharge_i_max), so the entire 10.5 → 15.7 V band is usable. That
# unlocks ~2.7 J of extra reserve in the 10.5–11.0 V taper region.
V_CAP_CHARGE_STOP     = 15.7
V_CAP_DISCHARGE_STOP  = 10.5
V_CAP_DISCHARGE_TAPER = 11.0
I_CAP_MAX             = 0.60

VB_TARGET_GRID   = 9.9
VB_TARGET_EXPORT = 10.1

GRID_I_REF_MAX_HW   = 2.0     # match grid_smps   I_REF_HI
EXPORT_I_REF_MAX_HW = 2.0     # match export_smps I_REF_HI

VBUS_FALLBACK    = 9.9        # if telemetry missing / invalid
POWER_DEADBAND_W = 1.0        # idle band on the net imbalance

# Conservative PV boost-converter efficiency. Bus-side PV power = panel × this.
# Bench characterisation shows actual η > 95% across all four irradiances
# (Section 3.3). 0.90 leaves ~5 pp of headroom so the algorithm never over-
# models PV bus injection — keeps the bias toward bus surplus (export droop)
# rather than bus deficit (grid import).
PV_EFFICIENCY = 0.90

# Cap-module SMPS one-way efficiency. Used to compensate i_cmd on DISCHARGE
# only — when we want X W on the bus from a cap discharge, we have to ask
# the firmware for X / η so that after the converter loss the bus actually
# sees X. Charging side gets no compensation: whatever the bus gives up
# physically reaches the cap minus η loss, and that's just life.
# Measured round-trip is ~87 %; conservatively call one-way 0.90.
ETA_CAP_SMPS = 0.90

# LED firmware datasheet clamp — won't accept >3 W per channel.
P_LED_MAX_PER_CH = 3.0

# ---------------- Tick / time conventions ----------------
# Azure smart-grid simulation:
#   - one tick = 5 real seconds
#   - /demand .demand_W is instantaneous power in WATTS
#   - /deferables .energy is total energy in JOULES that must be delivered
#     by the deadline tick
#   - /price .buy_price / .sell_price are quoted in currency PER JOULE
#
# Implication: to spread a deferrable's joules linearly across its window,
# divide by (ticks_remaining × SECONDS_PER_TICK) to get watts.
SECONDS_PER_TICK = 5.0


# ---------------- Types ----------------

@dataclass
class Deferrable:
    index:      int
    tick_start: int
    tick_end:   int
    energy:     float   # remaining energy at this tick (W-tick units)


@dataclass
class GridState:
    tick:        int
    pv_p:        float                          # PV PANEL power (W, pre-loss)
    demand_p:    float                          # base demand   (W)
    vbus:        float                          # measured bus voltage (V)
    v_cap:       float                          # supercap terminal voltage (V)
    energy_cap:  float                          # cap energy (J)
    deferrables: List[Deferrable] = field(default_factory=list)

    # Real current-tick prices from the Azure feed. Used by smart_v1's
    # cap_policy to replace the forecast for current-tick economics —
    # forecast σ is ~19 ¢/J on real Azure data, so trusting forecast on
    # the present side blocks ~50 % of valid arb opportunities. Both
    # None means "fall back to forecast" — that's how the algorithm
    # behaved before this plumbing was added.
    actual_sell_price: Optional[float] = None   # ¢/J at this tick
    actual_buy_price:  Optional[float] = None   # ¢/J at this tick


@dataclass
class CapCmd:
    enable: int   = 1
    i_cmd:  float = 0.0


@dataclass
class LedCmd:
    enable: int   = 1
    p_red:  float = 0.0
    p_yel:  float = 0.0
    p_grn:  float = 0.0


@dataclass
class GridCmd:
    # Always enabled — passive droop. Sources current only when bus sags
    # below 9.9 V (i.e. cap has saturated on the discharge side).
    enable:    int   = 1
    vb_target: float = VB_TARGET_GRID
    i_ref_max: float = GRID_I_REF_MAX_HW


@dataclass
class ExportCmd:
    # Always enabled — passive droop. Sinks current only when bus rises
    # above 10.1 V (i.e. cap has saturated on the charge side).
    enable:    int   = 1
    vb_target: float = VB_TARGET_EXPORT
    i_ref_max: float = EXPORT_I_REF_MAX_HW


@dataclass
class Commands:
    cap:    CapCmd    = field(default_factory=CapCmd)
    led:    LedCmd    = field(default_factory=LedCmd)
    grid:   GridCmd   = field(default_factory=GridCmd)
    export: ExportCmd = field(default_factory=ExportCmd)

    # --- Diagnostics (for the dashboard "what is the algo doing?" panel) ---
    regime: str = "idle"          # "surplus" | "deficit" | "idle" | "arb_charge" | "arb_discharge"

    # Which algorithm produced this command set. Set by registry-aware
    # algorithms (smart_v1+); the naive baseline defaults to "naive" via
    # commands_to_diagnostics if not explicitly set.
    algo_id: str = "naive"

    # Algorithm-specific diagnostics (free-form dict). Stable per-algo
    # shape; the frontend renders whatever keys are present in a generic
    # "extras" panel.
    algo_extras: Dict = field(default_factory=dict)

    # Bus-side energy accounting (post PV derate).
    pv_panel_W:        float = 0.0     # raw panel reading
    pv_bus_W:          float = 0.0     # = pv_panel × PV_EFFICIENCY
    pv_eta_used:       float = PV_EFFICIENCY
    demand_W:          float = 0.0
    def_rate_total_W:  float = 0.0     # Σ active deferrable rates
    effective_load_W:  float = 0.0     # demand + Σ def rates
    net_W:             float = 0.0     # pv_bus - effective_load (+surplus / -deficit)

    # Per-deferrable detail for the dashboard table.
    active_deferrables: List[Dict] = field(default_factory=list)

    # Cap accounting.
    cap_p_W:        float = 0.0   # signed: +charging, −discharging (bus side)
    cap_clamped:    str   = ""    # "" / "ceiling" / "floor" / "i_max"
    cap_headroom_W: float = 0.0   # how much more cap could absorb/release

    # Residual after cap (handled passively by droop).
    surplus_W:  float = 0.0       # bus-side overflow → droop exports it
    deficit_W:  float = 0.0       # bus-side shortfall → droop imports it

    # LED clamp diagnostic.
    led_clamped_W: float = 0.0    # how much LED would have been over the clamp


# ---------------- Helpers ----------------

def _safe_vbus(v):
    if v is None or v <= 0.1:
        return VBUS_FALLBACK
    return float(v)


def _discharge_i_max(v_cap):
    """Effective max discharge current as a function of v_cap, matching
    the cap firmware's linear taper:

        v_cap ≥ 11.0 V          →  full I_CAP_MAX
        10.5 V < v_cap < 11.0 V →  linear ramp from I_CAP_MAX to 0
        v_cap ≤ 10.5 V          →  0  (SMPS can't transfer)

    The algorithm respects this so its accounting matches reality — what
    we command in this region IS what the firmware will deliver, and
    `cap_p_W` doesn't over-promise."""
    if v_cap >= V_CAP_DISCHARGE_TAPER:
        return I_CAP_MAX
    if v_cap <= V_CAP_DISCHARGE_STOP:
        return 0.0
    scale = (v_cap - V_CAP_DISCHARGE_STOP) / (V_CAP_DISCHARGE_TAPER - V_CAP_DISCHARGE_STOP)
    return I_CAP_MAX * scale


def _active_deferrable_rates(deferrables, tick):
    """Return (total_rate_W, [per-deferrable diagnostic dicts]) for the
    deferrables whose window covers ``tick``.

    Units (per Azure convention — see SECONDS_PER_TICK):
        d.energy            joules (J)
        ticks_remaining     Azure ticks
        seconds_remaining   real seconds (ticks × 5)
        rate_W              = energy_J / seconds_remaining  →  watts

    Spreading energy linearly across the remaining real-time guarantees
    the deferrable completes on the deadline tick, with adaptive catch-up
    if previous ticks under-served (because the live d.energy from Azure
    already reflects what's still owed)."""
    total = 0.0
    detail = []
    for d in deferrables:
        if d.tick_start <= tick <= d.tick_end and d.energy > 0:
            ticks_remaining   = max(1, d.tick_end - tick + 1)
            seconds_remaining = ticks_remaining * SECONDS_PER_TICK
            rate = d.energy / seconds_remaining
            total += rate
            detail.append({
                "index":              d.index,
                "tick_start":         d.tick_start,
                "tick_end":           d.tick_end,
                "ticks_remaining":    ticks_remaining,
                "seconds_remaining":  seconds_remaining,
                "remaining_energy":   d.energy,
                "rate_W":             rate,
            })
    return total, detail


# ---------------- Core policy ----------------

def decide(state: GridState) -> Commands:
    cmd  = Commands()
    vbus = _safe_vbus(state.vbus)

    # Step 1 — derate PV from panel side to bus side.
    pv_bus = max(0.0, state.pv_p) * PV_EFFICIENCY

    # Step 2 — active deferrables become smooth load on the bus.
    def_rate_total, def_detail = _active_deferrable_rates(
        state.deferrables, state.tick
    )

    # Step 3 — effective load and net imbalance.
    demand = max(0.0, state.demand_p)
    effective_load = demand + def_rate_total
    net = pv_bus - effective_load

    # Step 4 — LED dissipates the entire effective load (split 3 ways).
    # The LED firmware clamps internally at 3 W/channel, but compute the
    # "would-have-been" overflow for diagnostics.
    led_each = effective_load / 3.0
    led_clamped_overflow = 0.0
    if led_each > P_LED_MAX_PER_CH:
        led_clamped_overflow = (led_each - P_LED_MAX_PER_CH) * 3.0
        led_each = P_LED_MAX_PER_CH

    cmd.led.p_red = led_each
    cmd.led.p_yel = led_each
    cmd.led.p_grn = led_each

    # Step 5 — cap absorbs / releases as much of the imbalance as it can.
    cap_clamped = ""
    cap_p = 0.0     # bus-side power: +charging, -discharging
    cap_headroom = 0.0

    if net > POWER_DEADBAND_W:
        cmd.regime = "surplus"

        if state.v_cap >= V_CAP_CHARGE_STOP:
            cap_clamped = "ceiling"
            cap_p = 0.0
            cap_headroom = 0.0
        else:
            i_request = net / vbus
            i_charge  = min(I_CAP_MAX, i_request)
            if i_request > I_CAP_MAX:
                cap_clamped = "i_max"
            cmd.cap.i_cmd = i_charge
            cap_p         = i_charge * vbus
            cap_headroom  = I_CAP_MAX * vbus - cap_p

        residual = max(0.0, net - cap_p)
        cmd.surplus_W = residual    # droop exports this
        cmd.deficit_W = 0.0

    elif net < -POWER_DEADBAND_W:
        cmd.regime = "deficit"
        deficit = -net

        # Effective max discharge current at the current v_cap, accounting
        # for the firmware's 10.5–11.0 V taper. At v_cap=10.5 V this is 0.
        i_max_now = _discharge_i_max(state.v_cap)

        if i_max_now <= 0:
            cap_clamped = "floor"
            cap_p = 0.0
            cap_headroom = 0.0
        else:
            # Compensate for cap-side SMPS loss on discharge: ask the firmware
            # for deficit / η so the bus actually sees ``deficit`` watts after
            # the converter loss.  i_cmd is BUS-SIDE current (firmware spec).
            i_request   = deficit / (vbus * ETA_CAP_SMPS)
            i_discharge = min(i_max_now, i_request)
            # Diagnose which clamp (if any) bit:
            if state.v_cap < V_CAP_DISCHARGE_TAPER:
                cap_clamped = "taper"          # in the 10.5–11.0 V soft region
            elif i_request > i_max_now:
                cap_clamped = "i_max"          # hit the 0.6 A hardware limit
            cmd.cap.i_cmd = -i_discharge
            # cap_p is signed bus-side power AFTER the firmware delivers it.
            cap_p         = -i_discharge * vbus * ETA_CAP_SMPS
            cap_headroom  = (i_max_now - i_discharge) * vbus * ETA_CAP_SMPS

        residual = max(0.0, deficit - (-cap_p))
        cmd.deficit_W = residual    # droop imports this
        cmd.surplus_W = 0.0

    else:
        cmd.regime = "idle"
        cap_p = 0.0
        cap_headroom = 0.0

    # ---- Fill diagnostics ----
    cmd.pv_panel_W         = state.pv_p
    cmd.pv_bus_W           = pv_bus
    cmd.demand_W           = demand
    cmd.def_rate_total_W   = def_rate_total
    cmd.effective_load_W   = effective_load
    cmd.net_W              = net
    cmd.active_deferrables = def_detail
    cmd.cap_p_W            = cap_p
    cmd.cap_clamped        = cap_clamped
    cmd.cap_headroom_W     = cap_headroom
    cmd.led_clamped_W      = led_clamped_overflow

    return cmd


# ---------------- DB adapter ----------------

def _f(v, default=0.0):
    try:    return float(v) if v is not None else default
    except (TypeError, ValueError): return default


def _i(v, default=0):
    try:    return int(v) if v is not None else default
    except (TypeError, ValueError): return default


def state_from_db_rows(grid_row, pv_row, cap_row) -> Optional[GridState]:
    """Build a GridState from SQLAlchemy rows. Returns None if grid_row missing."""
    if grid_row is None:
        return None

    raw = json.loads(str(getattr(grid_row, 'deferables_json', None) or "[]"))
    if not isinstance(raw, list):
        raw = []
    deferrables = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        start = item.get('tick_start', item.get('start'))
        end   = item.get('tick_end',   item.get('end'))
        if start is None or end is None:
            continue
        deferrables.append(Deferrable(
            index      = idx,
            tick_start = _i(start),
            tick_end   = _i(end),
            energy     = max(0.0, _f(item.get('energy'))),
        ))

    # Prefer the cap module's bus reading. It's electrically closest to the
    # actuator we're commanding (cap.i_cmd), so its sense of vbus is what
    # determines the actual bus power delivered. Fall back to PV only if
    # the cap module is missing telemetry entirely.
    vbus = _f(getattr(cap_row, 'vb_bus', None))
    if vbus <= 0:
        vbus = _f(getattr(pv_row, 'vb_bus', None))

    # Plumb the current-tick actual prices through to smart_v1's cap_policy.
    # The grid_row carries the live Azure prices for this tick; without this,
    # cap_policy falls back to forecast (mean curve) and misses arbitrage
    # opportunities whenever actual diverges from forecast by more than the
    # arb trigger (~50 ¢/J). Lab trace tick 4-9 saw forecast=35 but actual
    # 11-24 — without plumbing, the algorithm refuses to charge cheap; with
    # it, gain clears the trigger and the cap fills before the morning peak.
    actual_sell = _f(getattr(grid_row, 'sell_price', None), default=-1.0)
    actual_buy  = _f(getattr(grid_row, 'buy_price',  None), default=-1.0)

    return GridState(
        tick              = _i(getattr(grid_row, 'tick', 0)),
        pv_p              = max(0.0, _f(getattr(pv_row,  'p_panel',        None))),
        demand_p          = max(0.0, _f(getattr(grid_row,'instant_demand', None))),
        vbus              = vbus,
        v_cap             = _f(getattr(cap_row, 'v_cap',    None)),
        energy_cap        = max(0.0, _f(getattr(cap_row, 'energy_J', None))),
        deferrables       = deferrables,
        actual_sell_price = actual_sell if actual_sell >= 0 else None,
        actual_buy_price  = actual_buy  if actual_buy  >= 0 else None,
    )


def commands_to_payloads(cmd: Commands) -> Dict[str, Dict]:
    """Lower a Commands dataclass to the JSON payloads the firmware /cmd
    endpoints expect, keyed by role."""
    return {
        'cap': {
            'enable': cmd.cap.enable,
            'i_cmd':  round(cmd.cap.i_cmd, 4),
        },
        'led': {
            'enable': cmd.led.enable,
            'p_red':  round(cmd.led.p_red, 4),
            'p_yel':  round(cmd.led.p_yel, 4),
            'p_grn':  round(cmd.led.p_grn, 4),
        },
        'grid': {
            'enable':    cmd.grid.enable,
            'vb_target': cmd.grid.vb_target,
            'i_ref_max': round(cmd.grid.i_ref_max, 4),
        },
        'export': {
            'enable':    cmd.export.enable,
            'vb_target': cmd.export.vb_target,
            'i_ref_max': round(cmd.export.i_ref_max, 4),
        },
    }


def commands_to_diagnostics(cmd: Commands) -> Dict:
    """Project the Commands dataclass to the JSON shape the dashboard
    debug panel consumes. Stable shape — frontend code reads these keys."""
    return {
        "algo_id":          cmd.algo_id,
        "regime":           cmd.regime,
        "pv_panel_W":       round(cmd.pv_panel_W,       4),
        "pv_bus_W":         round(cmd.pv_bus_W,         4),
        "pv_eta_used":      cmd.pv_eta_used,
        "demand_W":         round(cmd.demand_W,         4),
        "def_rate_total_W": round(cmd.def_rate_total_W, 4),
        "effective_load_W": round(cmd.effective_load_W, 4),
        "net_W":            round(cmd.net_W,            4),
        "cap_p_W":          round(cmd.cap_p_W,          4),
        "cap_clamped":      cmd.cap_clamped,
        "cap_headroom_W":   round(cmd.cap_headroom_W,   4),
        "surplus_W":        round(cmd.surplus_W,        4),
        "deficit_W":        round(cmd.deficit_W,        4),
        "led_clamped_W":    round(cmd.led_clamped_W,    4),
        "active_deferrables": [
            {
                **d,
                "rate_W":           round(d["rate_W"], 4),
                "remaining_energy": round(d["remaining_energy"], 4),
            }
            for d in cmd.active_deferrables
        ],
        "seconds_per_tick": SECONDS_PER_TICK,
        "algo_extras":      cmd.algo_extras,
    }


# ---------------- Back-compat shim ----------------

def naivealgo(pv_p, demand, deferrable, vbus, energy_cap, tick, v_cap=12.0):
    """Legacy signature kept so any old caller still works.
    Returns just the cap i_cmd (a float)."""
    defs = []
    for idx, d in enumerate(deferrable or []):
        if not isinstance(d, dict):
            continue
        start = d.get('tick_start', d.get('start'))
        end   = d.get('tick_end',   d.get('end'))
        if start is None or end is None:
            continue
        defs.append(Deferrable(
            index      = idx,
            tick_start = int(start),
            tick_end   = int(end),
            energy     = max(0.0, float(d.get('energy', 0.0))),
        ))

    cmd = decide(GridState(
        tick        = int(tick),
        pv_p        = float(pv_p),
        demand_p    = float(demand),
        vbus        = float(vbus),
        v_cap       = float(v_cap),
        energy_cap  = float(energy_cap),
        deferrables = defs,
    ))
    return cmd.cap.i_cmd