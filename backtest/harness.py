"""Replay harness — score an algorithm against a recorded Azure day.

Physical model (deliberately conservative, matches firmware behaviour):

  PV          panel × η_PV  → bus
  Cap charge  i_cmd × vbus  W drawn from bus;  η_SMPS reaches cap
  Cap discharge  |i_cmd| × vbus × η_SMPS W reaches bus; cap loses
                 |i_cmd| × vbus  (cap-side, no double-counting of η)
  Cap leakage  E × leak_rate / tick  (continuous, after step)
  LED         dissipates effective_load (clamped at 9 W total)
  Grid I/O    droop closes the bus balance; cost incurred at PSU side
              with η_PSU < 1 (lecturer convention: P_PSU = P_bus / η_PSU)

Scoring (lower = better):
  net_cost = Σ_tick [ import_J × sell_price / η_PSU_in
                    − export_J × buy_price × η_PSU_out ]
           + unmet_deferable_penalty × Σ_unmet_J

The penalty rate is the day's mean sell_price — i.e. unmet J cost ≈
the worst-case grid replacement price.
"""

import json
import math
import os
import statistics
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple

from buysellalgorithm import naive, smart_v1, forecast, served_tracker
from buysellalgorithm.naive import GridState, Deferrable


# ---- Physical constants for the sim ----
C_CAP             = 0.5      # F, super-capacitor
V_CAP_MIN         = 10.5
V_CAP_MAX         = 15.7
V_BUS_NOMINAL     = 10.0
PV_PEAK_W         = 4.0      # normal-day, not demo day
PV_ETA            = 0.90     # boost converter
SMPS_ETA          = 0.90     # cap-side, both directions
SECONDS_PER_TICK  = 5.0
LEAK_PER_TICK     = 0.0025   # 0.25%/tick continuous leakage
LED_MAX_TOTAL_W   = 9.0
PSU_ETA_IN        = 1.0      # match dashboard: cost = bus_W × sell_price (no /η)
PSU_ETA_OUT       = 1.0      # match dashboard: revenue = bus_W × buy_price (no ×η)


@dataclass
class DayResult:
    label:                str
    net_cost:             float        # ¢ (lower = better)
    import_J:             float
    export_J:             float
    import_cost:          float        # ¢, PSU-side
    export_revenue:       float        # ¢, PSU-side
    leakage_J:            float
    unmet_J:              float
    unmet_penalty:        float
    by_tick:              List[Dict] = field(default_factory=list)


def default_deferrables() -> List[Deferrable]:
    """Three obligations representative of real Azure days (from DB samples,
    days 5933320–5933325 — total ~90–130 J/day, with one always-on 50 J
    plus a mid-day and a late-day deferable)."""
    return [
        Deferrable(index=0, tick_start=0,  tick_end=59, energy=50.0),
        Deferrable(index=1, tick_start=20, tick_end=45, energy=35.0),
        Deferrable(index=2, tick_start=42, tick_end=59, energy=30.0),
    ]


def _energy_to_v(E: float) -> float:
    return math.sqrt(max(0.0, 2.0 * E / C_CAP))


def _v_to_energy(V: float) -> float:
    return 0.5 * C_CAP * V * V


