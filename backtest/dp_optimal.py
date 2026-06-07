"""DP-based optimal cap dispatch with perfect day knowledge.

Used to bound how much further the heuristic smart_v1 can improve.
Treats deferable schedule as exogenous (uses scheduler.allocate_all
forward); DPs only the cap action.
"""

import math
import os
import numpy as np

from buysellalgorithm import scheduler, served_tracker, forecast
from buysellalgorithm.naive import Deferrable

from backtest.harness import (
    C_CAP, V_CAP_MIN, V_CAP_MAX, V_BUS_NOMINAL, PV_PEAK_W, PV_ETA, SMPS_ETA,
    SECONDS_PER_TICK, LEAK_PER_TICK,
    PSU_ETA_IN, PSU_ETA_OUT,
    default_deferrables, load_day,
)


def precompute_eff_load(day, deferrables):
    """Run smart's scheduler forward, returning per-tick (eff_load, pv_bus)."""
    served_tracker.reset_all()
    served = {}
    eff = np.zeros(60)
    pv  = np.zeros(60)
    for entry in day:
        t = int(entry['tick'])
        demand = float(entry['demand'])
        sun = forecast.expected_sun(t)
        pv[t] = sun * (PV_PEAK_W / 100.0) * PV_ETA
        rate, detail = scheduler.allocate_all(
            [Deferrable(d.index, d.tick_start, d.tick_end, d.energy) for d in deferrables],
            t, dict(served)
        )
        eff[t] = demand + rate
        for d in detail:
            served[d['index']] = served.get(d['index'], 0.0) + d['rate_W'] * SECONDS_PER_TICK
    return eff, pv


def solve_dp(day, deferrables=None, v_start: float = 13.0, a_step: float = 0.1, v_step: float = 0.025):
    if deferrables is None:
        deferrables = default_deferrables()
    eff, pv = precompute_eff_load(day, deferrables)
    sell = np.array([float(e['sell_price']) for e in day])
    buy  = np.array([float(e['buy_price'])  for e in day])

    V_GRID = np.arange(V_CAP_MIN, V_CAP_MAX + 1e-9, v_step)
    nV = len(V_GRID)
    A_GRID = np.arange(-6.0, 6.0 + 1e-9, a_step)
    nA = len(A_GRID)

    E_max = 0.5 * C_CAP * V_CAP_MAX ** 2
    E_min = 0.5 * C_CAP * V_CAP_MIN ** 2

    V_fn   = np.zeros((61, nV))
    policy = np.zeros((60, nV), dtype=np.int16)

    for t in range(59, -1, -1):
        Vt = np.full(nV, np.inf)
        Pt = np.zeros(nV, dtype=np.int16)
        for vi, v in enumerate(V_GRID):
            E_now = 0.5 * C_CAP * v * v
            headroom = max(0.0, E_max - E_now)
            available = max(0.0, E_now - E_min)
            a_max_c = min(6.0, headroom  / (SMPS_ETA * SECONDS_PER_TICK))
            a_max_d = min(6.0 * SMPS_ETA, available * SMPS_ETA / SECONDS_PER_TICK)

            best = np.inf
            best_ai = 0
            for ai, a in enumerate(A_GRID):
                if a > a_max_c + 1e-9 or -a > a_max_d + 1e-9:
                    continue
                if a >= 0:
                    cap_E_gain = a * SMPS_ETA * SECONDS_PER_TICK
                    bus_cap_W  = a
                else:
                    cap_E_gain = a / SMPS_ETA * SECONDS_PER_TICK
                    bus_cap_W  = a
                E_after = E_now + cap_E_gain
                E_leak  = max(0.0, E_after) * LEAK_PER_TICK
                E_new   = min(E_max, max(E_min, E_after - E_leak))
                v_new   = math.sqrt(max(0.0, 2.0 * E_new / C_CAP))
                vf  = (v_new - V_CAP_MIN) / v_step
                vlo = max(0, int(math.floor(vf)))
                vhi = min(nV - 1, vlo + 1)
                f   = vf - vlo
                V_next = (1 - f) * V_fn[t + 1, vlo] + f * V_fn[t + 1, vhi]

                bus_in  = pv[t] + max(0.0, -bus_cap_W)
                bus_out = eff[t] + max(0.0,  bus_cap_W)
                bus_net = bus_in - bus_out
                if bus_net > 0:
                    exp_J = bus_net * SECONDS_PER_TICK; imp_J = 0
                else:
                    imp_J = -bus_net * SECONDS_PER_TICK; exp_J = 0
                step = imp_J * sell[t] / PSU_ETA_IN - exp_J * buy[t] * PSU_ETA_OUT
                tot = step + V_next
                if tot < best:
                    best = tot
                    best_ai = ai
            Vt[vi] = best
            Pt[vi] = best_ai
        V_fn[t]   = Vt
        policy[t] = Pt

    vi_start = int(round((v_start - V_CAP_MIN) / v_step))
    return V_fn, policy, V_GRID, A_GRID, eff, pv, sell, buy, vi_start


def replay_optimal(day, deferrables=None, v_start: float = 13.0, **kw):
    V_fn, policy, V_GRID, A_GRID, eff, pv, sell, buy, vi_start = solve_dp(day, deferrables, v_start, **kw)
    v_cap = v_start
    total_cost = total_imp = total_exp = 0.0
    log = []
    E_max = 0.5 * C_CAP * V_CAP_MAX ** 2
    E_min = 0.5 * C_CAP * V_CAP_MIN ** 2
    v_step = V_GRID[1] - V_GRID[0]
    for t in range(60):
        vi = int(round((v_cap - V_CAP_MIN) / v_step))
        vi = min(len(V_GRID) - 1, max(0, vi))
        a  = A_GRID[policy[t, vi]]
        if a >= 0:
            cap_E_gain = a * SMPS_ETA * SECONDS_PER_TICK
            bus_cap_W  = a
        else:
            cap_E_gain = a / SMPS_ETA * SECONDS_PER_TICK
            bus_cap_W  = a
        E_now   = 0.5 * C_CAP * v_cap ** 2
        E_after = E_now + cap_E_gain
        E_leak  = max(0.0, E_after) * LEAK_PER_TICK
        E_new   = min(E_max, max(E_min, E_after - E_leak))
        v_cap   = math.sqrt(max(0.0, 2.0 * E_new / C_CAP))
        bus_in  = pv[t] + max(0.0, -bus_cap_W)
        bus_out = eff[t] + max(0.0,  bus_cap_W)
        bus_net = bus_in - bus_out
        if bus_net > 0:
            exp_J = bus_net * SECONDS_PER_TICK; imp_J = 0
        else:
            imp_J = -bus_net * SECONDS_PER_TICK; exp_J = 0
        total_imp += imp_J; total_exp += exp_J
        total_cost += imp_J * sell[t] / PSU_ETA_IN - exp_J * buy[t] * PSU_ETA_OUT
        log.append((t, sell[t], v_cap, a, imp_J, exp_J))
    return total_cost, total_imp, total_exp, log


if __name__ == "__main__":
    here = os.path.dirname(__file__)
    total = 0.0
    for day_name in ('day1', 'day2'):
        day = load_day(os.path.join(here, 'data', f'{day_name}.json'))
        cost, imp, exp, log = replay_optimal(day)
        total += cost
        print(f'{day_name} OPTIMAL: cost={cost:.1f}c  imp={imp:.1f}J  exp={exp:.1f}J')
    print(f'TOTAL optimal = {total:.1f}c')
