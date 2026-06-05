"""Deterministic forecast of the Azure smart-grid day.

The Azure simulation (see Imperial ICelec50015 data_visualizer.html) has a
fully-deterministic *mean* — only Gaussian noise sits on top. So for any
tick ``t`` we can compute the expected sun, PV power, base demand, and
price from closed-form formulas without any data fitting.

Used by:
  - scheduler.py: rank future ticks by marginal cost-to-serve a deferrable
  - cap_policy.py: decide whether to charge/discharge for temporal arbitrage

All units are SI on the bus side. Prices are currency-per-joule
(the Azure convention).
"""

import math
from typing import List, Tuple

# --- Azure constants (mirrored from data_visualizer.html) ---
TICKS_PER_DAY        = 60
SUNRISE              = 15
DAY_LENGTH           = 30
BASE_DEMAND_PROFILE  = [(0, 25), (10, 25), (20, 100), (50, 100), (60, 25)]
BASE_DEMAND_SCALING  = 0.02        # multiplier from "raw demand units" to watts
BASE_PRICE           = 10.0        # ¢/J
PRICE_SOLAR_DEP      = 1.0
PRICE_MIN            = 10.0        # both buy/sell clamped at this floor (pre-BUY_RATIO)
BUY_RATIO            = 0.5         # buy_price = 0.5 × sell_price (grid-perspective)
PV_PEAK_W            = 8.0

# Conservative bus-side PV η (matches naive.PV_EFFICIENCY).
PV_EFFICIENCY        = 0.90


def expected_sun(tick: int) -> float:
    """Sunlight 0–100. Zero outside [SUNRISE, SUNRISE+DAY_LENGTH)."""
    if tick < SUNRISE or tick >= SUNRISE + DAY_LENGTH:
        return 0.0
    return math.floor(math.sin((tick - SUNRISE) * math.pi / DAY_LENGTH) * 100)


def expected_pv_panel_W(tick: int) -> float:
    """Panel-side expected PV power (W)."""
    return expected_sun(tick) * (PV_PEAK_W / 100.0)


def expected_pv_bus_W(tick: int) -> float:
    """Bus-side expected PV power, after the boost converter η."""
    return expected_pv_panel_W(tick) * PV_EFFICIENCY


def expected_base_demand_raw(tick: int) -> float:
    """Piecewise-linear raw base demand at ``tick`` (pre-scaling)."""
    prev = (0, 0)
    for p in BASE_DEMAND_PROFILE:
        if tick < p[0]:
            x0, y0 = prev
            x1, y1 = p
            if x1 == x0:
                return y1
            return (tick - x0) / (x1 - x0) * (y1 - y0) + y0
        prev = p
    return prev[1]


def expected_demand_W(tick: int) -> float:
    """Bus-side expected base demand (W)."""
    return expected_base_demand_raw(tick) * BASE_DEMAND_SCALING


def expected_sell_price(tick: int) -> float:
    """Per-tick price the grid charges us on imports (¢/J).
    Mirrors data_visualizer.html: max(PRICE_MIN, BASE_PRICE + (base − sun))."""
    base = expected_base_demand_raw(tick)
    sun  = expected_sun(tick)
    return max(PRICE_MIN, BASE_PRICE + (base - sun) * PRICE_SOLAR_DEP)


def expected_buy_price(tick: int) -> float:
    """Per-tick price the grid pays us on exports (¢/J)."""
    return expected_sell_price(tick) * BUY_RATIO


def expected_net_W(tick: int) -> float:
    """Bus-side PV minus base demand (no deferrables). +surplus / -deficit."""
    return expected_pv_bus_W(tick) - expected_demand_W(tick)


def price_curve(t_start: int, t_end: int) -> List[Tuple[int, float, float]]:
    """Return [(tick, sell_price, buy_price)] across [t_start, t_end]."""
    out = []
    for t in range(t_start, t_end + 1):
        out.append((t, expected_sell_price(t), expected_buy_price(t)))
    return out


# --- Sanity print: run `python forecast.py` to eyeball the day shape ---
if __name__ == "__main__":  # pragma: no cover
    print(f"{'tick':>4} {'sun':>5} {'pv_W':>6} {'dem_W':>6} {'sell':>6} {'buy':>6} {'net_W':>7}")
    for t in range(0, 60, 2):
        print(f"{t:>4} {expected_sun(t):>5.0f} {expected_pv_bus_W(t):>6.2f} "
              f"{expected_demand_W(t):>6.2f} {expected_sell_price(t):>6.1f} "
              f"{expected_buy_price(t):>6.1f} {expected_net_W(t):>7.2f}")
