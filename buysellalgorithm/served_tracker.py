"""Per-day cumulative deferrable energy served, kept in-memory.

Azure's /deferables endpoint publishes each deferrable's ORIGINAL
``energy`` obligation at every tick — it does NOT decrease as we serve
the deferrable. The docstring in ``naive._active_deferrable_rates``
(written before this was empirically tested) assumed the opposite, so
both the naive baseline and Smart V1 over-dispatch:

    rate = d.energy / seconds_remaining

If ``d.energy`` never decreases, the dispatched energy over the full
window equals  d.energy × harmonic(N)  for an N-tick window. For the
typical 60-tick deferrable that's ~5× over-service. Verified against the
2026-06-05 run: a 50 J obligation produced ~234 J of LED dispatch.

This module fixes that by tracking each deferrable's cumulative dispatch
ourselves, and exposing a snapshot the decide() functions subtract from
``d.energy`` before computing the per-tick rate.

State scope:
  - In-memory only. Restart resets it. Multi-day auto-loop runs are
    self-cleaning because ``reset_day_if_changed`` is called every tick
    and purges previous days on rollover.
  - Keyed by (Azure day, deferable index). Index is the position in the
    /deferables JSON array — stable within a day, reset between days.
"""

import threading
from typing import Dict, Tuple


_lock:        threading.Lock = threading.Lock()
_served:      Dict[Tuple[int, int], float] = {}
_current_day: int = -1


def reset_day_if_changed(day: int) -> None:
    """Drop every entry from previous days when the Azure day rolls over.
    Cheap to call every tick — only does work on rollover."""
    global _current_day
    if day == _current_day:
        return
    with _lock:
        if day == _current_day:
            return
        _served.clear()
        _current_day = day


def note_dispatch(day: int, def_index: int, joules: float) -> None:
    """Credit ``joules`` of additional service to (day, def_index)."""
    if joules <= 0:
        return
    with _lock:
        key = (day, def_index)
        _served[key] = _served.get(key, 0.0) + joules


def served_for_day(day: int) -> Dict[int, float]:
    """Snapshot of {def_index: cumulative_served_J} for the given day."""
    with _lock:
        return {idx: j for (d, idx), j in _served.items() if d == day}


def reset_all() -> None:
    """Test-only: clear all state."""
    global _current_day
    with _lock:
        _served.clear()
        _current_day = -1