def replay(
    day_data: List[Dict],
    decide: Callable[[GridState], object],
    label: str,
    deferrables: List[Deferrable] = None,
    v_cap_start: float = 13.0,
    apply_psu_loss: bool = True,
    verbose: bool = False,
) -> DayResult:
    if deferrables is None:
        deferrables = default_deferrables()

    served_tracker.reset_all()
    served_J: Dict[int, float] = {}

    v_cap = v_cap_start
    v_bus = V_BUS_NOMINAL

    res = DayResult(
        label=label, net_cost=0.0,
        import_J=0.0, export_J=0.0,
        import_cost=0.0, export_revenue=0.0,
        leakage_J=0.0, unmet_J=0.0, unmet_penalty=0.0,
    )

    psu_in  = PSU_ETA_IN  if apply_psu_loss else 1.0
    psu_out = PSU_ETA_OUT if apply_psu_loss else 1.0

    for entry in day_data:
        t      = int(entry['tick'])
        sell   = float(entry['sell_price'])
        buy    = float(entry['buy_price'])
        demand = float(entry['demand'])

        sun_now    = forecast.expected_sun(t)
        pv_panel   = sun_now * (PV_PEAK_W / 100.0)
        pv_bus_W   = pv_panel * PV_ETA

        state = GridState(
            tick                 = t,
            pv_p                 = pv_panel,
            demand_p             = demand,
            vbus                 = v_bus,
            v_cap                = v_cap,
            energy_cap           = _v_to_energy(v_cap),
            deferrables          = [Deferrable(d.index, d.tick_start, d.tick_end, d.energy) for d in deferrables],
            deferrables_served_J = dict(served_J),
            day                  = 0,
        )
        # Optional: leak real prices through to algorithms that look for them.
        state.actual_sell_price = sell
        state.actual_buy_price  = buy

        cmd = decide(state)

        # --- Apply LED dissipation (firmware clamps at 3 W/ch = 9 W total) ---
        led_W = min(LED_MAX_TOTAL_W,
                    cmd.led.p_red + cmd.led.p_yel + cmd.led.p_grn)

        # --- Cap action ---
        i_cmd = cmd.cap.i_cmd
        if i_cmd > 0:
            # charge
            bus_cap_W      = i_cmd * v_bus                              # bus loses this
            cap_energy_in  = bus_cap_W * SMPS_ETA * SECONDS_PER_TICK    # cap gains η of it
        else:
            # discharge
            bus_cap_W      = -(abs(i_cmd) * v_bus * SMPS_ETA)           # bus gains η of cap loss
            cap_energy_in  = -abs(i_cmd) * v_bus * SECONDS_PER_TICK     # cap loses cap-side energy

        E_cap_now = _v_to_energy(v_cap)
        E_after   = E_cap_now + cap_energy_in
        # Continuous leakage (apply after the step)
        E_leak    = max(0.0, E_after) * LEAK_PER_TICK
        E_new     = E_after - E_leak
        # Physical clamps
        E_max = _v_to_energy(V_CAP_MAX)
        E_min = _v_to_energy(V_CAP_MIN)
        E_new = min(E_max, max(E_min, E_new))
        v_cap = _energy_to_v(E_new)
        res.leakage_J += max(0.0, E_leak)

        # --- Bus balance ---
        # Source side: PV + cap discharge contribution
        # Sink side: LED + cap charge consumption
        bus_in  = pv_bus_W + max(0.0, -bus_cap_W)
        bus_out = led_W    + max(0.0, bus_cap_W)
        bus_net = bus_in - bus_out                  # +export / -import

        if bus_net > 0:
            export_W = bus_net
            import_W = 0.0
        else:
            export_W = 0.0
            import_W = -bus_net

        # --- Cost / revenue (¢/J already in data; apply PSU η at user side) ---
        imp_J = import_W * SECONDS_PER_TICK
        exp_J = export_W * SECONDS_PER_TICK
        # At PSU side: pay sell × (bus_J / η_in) because PSU has to supply more
        imp_cost = imp_J * sell / psu_in
        exp_rev  = exp_J * buy  * psu_out

        res.import_J       += imp_J
        res.export_J       += exp_J
        res.import_cost    += imp_cost
        res.export_revenue += exp_rev

        # --- Credit served deferrables ---
        for d_info in getattr(cmd, 'active_deferrables', []) or []:
            idx  = d_info.get('index')
            rate = d_info.get('rate_W', 0.0)
            if idx is None:
                continue
            served_J[idx] = served_J.get(idx, 0.0) + rate * SECONDS_PER_TICK

        if verbose:
            res.by_tick.append({
                "t": t, "sell": sell, "buy": buy,
                "pv_bus": round(pv_bus_W, 2),
                "led": round(led_W, 2),
                "v_cap": round(v_cap, 2),
                "cap_bus_W": round(bus_cap_W, 2),
                "imp_W": round(import_W, 2),
                "exp_W": round(export_W, 2),
                "regime": cmd.regime,
                "reason": (cmd.algo_extras or {}).get("cap_action_reason", ""),
            })

    # --- Unmet deferable penalty ---
    avg_sell = statistics.mean(float(e['sell_price']) for e in day_data)
    for d in deferrables:
        already = served_J.get(d.index, 0.0)
        unmet   = max(0.0, d.energy - already)
        res.unmet_J       += unmet
        res.unmet_penalty += unmet * avg_sell

    res.net_cost = res.import_cost - res.export_revenue + res.unmet_penalty
    return res


def load_day(path: str) -> List[Dict]:
    with open(path) as f:
        return json.load(f)


def score_one(day_path: str, label: str = None) -> Dict[str, DayResult]:
    day = load_day(day_path)
    name = label or os.path.basename(day_path).replace('.json', '')
    out = {}
    out[f"{name}_naive"]    = replay(day, naive.decide,    f"{name}_naive")
    out[f"{name}_smartv1"]  = replay(day, smart_v1.decide, f"{name}_smartv1")
    return out


def pretty(results: Dict[str, DayResult]) -> None:
    print(f"{'label':<22} {'net_¢':>9} {'imp¢':>9} {'expR¢':>9} {'unmetJ':>7} {'leakJ':>7} {'impJ':>7} {'expJ':>7}")
    for k, r in results.items():
        print(f"{k:<22} {r.net_cost:>9.1f} {r.import_cost:>9.1f} {r.export_revenue:>9.1f} "
              f"{r.unmet_J:>7.1f} {r.leakage_J:>7.1f} {r.import_J:>7.1f} {r.export_J:>7.1f}")


if __name__ == "__main__":
    import glob
    here = os.path.dirname(__file__)
    all_results = {}
    day_files = sorted(glob.glob(os.path.join(here, "data", "day*.json")))
    for path in day_files:
        all_results.update(score_one(path))
    pretty(all_results)
    print()
    # Per-day summary
    print(f"{'day':<6} {'naive_¢':>9} {'smart_¢':>9} {'saved_¢':>9} {'%':>6}")
    naive_total = smartv1_total = 0.0
    for path in day_files:
        name = os.path.basename(path).replace('.json','')
        n = all_results[f"{name}_naive"].net_cost
        s = all_results[f"{name}_smartv1"].net_cost
        naive_total += n
        smartv1_total += s
        pct = 100*(n-s)/n if n else 0.0
        print(f"{name:<6} {n:>9.1f} {s:>9.1f} {n-s:>+9.1f} {pct:>+5.1f}%")
    delta = naive_total - smartv1_total
    print()
    print(f"TOTAL  naive={naive_total:.1f}¢   smartv1={smartv1_total:.1f}¢   "
          f"smart-saved={delta:+.1f}¢ ({100*delta/abs(naive_total):+.1f}%)")
