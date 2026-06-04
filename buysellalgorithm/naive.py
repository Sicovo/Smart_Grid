"""Naive grid-balancing policy.

Pure decision function: given a snapshot of the grid + bus state, return
the commands to issue to each firmware module. No DB, no HTTP, no globals.

Goal: minimise grid import and export. The supercap is the primary
balancing actuator; grid + export are the passive safety net.

Architecture: **always-enabled symmetric droop**.
  - grid   is always enabled, vb_target = 9.9 V
  - export is always enabled, vb_target = 10.1 V
  - Together they form a 9.9–10.1 V deadband on the bus.
  - As long as cap can absorb/release the imbalance, the bus stays inside
    the deadband and NEITHER grid nor export flows current. Zero import,
    zero export.
  - When cap saturates (SoC ceiling on charge, floor on discharge, or
    |i_cmd| > 0.6 A), the bus drifts out of the deadband and the relevant
    side of the droop takes over automatically. No mode switch needed.

Active policy (decides cap and LED setpoints each tick):

    net = pv_p - demand_p

    SURPLUS  (net > deadband):
        1. Serve deferrables EDF — they consume directly from PV at 100 %
           efficiency, which is the cheapest way to reduce future demand.
        2. Charge cap with whatever's left over (clamped at 15.7 V).
        3. Anything still left → droop exports it passively.

    DEFICIT  (net < -deadband):
        1. Discharge cap to cover the deficit (refused below 11.0 V).
        2. Anything still uncovered → droop imports it passively.

    IDLE     (|net| ≤ deadband):
        cap.i_cmd = 0; droop holds the bus.

LED setpoint = demand_p + served_deferrable_power, split equally across
the three channels. LEDs are the only physical load that can dissipate
both base demand and the deferrable energy buckets.

Firmware-matched constants (see firmware/cap_smps/main.py):
  - V_CAP_CHARGE_STOP    = 15.7 V  (firmware hard charge cutoff)
  - V_CAP_DISCHARGE_STOP = 11.0 V  (firmware starts tapering below this)
  - I_CAP_MAX            = 0.60 A  (firmware clamp)
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

VBUS_FALLBACK = 9.9           # if telemetry missing / invalid
POWER_DEADBAND_W = 1.0        # don't bother enabling grid/export for crumbs


# ---------------- Types ----------------

@dataclass
class Deferrable:
    index:      int
    tick_start: int
    tick_end:   int
    energy:     float   # remaining energy at this tick (W, treated as power per tick)


@dataclass
class GridState:
    tick:        int
    pv_p:        float                          # PV power available  (W)
    demand_p:    float                          # base demand         (W)
    vbus:        float                          # measured bus voltage (V)
    v_cap:       float                          # supercap terminal voltage (V)
    energy_cap:  float                          # available cap energy (J)
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
    # Always enabled — passive droop safety net. Only flows current when
    # bus sags below 9.9 V (i.e. cap has saturated on the discharge side).
    enable:    int   = 1
    vb_target: float = VB_TARGET_GRID
    i_ref_max: float = GRID_I_REF_MAX_HW


@dataclass
class ExportCmd:
    # Always enabled — passive droop safety net. Only flows current when
    # bus rises above 10.1 V (i.e. cap has saturated on the charge side).
    enable:    int   = 1
    vb_target: float = VB_TARGET_EXPORT
    i_ref_max: float = EXPORT_I_REF_MAX_HW


@dataclass
class Commands:
    cap:                CapCmd     = field(default_factory=CapCmd)
    led:                LedCmd     = field(default_factory=LedCmd)
    grid:               GridCmd    = field(default_factory=GridCmd)
    export:             ExportCmd  = field(default_factory=ExportCmd)
    served_deferrables: List[Dict] = field(default_factory=list)
    surplus_W:          float      = 0.0
    deficit_W:          float      = 0.0
    regime:             str        = "idle"   # "surplus" | "deficit" | "idle"


# ---------------- Helpers ----------------

def _safe_vbus(v):
    if v is None or v <= 0.1:
        return VBUS_FALLBACK
    return float(v)


def _serve_deferrables_edf(deferrables, surplus, tick):
    """Earliest-deadline-first allocation of surplus to active jobs.
    Returns (served_list, remaining_surplus, served_power_total)."""
    served = []
    served_power = 0.0
    active = sorted(
        [d for d in deferrables
         if d.tick_start <= tick <= d.tick_end and d.energy > 0],
        key=lambda d: d.tick_end,
    )
    for d in active:
        if surplus <= 0:
            break
        used = min(d.energy, surplus)
        surplus     -= used
        served_power += used
        served.append({
            'index':            d.index,
            'served_energy':    used,
            'remaining_energy': d.energy - used,
            'tick_start':       d.tick_start,
            'tick_end':         d.tick_end,
        })
    return served, max(0.0, surplus), served_power


# ---------------- Core policy ----------------

def decide(state: GridState) -> Commands:
    cmd  = Commands()
    vbus = _safe_vbus(state.vbus)
    net  = state.pv_p - state.demand_p

    # LED base = demand (always must be served). Surplus path may add served
    # deferrable power on top — computed after deferrable allocation below.
    led_total = max(0.0, state.demand_p)

    # Grid and export are ALWAYS enabled at their droop targets (set by
    # GridCmd / ExportCmd defaults). The naive only commands the cap and
    # the LED — droop handles overflow / underflow passively.

    if net > POWER_DEADBAND_W:
        # ---------- SURPLUS ----------
        cmd.regime = "surplus"
        served, leftover, served_power = _serve_deferrables_edf(
            state.deferrables, net, state.tick
        )
        cmd.served_deferrables = served
        led_total += served_power

        # Charge cap with the remainder, clamped to firmware cutoff.
        if leftover > 0 and state.v_cap < V_CAP_CHARGE_STOP:
            i_charge      = min(I_CAP_MAX, leftover / vbus)
            cmd.cap.i_cmd = i_charge
            leftover     -= i_charge * vbus

        # Anything still left over → droop will export it passively.
        cmd.surplus_W = max(0.0, leftover)

    elif net < -POWER_DEADBAND_W:
        # ---------- DEFICIT ----------
        cmd.regime = "deficit"
        deficit = -net

        # Discharge cap if it has usable energy.
        if state.v_cap > V_CAP_DISCHARGE_STOP and state.energy_cap > 0:
            i_discharge   = min(I_CAP_MAX, deficit / vbus)
            cmd.cap.i_cmd = -i_discharge
            deficit      -= i_discharge * vbus

        # Anything still uncovered → droop will import it passively.
        cmd.deficit_W = max(0.0, deficit)

    else:
        # ---------- BALANCED ----------
        # Within the droop deadband; cap idles, droop holds the bus.
        cmd.regime = "idle"

    # LED setpoints — equal split across 3 channels.
    each = led_total / 3.0
    cmd.led.p_red = each
    cmd.led.p_yel = each
    cmd.led.p_grn = each

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


# ---------------- Back-compat shim for the old name ----------------

def naivealgo(pv_p, demand, deferrable, vbus, energy_cap, tick,
              v_cap=12.0):
    """Legacy signature kept so any old caller still works.
    Returns just the cap i_cmd (a float), matching the old contract.
    Prefer ``decide()`` for new code."""
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
