"""Forecast-aware deferrable scheduler.

The naive baseline (``naive.py``) spreads each deferrable's remaining
joules linearly across its remaining real-time. That's safe but blind:
it serves 1 J on a 10 ¢/J midday tick just as eagerly as on a 100 ¢/J
evening tick.

This scheduler instead ranks every future tick in the deferrable's
remaining window by the **marginal cost of serving 1 J there**, then
greedily fills the cheapest ticks first. The output ``rate_W`` for the
current tick goes back into the same "deferrables as bus load" math the
naive policy uses, so the only change downstream is the cap/grid balance
shift that follows.

Marginal cost model (grid-perspective prices, all positive — lower = better):
  - If forecast_net(t) > 0  (PV surplus that would have been exported at
    buy_price): cost = +buy_price(t) — serving here is the foregone
    export revenue. Cheap because buy ≈ 0.5 × sell.
  - If forecast_net(t) < 0  (we'd have imported to cover): cost =
    +sell_price(t) — serving here is the marginal import cost. Expensive.
  - Surplus ticks therefore dominate the cheap end of the ranking.
  - Tie-break by serving earlier (less leakage risk for downstream
    cap interactions).

Capacity per tick is bounded by the LED dissipator's headroom (3 W/ch ×
3 ch = 9 W, minus whatever base demand and other deferrables are already
booked there).
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple

from . import forecast


SECONDS_PER_TICK = 5.0

# How much LED dissipator capacity is available per tick, total across all
# three channels. Matches naive.P_LED_MAX_PER_CH × 3.
LED_TOTAL_CAP_W  = 9.0


@dataclass
class Deferrable:
    """Mirror of naive.Deferrable — duplicated here to avoid a circular
    import (smart_v1.py imports both modules)."""
    index:      int
    tick_start: int
    tick_end:   int
    energy:     float       # joules remaining


def _tick_capacity_W(t: int, already_booked_W: float) -> float:
    """How much MORE deferrable load tick ``t`` can absorb without
    exceeding the LED dissipator's 9 W bus-side cap, after subtracting
    base demand and already-booked deferrable rates for that tick."""
    base = forecast.expected_demand_W(t)
    free = LED_TOTAL_CAP_W - base - already_booked_W
    return max(0.0, free)


def allocate_one(
    d: Deferrable, current_tick: int, already_booked_per_tick: Dict[int, float]
) -> Tuple[float, List[Tuple[int, float]]]:
    """Allocate ``d.energy`` joules across the cheapest ticks in
    [current_tick, d.tick_end].

    Returns:
      (rate_W_this_tick, [(tick, allocated_J), ...])

    ``already_booked_per_tick`` is mutated in place so subsequent
    deferrables see this one's bookings.
    """
    if d.energy <= 0 or current_tick > d.tick_end:
        return 0.0, []

    t_start = max(current_tick, d.tick_start)
    ticks = list(range(t_start, d.tick_end + 1))
    if not ticks:
        return 0.0, []

    # Marginal cost per tick — all positive, lower = cheaper to serve here.
    scored = []
    for t in ticks:
        net = forecast.expected_net_W(t)
        if net > 0.5:                      # PV surplus → foregone export revenue
            cost = forecast.expected_buy_price(t)
        else:                               # have to import → marginal import cost
            cost = forecast.expected_sell_price(t)
        scored.append((cost, t))

    # Cheapest first, then earliest (tie-break favours earlier so the
    # cap-policy decisions downstream see this energy ASAP and don't
    # need to bank it).
    scored.sort(key=lambda x: (x[0], x[1]))

    remaining_J = d.energy
    bookings: List[Tuple[int, float]] = []
    rate_this_tick = 0.0

    for _, t in scored:
        if remaining_J <= 1e-6:
            break
        cap_W = _tick_capacity_W(t, already_booked_per_tick.get(t, 0.0))
        if cap_W <= 0:
            continue
        # Up to cap_W × SECONDS_PER_TICK joules can go here.
        slot_J = min(cap_W * SECONDS_PER_TICK, remaining_J)
        slot_W = slot_J / SECONDS_PER_TICK
        bookings.append((t, slot_J))
        already_booked_per_tick[t] = already_booked_per_tick.get(t, 0.0) + slot_W
        remaining_J -= slot_J
        if t == current_tick:
            rate_this_tick += slot_W

    # If we still have remaining_J that wouldn't fit anywhere — that's a
    # warning sign (deferrable can't be served even with the LED cap),
    # but we still owe the energy. Force it into the deadline tick.
    if remaining_J > 1e-3 and ticks:
        deadline = ticks[-1]
        slot_W = remaining_J / SECONDS_PER_TICK
        bookings.append((deadline, remaining_J))
        already_booked_per_tick[deadline] = already_booked_per_tick.get(deadline, 0.0) + slot_W
        if deadline == current_tick:
            rate_this_tick += slot_W

    return rate_this_tick, bookings


def allocate_all(
    deferrables: List[Deferrable],
    current_tick: int,
    served_J_per_idx: Dict[int, float] = None,
) -> Tuple[float, List[Dict]]:
    """Run ``allocate_one`` on every active deferrable, in the order
    given. Returns (total_rate_W_this_tick, per-deferrable diagnostic dicts).

    ``served_J_per_idx`` carries the per-day cumulative joules already
    dispatched per deferable index (from served_tracker). We subtract
    these from ``d.energy`` before scheduling — Azure publishes the
    original obligation at every tick rather than the remaining, so
    without this correction we'd massively over-serve (~5× across a
    60-tick window).

    Order matters: tightest deadline books first since it has the least
    scheduling flexibility.
    """
    served_J_per_idx = served_J_per_idx or {}
    booked: Dict[int, float] = {}
    total = 0.0
    detail = []

    # Build "adjusted" deferrables whose energy field reflects the true
    # remaining. allocate_one's only reads of ``d`` are index / window /
    # energy, so we can substitute a fresh Deferrable freely.
    active = []
    served_lookup: Dict[int, float] = {}
    original_lookup: Dict[int, float] = {}
    for d in deferrables:
        if not (d.tick_start <= current_tick <= d.tick_end):
            continue
        already   = max(0.0, served_J_per_idx.get(d.index, 0.0))
        remaining = max(0.0, d.energy - already)
        served_lookup[d.index]   = already
        original_lookup[d.index] = d.energy
        if remaining <= 1e-3:
            continue
        active.append(Deferrable(
            index      = d.index,
            tick_start = d.tick_start,
            tick_end   = d.tick_end,
            energy     = remaining,
        ))
    # Tightest deadline first.
    active.sort(key=lambda d: d.tick_end)

    for d in active:
        rate, bookings = allocate_one(d, current_tick, booked)
        total += rate
        # Pick out the marginal cost of the chosen schedule for diagnostics.
        scheduled_cost = 0.0
        for t, j in bookings:
            net = forecast.expected_net_W(t)
            price = (forecast.expected_buy_price(t)
                     if net > 0.5 else forecast.expected_sell_price(t))
            scheduled_cost += j * price
        detail.append({
            "index":             d.index,
            "tick_start":        d.tick_start,
            "tick_end":          d.tick_end,
            "ticks_remaining":   d.tick_end - current_tick + 1,
            "seconds_remaining": (d.tick_end - current_tick + 1) * SECONDS_PER_TICK,
            "remaining_energy":  d.energy,                       # already adjusted
            "served_J":          served_lookup.get(d.index, 0.0),
            "original_energy_J": original_lookup.get(d.index, d.energy),
            "rate_W":            rate,
            "scheduled_cost":    scheduled_cost,
            "bookings_count":    len(bookings),
        })

    return total, detail


# --- Sanity print: feed a couple of typical jobs through it ---
if __name__ == "__main__":  # pragma: no cover
    # Job 1 = always 50 J across full day; Job 3 = mid-day 30 J in [10, 40].
    deferrables = [
        Deferrable(index=0, tick_start=0,  tick_end=59, energy=50.0),
        Deferrable(index=2, tick_start=10, tick_end=40, energy=30.0),
    ]
    for tick in (0, 10, 20, 30, 40, 50):
        total, det = allocate_all(deferrables, tick)
        print(f"tick {tick:>2}: total_rate = {total:>5.2f} W")
        for d in det:
            print(f"   def#{d['index']}: rate={d['rate_W']:.2f} W  "
                  f"sched_cost={d['scheduled_cost']:>6.1f} ¢")
