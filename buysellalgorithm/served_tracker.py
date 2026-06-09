"""Per-deferrable served-J accumulator for the live PMS path.

Azure (and the fixed-data shim) republishes the ORIGINAL deferrable
energies every tick — they do NOT decrement as energy is served. Without
this tracker the algorithm sees "full energy still pending" every tick
and re-allocates the same joules repeatedly, over-driving the LED by
~200 J/day in a 60-tick window.

The backtest harness (backtest/harness.py) solves this internally with a
local ``served_J`` dict. This module is the live-path equivalent so the
poll/apply loop in ``backend/main.py`` gets the same correction.

Usage (in the live decide path):

    from buysellalgorithm import served_tracker

    state.deferrables = served_tracker.current_remaining(
        state.deferrables, state.tick
    )
    cmd = active.decide_fn(state)
    # ...dispatch to actuators...
    served_tracker.commit(cmd.active_deferrables, state.tick)

Commit is idempotent within a tick — repeated reads (frontend polling
/algo/naive) don't pollute state because the increment only fires once
per (tick, day-signature) pair.
"""

import threading
from typing import List, Optional, Tuple

SECONDS_PER_TICK = 5.0


_lock = threading.Lock()
_served_J: dict = {}          # index -> cumulative J served on the current day
_last_tick: Optional[int] = None
_day_sig: Optional[Tuple] = None
_tick_committed: bool = False


def _signature(deferrables) -> Tuple:
    """A signature that changes when the deferrable set rolls over.
    Uses (index, start, end, energy-from-Azure) — since Azure never
    decrements energy, that tuple is stable within a day and unique
    across days with overwhelming probability."""
    return tuple(
        (d.index, d.tick_start, d.tick_end, round(float(d.energy), 4))
        for d in deferrables
    )


def current_remaining(deferrables, current_tick: int) -> List:
    """Return deferrables with energy reduced by what's been served so
    far on this day. Detects day rollover (tick wrap backward, or
    deferrable-set change) and zeroes the tracker before subtracting."""
    # Local import — naive.py and this module are mutually visible only
    # via the package, and the live caller path is poller→main→here→naive.
    from .naive import Deferrable

    global _served_J, _last_tick, _day_sig, _tick_committed

    with _lock:
        sig = _signature(deferrables)
        rollover = False
        if _last_tick is not None and current_tick < _last_tick:
            rollover = True
        if _day_sig is not None and _day_sig != sig:
            rollover = True
        if rollover:
            _served_J = {}
            _tick_committed = False
        _day_sig = sig
        if _last_tick != current_tick:
            _tick_committed = False
        served = dict(_served_J)

    return [
        Deferrable(
            index      = d.index,
            tick_start = d.tick_start,
            tick_end   = d.tick_end,
            energy     = max(0.0, float(d.energy) - served.get(d.index, 0.0)),
        )
        for d in deferrables
    ]


def commit(active_deferrables_diag, current_tick: int) -> None:
    """Accumulate served energy after a successful dispatch. Idempotent
    within a tick: repeated calls for the same tick are no-ops, so the
    read path (/algo/naive) can call decide() many times without
    polluting state.

    ``active_deferrables_diag`` is ``cmd.active_deferrables`` — a list
    of dicts each carrying ``index`` and ``rate_W`` (bus-side W
    commanded for this tick)."""
    global _served_J, _last_tick, _tick_committed

    with _lock:
        if _tick_committed and _last_tick == current_tick:
            return
        for d in active_deferrables_diag or []:
            try:
                idx = int(d.get("index"))
                rate_W = float(d.get("rate_W", 0.0))
            except (TypeError, ValueError):
                continue
            _served_J[idx] = _served_J.get(idx, 0.0) + rate_W * SECONDS_PER_TICK
        _last_tick = current_tick
        _tick_committed = True


def reset() -> None:
    """Explicit reset — for tests, or when an operator forces a day change."""
    global _served_J, _last_tick, _day_sig, _tick_committed
    with _lock:
        _served_J = {}
        _last_tick = None
        _day_sig = None
        _tick_committed = False


def snapshot() -> dict:
    """Read-only copy of current state (for diagnostics)."""
    with _lock:
        return {
            "served_J":  dict(_served_J),
            "last_tick": _last_tick,
            "day_sig":   _day_sig,
        }
