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
   Each active deferrable has a smooth required rate:
       rate_W = remaining_energy / max(1, tick_end − tick + 1)
   That spreads the energy linearly across the remaining ticks, ADAPTIVE
   to any catch-up needed (if we under-served last tick, rate goes up).
   At the deadline tick, rate equals remaining_energy — last-chance dump.

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

V_CAP_CHARGE_STOP    = 15.7   # match firmware V_CAP_CHARGE_CUTOFF
V_CAP_DISCHARGE_STOP = 11.0   # match firmware V_CAP_TAPER_LO
I_CAP_MAX            = 0.60   # match firmware I_CAP_MAX

VB_TARGET_GRID   = 9.9
VB_TARGET_EXPORT = 10.1

GRID_I_REF_MAX_HW   = 2.0     # match grid_smps   I_REF_HI
EXPORT_I_REF_MAX_HW = 2.0     # match export_smps I_REF_HI

VBUS_FALLBACK    = 9.9        # if telemetry missing / invalid
POWER_DEADBAND_W = 1.0        # idle band on the net imbalance

# Conservative PV boost-converter efficiency. Bus-side PV power = panel × this.
# 0.80 is intentionally pessimistic — covers boost loss + cabling + cap-module
# standby + LED converter loss. If we ever measure actual η > 0.85 we can bump.
PV_EFFICIENCY = 0.80

# LED firmware datasheet clamp — won't accept >3 W per channel.
P_LED_MAX_PER_CH = 3.0


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
    regime: str = "idle"          # "surplus" | "deficit" | "idle"

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


def _active_deferrable_rates(deferrables, tick):
    """Return (total_rate_W, [per-deferrable diagnostic dicts]) for the
    deferrables whose window covers ``tick``. Each rate is
    remaining_energy / ticks_remaining, so the bucket completes by its
    deadline even if we under-served earlier ticks."""
    total = 0.0
    detail = []
    for d in deferrables:
        if d.tick_start <= tick <= d.tick_end and d.energy > 0:
            ticks_remaining = max(1, d.tick_end - tick + 1)
            rate = d.energy / ticks_remaining
            total += rate
            detail.append({
                "index":              d.index,
                "tick_start":         d.tick_start,
                "tick_end":           d.tick_end,
                "ticks_remaining":    ticks_remaining,
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

        if state.v_cap <= V_CAP_DISCHARGE_STOP or state.energy_cap <= 0:
            cap_clamped = "floor"
            cap_p = 0.0
            cap_headroom = 0.0
        else:
            i_request   = deficit / vbus
            i_discharge = min(I_CAP_MAX, i_request)
            if i_request > I_CAP_MAX:
                cap_clamped = "i_max"
            cmd.cap.i_cmd = -i_discharge
            cap_p         = -i_discharge * vbus
            cap_headroom  = I_CAP_MAX * vbus - i_discharge * vbus

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

    vbus = _f(getattr(cap_row, 'vb_bus', None))
    if vbus <= 0:
        vbus = _f(getattr(pv_row, 'vb_bus', None))

    return GridState(
        tick        = _i(getattr(grid_row, 'tick', 0)),
        pv_p        = max(0.0, _f(getattr(pv_row,  'p_panel',        None))),
        demand_p    = max(0.0, _f(getattr(grid_row,'instant_demand', None))),
        vbus        = vbus,
        v_cap       = _f(getattr(cap_row, 'v_cap',    None)),
        energy_cap  = max(0.0, _f(getattr(cap_row, 'energy_J', None))),
        deferrables = deferrables,
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
