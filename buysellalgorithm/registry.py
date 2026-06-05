"""Algorithm registry + persisted active-algorithm selection.

Each algorithm is a function ``decide(state: GridState) -> Commands``.
The registry exposes a small surface:

    list_all()        → [(id, name, description), ...]
    get(id)           → AlgorithmInfo or None
    get_active()      → AlgorithmInfo for the currently-active id
    set_active(id)    → persist id to disk so it survives restart
    active_id()       → currently-active id (cheap, no disk read)

Active id is mirrored to ``active_algo.json`` next to this file. On
first run that file is absent and the default (``naive``) is used.

Adding a new algorithm:
  1. Write ``my_algo.py`` exporting ``decide(state) -> Commands`` and
     module-level constants ``ALGO_ID``, ``ALGO_NAME``, ``ALGO_DESC``.
  2. Import it below in ``_bootstrap()`` and call ``register()``.
  3. Restart the backend. The frontend tabs auto-populate from
     ``/algo/list``.
"""

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional


@dataclass
class AlgorithmInfo:
    id:          str
    name:        str
    description: str
    decide_fn:   Callable     # GridState -> Commands


_REGISTRY:    Dict[str, AlgorithmInfo] = {}
_DEFAULT_ID = "naive"
_STATE_FILE = Path(__file__).resolve().parent / "active_algo.json"
_lock       = threading.Lock()

# Cached active id. Reloaded on every set_active(); reads use the cache.
_active_id: Optional[str] = None


def register(info: AlgorithmInfo) -> None:
    """Register an algorithm. Re-registering with the same id replaces it."""
    _REGISTRY[info.id] = info


def list_all() -> List[AlgorithmInfo]:
    return list(_REGISTRY.values())


def get(algo_id: str) -> Optional[AlgorithmInfo]:
    return _REGISTRY.get(algo_id)


def default_id() -> str:
    return _DEFAULT_ID


def _load_active_from_disk() -> str:
    if not _STATE_FILE.exists():
        return _DEFAULT_ID
    try:
        data = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
        aid  = data.get("id", _DEFAULT_ID)
        if aid in _REGISTRY:
            return aid
        return _DEFAULT_ID
    except (json.JSONDecodeError, OSError):
        return _DEFAULT_ID


def active_id() -> str:
    """Currently active algorithm id. Lazy-loads from disk on first call."""
    global _active_id
    with _lock:
        if _active_id is None:
            _active_id = _load_active_from_disk()
        return _active_id


def get_active() -> AlgorithmInfo:
    """Return the active AlgorithmInfo, falling back to the default if the
    persisted id is no longer registered."""
    aid = active_id()
    info = _REGISTRY.get(aid)
    if info is None:
        info = _REGISTRY.get(_DEFAULT_ID)
    return info


def set_active(algo_id: str) -> AlgorithmInfo:
    """Switch the active algorithm. Persists to disk so the choice
    survives backend restart. Raises ValueError if id is unknown."""
    global _active_id
    if algo_id not in _REGISTRY:
        raise ValueError(f"Unknown algorithm id: {algo_id}")
    with _lock:
        _active_id = algo_id
        try:
            _STATE_FILE.write_text(
                json.dumps({"id": algo_id}, indent=2), encoding="utf-8"
            )
        except OSError as exc:
            # Non-fatal — the in-memory cache still tracks the switch
            # for this process; it just won't survive a restart.
            print(f"[registry] warning: could not persist active id: {exc}")
    return _REGISTRY[algo_id]


def _bootstrap() -> None:
    """Import every algorithm module and register it. Imported lazily so
    the registry can be imported without triggering all of them (handy
    for unit tests)."""
    # naive baseline — keep id "naive" for back-compat with existing
    # /algo/naive endpoint and frontend code that reads it.
    from . import naive as _naive
    register(AlgorithmInfo(
        id          = "naive",
        name        = "Naive Baseline",
        description = (
            "Reactive symmetric-droop: cap absorbs/releases instantaneous "
            "imbalance, deferrables smeared linearly across remaining "
            "window. No forecast. This is the algorithm the brief asks "
            "the smart policy to beat."
        ),
        decide_fn   = _naive.decide,
    ))

    from . import smart_v1 as _smart_v1
    register(AlgorithmInfo(
        id          = _smart_v1.ALGO_ID,
        name        = _smart_v1.ALGO_NAME,
        description = _smart_v1.ALGO_DESC,
        decide_fn   = _smart_v1.decide,
    ))


_bootstrap()
