import csv
import io
import json
import os
import socket
import sys
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy import desc

from db import (SessionLocal, GridSnapshot, ModuleSnapshot, NaiveDecision,
                init_db, save_module_snapshot, save_naive_decision)

# Make sibling `buysellalgorithm/` importable.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
from buysellalgorithm.naive import (  # noqa: E402
    decide as naive_decide,
    state_from_db_rows as naive_state_from_db_rows,
    commands_to_payloads as naive_commands_to_payloads,
)

app = FastAPI()

MODULE_CMD_TIMEOUT = float(os.getenv("MODULE_CMD_TIMEOUT", "2"))
MODULE_CMD_TARGETS = {
    "pv": os.getenv("PICO_PV_URL", "http://192.168.137.24"),
    "grid": os.getenv("PICO_GRID_URL", "http://192.168.137.23"),
    "cap": os.getenv("PICO_CAP_URL", "http://192.168.137.21"),
    "led": os.getenv("PICO_LED_URL", "http://192.168.137.25"),
    "export": os.getenv("PICO_EXPORT_URL", "http://192.168.137.22"),
    "lux": os.getenv("PICO_LUX_URL", "http://192.168.137.26"),
}
MODULE_CMD_ROLES = tuple(MODULE_CMD_TARGETS.keys())


def _f(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _i(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _get_window_tick(item, primary, fallback):
    if primary in item:
        return item.get(primary)
    return item.get(fallback)


def _normalize_host(host):
    host = (host or "").strip()
    if not host:
        return ""
    if host.startswith("http://") or host.startswith("https://"):
        return host
    return "http://" + host


def _post_module_cmd(role, payload):
    host = _normalize_host(MODULE_CMD_TARGETS.get(role, ""))
    if not host:
        return {
            "ok": False,
            "status": "skipped",
            "reason": f"No host configured for role {role}",
        }

    parsed = urlparse(host)
    hostname = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = parsed.path.rstrip("/")
    if not path:
        path = "/cmd"
    elif not path.endswith("/cmd"):
        path += "/cmd"
    body = json.dumps(payload)
    req = (
        f"POST {path} HTTP/1.1\r\n"
        f"Host: {hostname}\r\n"
        "Accept: application/json\r\n"
        "Content-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n"
        "\r\n"
        f"{body}"
    ).encode("utf-8")

    try:
        print(f"[cmd proxy] send {role} -> {host}/cmd payload={payload}")
        with socket.create_connection((hostname, port), timeout=MODULE_CMD_TIMEOUT) as sock:
            sock.sendall(req)
            resp = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                resp += chunk

        resp_text = resp.decode(errors="replace")
        status_line = resp_text.splitlines()[0] if resp_text else ""
        parts = status_line.split(" ")
        status_code = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else 0
        body_start = resp_text.find("\r\n\r\n")
        response_body = resp_text[body_start + 4 :] if body_start >= 0 else ""
        print(f"[cmd proxy] result {role} -> {host}/cmd status={status_code} response={response_body[:200]!r}")

        return {
            "ok": 200 <= status_code < 300,
            "status": status_code,
            "url": host.rstrip("/") + "/cmd",
            "payload": payload,
            "response": response_body[:200],
        }
    except OSError as exc:
        print(f"[cmd proxy] error {role} -> {host}/cmd reason={exc}")
        return {
            "ok": False,
            "status": "error",
            "url": host.rstrip("/") + "/cmd",
            "payload": payload,
            "reason": str(exc),
        }


@app.get("/algo/module-hosts")
def get_module_hosts():
    return {
        "hosts": {role: MODULE_CMD_TARGETS.get(role, "") for role in MODULE_CMD_ROLES}
    }

@app.post("/modules/cmd/{role}")
def send_module_cmd(role: str, payload: dict):
    """Proxy a browser command through FastAPI to the module HTTP /cmd endpoint.

    This avoids browser CORS/preflight problems because the browser only calls
    FastAPI, while FastAPI talks to the Pico/ESP32 directly from the server side.
    """
    if role not in MODULE_CMD_TARGETS:
        raise HTTPException(status_code=404, detail=f"Unknown module role: {role}")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Command payload must be a JSON object")

    result = _post_module_cmd(role, payload)
    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=result)
    return result

@app.post("/modules/tlm/{role}")
def receive_module_tlm(role: str, payload: dict):
    """Receive pushed telemetry from a firmware module and persist it."""
    if role not in MODULE_CMD_TARGETS:
        raise HTTPException(status_code=404, detail=f"Unknown module role: {role}")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Telemetry payload must be a JSON object")

    if payload.get("role") != role:
        payload["role"] = role

    try:
        if not save_module_snapshot(payload):
            raise RuntimeError("Snapshot save skipped or duplicate")
        print(f"[tlm push] {role}: saved snapshot")
    except Exception as exc:
        print(f"[tlm push] {role}: error - {exc}")
        raise HTTPException(status_code=500, detail={"ok": False, "reason": str(exc)})

    return {"ok": True, "role": role}

@app.get("/modules/status")
def get_module_status():
    timeout_s = 6.0
    now = datetime.utcnow()

    db = SessionLocal()

    result = {}
    for role in ["pv", "grid", "export", "cap", "led", "lux"]:
        row = (
            db.query(ModuleSnapshot)
            .filter(ModuleSnapshot.role == role)
            .order_by(desc(ModuleSnapshot.id))
            .first()
        )

        if row is None:
            result[role] = {
                "online": False,
                "last_seen": None,
                "age_s": None,
            }
        else:
            age_s = (now - row.timestamp).total_seconds()
            result[role] = {
                "online": age_s <= timeout_s,
                "last_seen": row.timestamp.isoformat(),
                "age_s": round(age_s, 2),
            }

    db.close()
    return result


@app.post("/algo/module-hosts")
def set_module_hosts(payload: dict):
    updates = payload.get("hosts", payload) if isinstance(payload, dict) else {}
    if not isinstance(updates, dict):
        raise HTTPException(status_code=422, detail="hosts must be an object")

    unknown = [k for k in updates.keys() if k not in MODULE_CMD_TARGETS]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown roles: {', '.join(unknown)}")

    for role, host in updates.items():
        MODULE_CMD_TARGETS[role] = str(host or "").strip()

    return {
        "ok": True,
        "hosts": {role: MODULE_CMD_TARGETS.get(role, "") for role in MODULE_CMD_ROLES},
    }


def _run_naive_from_db(grid_row, module_rows):
    """Thin adapter: pulls rows → builds a GridState → calls naive.decide() →
    formats the response shape the frontend expects.

    All policy lives in buysellalgorithm/naive.py — keep it there.
    """
    if grid_row is None:
        return {"error": "No grid snapshot available"}

    pv_row  = module_rows.get("pv")
    cap_row = module_rows.get("cap")

    state = naive_state_from_db_rows(grid_row, pv_row, cap_row)
    if state is None:
        return {"error": "No grid snapshot available"}

    cmd = naive_decide(state)
    payloads = naive_commands_to_payloads(cmd)

    return {
        "tick":   state.tick,
        "regime": cmd.regime,
        "inputs": {
            "pv_power_W":       state.pv_p,
            "demand_W":         state.demand_p,
            "vbus_V":           state.vbus,
            "v_cap_V":          state.v_cap,
            "energy_cap_J":     state.energy_cap,
            "deferables_count": len(state.deferrables),
        },
        "suggested": {
            "cap":    payloads["cap"],
            "led":    payloads["led"],
            "grid":   payloads["grid"],
            "export": payloads["export"],
        },
        "served_deferrables":   cmd.served_deferrables,
        "remaining_surplus_W":  round(cmd.surplus_W, 4),
        "remaining_deficit_W":  round(cmd.deficit_W, 4),
    }


def start_smps_serial_ingest():
    port = os.getenv("SMPS_SERIAL_PORT")
    if not port:
        print("SMPS ingest disabled: set SMPS_SERIAL_PORT (example: COM5)")
        return

    baud = int(os.getenv("SMPS_SERIAL_BAUD", "115200"))

    def worker():
        try:
            import serial
        except ImportError:
            print("SMPS ingest disabled: pyserial not installed (pip install pyserial)")
            return

        while True:
            try:
                with serial.Serial(port, baud, timeout=1) as ser:
                    print("SMPS ingest listening on {} @ {}".format(port, baud))
                    while True:
                        raw = ser.readline()
                        if not raw:
                            continue
                        try:
                            line = raw.decode("utf-8").strip()
                        except UnicodeError:
                            continue
                        if not line or not line.startswith("{"):
                            continue
                        try:
                            payload = json.loads(line)
                            if "role" in payload:
                                save_module_snapshot(payload)
                            else:
                                print("SMPS ingest ignored: payload missing role")
                        except (ValueError, KeyError, TypeError):
                            continue
            except Exception as exc:
                print("SMPS ingest reconnecting after error: {}".format(exc))

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()


@app.on_event("startup")
def startup_event():
    init_db()
    start_smps_serial_ingest()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "Smart Grid Backend is running"}

@app.get("/snapshots")
def get_snapshots(limit: int = 50):
    db = SessionLocal()

    rows = (
        db.query(GridSnapshot)
        .order_by(desc(GridSnapshot.id))
        .limit(limit)
        .all()
    )

    db.close()

    return [
        {
            "id": row.id,
            "timestamp": row.timestamp.isoformat(),
            "tick": row.tick,
            "sun": row.sun,
            "buy_price": row.buy_price,
            "sell_price": row.sell_price,
            "instant_demand": row.instant_demand,
            "deferables": json.loads(str(row.deferables_json or "[]")),
        }
        for row in reversed(rows)
    ]

@app.get("/latest")
def get_latest():
    db = SessionLocal()

    row = (
        db.query(GridSnapshot)
        .order_by(desc(GridSnapshot.id))
        .first()
    )

    db.close()

    if row is None:
        return {"error": "No snapshots yet"}

    return {
        "id": row.id,
        "timestamp": row.timestamp.isoformat(),
        "tick": row.tick,
        "sun": row.sun,
        "buy_price": row.buy_price,
        "sell_price": row.sell_price,
        "instant_demand": row.instant_demand,
        "deferables": json.loads(str(row.deferables_json or "[]")),
    }


@app.post("/smps/ingest")
async def ingest_smps(payload: dict):
    try:
        if "role" in payload:
            save_module_snapshot(payload)
        else:
            raise KeyError("Missing role field")
    except (KeyError, TypeError) as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail=str(exc))
    return {"ok": True}


def _module_row_dict(row):
    return {
        "id":          row.id,
        "timestamp":   row.timestamp.isoformat(),
        "role":        row.role,
        "trip":        row.trip,
        "trip_reason": row.trip_reason,
        "enable":      row.enable,
        "wd":          row.wd,
        "pwm":         row.pwm,
        "vb_bus":      row.vb_bus,
        "iL":          row.iL,
        "i_ref":       row.i_ref,
        "vb_target":   row.vb_target,
        "v_panel":     row.v_panel,
        "p_panel":     row.p_panel,
        "vmpp_target": row.vmpp_target,
        "mppt_mode":   row.mppt_mode,
        "irradiance":  row.irradiance,
        "web_tick":    row.web_tick,
        "v_psu":       row.v_psu,
        "p_import":    row.p_import,
        "v_resistor":  row.v_resistor,
        "p_dissip":    row.p_dissip,
        "v_cap":       row.v_cap,
        "p_cap":       row.p_cap,
        "soc_pct":     row.soc_pct,
        "energy_J":    row.energy_J,
        "i_cmd":       row.i_cmd,
        "i_cmd_eff":   row.i_cmd_eff,
        "i_red":       row.i_red,
        "i_yel":       row.i_yel,
        "i_grn":       row.i_grn,
        "v_red":       row.v_red,
        "v_yel":       row.v_yel,
        "v_grn":       row.v_grn,
        "p_red":       row.p_red,
        "p_yel":       row.p_yel,
        "p_grn":       row.p_grn,
    }


@app.get("/modules/latest")
def get_all_modules_latest():
    db = SessionLocal()
    result = {}
    for role in ['pv', 'grid', 'export', 'cap', 'led']:
        row = (
            db.query(ModuleSnapshot)
            .filter(ModuleSnapshot.role == role)
            .order_by(desc(ModuleSnapshot.id))
            .first()
        )
        result[role] = _module_row_dict(row) if row else None
    db.close()
    return result


@app.get("/modules/latest/{role}")
def get_module_latest(role: str):
    db = SessionLocal()
    row = (
        db.query(ModuleSnapshot)
        .filter(ModuleSnapshot.role == role)
        .order_by(desc(ModuleSnapshot.id))
        .first()
    )
    db.close()
    if row is None:
        return {"error": f"No snapshots for role {role}"}
    return _module_row_dict(row)


@app.get("/modules/snapshots/{role}")
def get_module_snapshots(role: str, limit: int = 60):
    db = SessionLocal()
    rows = (
        db.query(ModuleSnapshot)
        .filter(ModuleSnapshot.role == role)
        .order_by(desc(ModuleSnapshot.id))
        .limit(limit)
        .all()
    )
    db.close()
    return [_module_row_dict(r) for r in reversed(rows)]


@app.get("/algo/naive")
def get_naive_recommendation():
    db = SessionLocal()

    try:
        grid_row = (
            db.query(GridSnapshot)
            .order_by(desc(GridSnapshot.id))
            .first()
        )

        module_rows = {}
        for role in ["pv", "cap"]:
            module_rows[role] = (
                db.query(ModuleSnapshot)
                .filter(ModuleSnapshot.role == role)
                .order_by(desc(ModuleSnapshot.id))
                .first()
            )

        return _run_naive_from_db(grid_row, module_rows)
    finally:
        db.close()


def _compute_and_apply_naive(db, log_decision=False):
    """Pull latest state, compute the naive recommendation, dispatch to all
    four actuators in parallel, optionally log the decision to the DB.

    Returns a dict with keys: ok, recommendation, applied. If there is no
    grid snapshot yet, returns {"error": ...}.

    Note: grid + export are ALWAYS enabled (passive symmetric-droop safety
    net). The naive only varies cap.i_cmd and LED setpoints; grid/export
    flow current only when cap saturates and the bus leaves the 9.9–10.1 V
    deadband.
    """
    grid_row = (
        db.query(GridSnapshot)
        .order_by(desc(GridSnapshot.id))
        .first()
    )

    module_rows = {}
    for role in ["pv", "cap"]:
        module_rows[role] = (
            db.query(ModuleSnapshot)
            .filter(ModuleSnapshot.role == role)
            .order_by(desc(ModuleSnapshot.id))
            .first()
        )

    recommendation = _run_naive_from_db(grid_row, module_rows)
    if "error" in recommendation:
        return {"error": recommendation["error"]}

    suggested = recommendation.get("suggested", {}) or {}
    targets = {}
    for role in ("cap", "led", "grid", "export"):
        payload = suggested.get(role, {})
        targets[role] = payload if isinstance(payload, dict) else {}

    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {
            role: ex.submit(_post_module_cmd, role, payload)
            for role, payload in targets.items()
        }
        applied = {role: fut.result() for role, fut in futures.items()}

    all_ok = all(bool(r.get("ok")) for r in applied.values())

    if log_decision:
        try:
            save_naive_decision({
                "tick":           recommendation.get("tick"),
                "regime":         recommendation.get("regime"),
                "all_ok":         all_ok,
                "inputs":         recommendation.get("inputs", {}),
                "recommendation": recommendation,
                "applied":        applied,
            })
        except Exception as exc:
            print(f"[naive] decision log failed: {exc}")

    return {
        "ok":             all_ok,
        "recommendation": recommendation,
        "applied":        applied,
    }


@app.post("/algo/naive/apply")
def apply_naive_recommendation():
    db = SessionLocal()
    try:
        result = _compute_and_apply_naive(db, log_decision=True)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    finally:
        db.close()


# ============================================================
# Phase 4: Naive auto-loop
# ============================================================
# Background worker that re-runs the naive policy on every new Azure tick
# and dispatches commands to the four actuators. Watches /modules/status
# style health (snapshot freshness, module trips) and skips the apply when
# anything looks wrong, so a single bad tick doesn't push unsafe setpoints.

_AUTO_POLL_S  = float(os.getenv("AUTO_NAIVE_POLL_S",  "1.0"))
_AUTO_STALE_S = float(os.getenv("AUTO_NAIVE_STALE_S", "15.0"))

_auto_lock       = threading.Lock()
_auto_stop_event = threading.Event()
_auto_thread     = None
_auto_state = {
    "running":           False,
    "started_at":        None,
    "stopped_at":        None,
    "last_tick_applied": None,
    "last_action_at":    None,
    "last_regime":       None,
    "last_result":       None,    # short summary dict of last iteration
    "last_error":        None,
    "applied_count":     0,
    "skipped_count":     0,
    "poll_s":            _AUTO_POLL_S,
    "stale_s":           _AUTO_STALE_S,
}


def _auto_loop_iteration():
    """One iteration of the auto-loop. Returns a small dict describing
    what happened ({action: applied|skipped, reason: ..., ...})."""
    db = SessionLocal()
    try:
        grid_row = (
            db.query(GridSnapshot)
            .order_by(desc(GridSnapshot.id))
            .first()
        )
        if grid_row is None:
            return {"action": "skipped", "reason": "no_grid_snapshot"}

        # Skip if we've already applied this tick.
        with _auto_lock:
            last_applied = _auto_state["last_tick_applied"]
        if last_applied == grid_row.tick:
            return {"action": "skipped", "reason": "tick_already_applied",
                    "tick": grid_row.tick}

        # Skip if the grid snapshot is too old (poller stalled / Azure down).
        age_s = (datetime.utcnow() - grid_row.timestamp).total_seconds()
        if age_s > _AUTO_STALE_S:
            return {"action": "skipped", "reason": "snapshot_stale",
                    "age_s": round(age_s, 2)}

        # Skip if any actuator module is currently tripped.
        for role in ("cap", "led", "grid", "export"):
            row = (
                db.query(ModuleSnapshot)
                .filter(ModuleSnapshot.role == role)
                .order_by(desc(ModuleSnapshot.id))
                .first()
            )
            if row is not None and row.trip:
                return {"action": "skipped", "reason": f"{role}_tripped",
                        "trip_reason": row.trip_reason}

        # Compute + apply + log.
        result = _compute_and_apply_naive(db, log_decision=True)
        if "error" in result:
            return {"action": "skipped", "reason": result["error"]}

        rec = result.get("recommendation", {}) or {}
        return {
            "action":  "applied",
            "tick":    rec.get("tick"),
            "regime":  rec.get("regime"),
            "all_ok":  result.get("ok"),
            "inputs":  rec.get("inputs", {}),
        }
    finally:
        db.close()


def _auto_loop_worker():
    """Long-running thread body. Polls every _AUTO_POLL_S seconds, calls
    one iteration, updates the published _auto_state, and sleeps."""
    while not _auto_stop_event.is_set():
        try:
            result = _auto_loop_iteration()
            with _auto_lock:
                _auto_state["last_action_at"] = datetime.utcnow().isoformat()
                _auto_state["last_result"]    = result
                if result.get("action") == "applied":
                    _auto_state["applied_count"]    += 1
                    _auto_state["last_tick_applied"] = result.get("tick")
                    _auto_state["last_regime"]       = result.get("regime")
                    _auto_state["last_error"]        = None
                else:
                    _auto_state["skipped_count"] += 1
        except Exception as exc:
            with _auto_lock:
                _auto_state["last_error"] = str(exc)
            print(f"[naive auto] iteration error: {exc}")
        # Use Event.wait so /algo/auto/stop returns quickly.
        _auto_stop_event.wait(_AUTO_POLL_S)


@app.post("/algo/auto/start")
def auto_naive_start():
    global _auto_thread
    with _auto_lock:
        if _auto_state["running"]:
            return {"ok": True, "already_running": True,
                    "state": dict(_auto_state)}
        _auto_stop_event.clear()
        _auto_state["running"]       = True
        _auto_state["started_at"]    = datetime.utcnow().isoformat()
        _auto_state["stopped_at"]    = None
        _auto_state["applied_count"] = 0
        _auto_state["skipped_count"] = 0
        _auto_state["last_error"]    = None

    _auto_thread = threading.Thread(
        target=_auto_loop_worker, name="naive-auto-loop", daemon=True
    )
    _auto_thread.start()
    return {"ok": True, "state": dict(_auto_state)}


@app.post("/algo/auto/stop")
def auto_naive_stop():
    with _auto_lock:
        if not _auto_state["running"]:
            return {"ok": True, "already_stopped": True,
                    "state": dict(_auto_state)}
        _auto_stop_event.set()
        _auto_state["running"]    = False
        _auto_state["stopped_at"] = datetime.utcnow().isoformat()
    return {"ok": True, "state": dict(_auto_state)}


@app.get("/algo/auto/status")
def auto_naive_status():
    with _auto_lock:
        return dict(_auto_state)


# ============================================================
# Phase 5: Full-day data export
# ============================================================
# Dumps every table (grid snapshots, module snapshots, naive decisions)
# for the requested time range. Two formats:
#   format=json (default) — single JSON document, good for programmatic use
#   format=csv            — zip of three CSVs, good for opening in Excel
#
# Range can be specified with ?since=<ISO> and ?until=<ISO>, or with
# ?last_hours=N (overrides since/until). Default: everything.

def _grid_row_to_dict(row):
    return {
        "id":             row.id,
        "timestamp":      row.timestamp.isoformat(),
        "day":            row.day,
        "tick":           row.tick,
        "sun":            row.sun,
        "buy_price":      row.buy_price,
        "sell_price":     row.sell_price,
        "instant_demand": row.instant_demand,
        "deferables":     json.loads(str(row.deferables_json or "[]")),
    }


def _decision_row_to_dict(row):
    return {
        "id":             row.id,
        "timestamp":      row.timestamp.isoformat(),
        "tick":           row.tick,
        "regime":         row.regime,
        "all_ok":         bool(row.all_ok),
        "inputs":         json.loads(str(row.inputs_json or "{}")),
        "recommendation": json.loads(str(row.recommendation_json or "{}")),
        "applied":        json.loads(str(row.applied_json or "{}")),
    }


def _parse_iso(s):
    if not s:
        return None
    try:
        # Accept both "Z" and offset-less ISO strings.
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail=f"Bad ISO timestamp: {s!r}")


def _query_export(db, since=None, until=None, last_hours=None):
    if last_hours is not None and last_hours > 0:
        since = datetime.utcnow().timestamp() - (float(last_hours) * 3600.0)
        since = datetime.utcfromtimestamp(since)
        until = None
    else:
        since = _parse_iso(since)
        until = _parse_iso(until)

    g_q = db.query(GridSnapshot)
    m_q = db.query(ModuleSnapshot)
    d_q = db.query(NaiveDecision)
    if since is not None:
        g_q = g_q.filter(GridSnapshot.timestamp   >= since)
        m_q = m_q.filter(ModuleSnapshot.timestamp >= since)
        d_q = d_q.filter(NaiveDecision.timestamp  >= since)
    if until is not None:
        g_q = g_q.filter(GridSnapshot.timestamp   <= until)
        m_q = m_q.filter(ModuleSnapshot.timestamp <= until)
        d_q = d_q.filter(NaiveDecision.timestamp  <= until)

    return (
        g_q.order_by(GridSnapshot.id).all(),
        m_q.order_by(ModuleSnapshot.id).all(),
        d_q.order_by(NaiveDecision.id).all(),
        since,
        until,
    )


@app.get("/export/full")
def export_full(format: str = "json",
                since: str = None,
                until: str = None,
                last_hours: float = None):
    db = SessionLocal()
    try:
        grid_rows, mod_rows, dec_rows, since_dt, until_dt = _query_export(
            db, since=since, until=until, last_hours=last_hours
        )

        meta = {
            "exported_at":      datetime.utcnow().isoformat(),
            "since":            since_dt.isoformat() if since_dt else None,
            "until":            until_dt.isoformat() if until_dt else None,
            "grid_count":       len(grid_rows),
            "module_count":     len(mod_rows),
            "decision_count":   len(dec_rows),
        }

        if format == "csv":
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                # Grid snapshots
                s = io.StringIO()
                w = csv.writer(s)
                w.writerow(["id", "timestamp", "day", "tick", "sun",
                            "buy_price", "sell_price", "instant_demand",
                            "deferables_json"])
                for r in grid_rows:
                    w.writerow([r.id, r.timestamp.isoformat(), r.day, r.tick,
                                r.sun, r.buy_price, r.sell_price,
                                r.instant_demand, r.deferables_json])
                zf.writestr("grid_snapshots.csv", s.getvalue())

                # Module snapshots (all columns, one row per snapshot)
                s = io.StringIO()
                w = csv.writer(s)
                cols = [c.name for c in ModuleSnapshot.__table__.columns]
                w.writerow(cols)
                for r in mod_rows:
                    row_vals = []
                    for c in cols:
                        v = getattr(r, c)
                        if isinstance(v, datetime):
                            v = v.isoformat()
                        row_vals.append(v)
                    w.writerow(row_vals)
                zf.writestr("module_snapshots.csv", s.getvalue())

                # Naive decisions
                s = io.StringIO()
                w = csv.writer(s)
                w.writerow(["id", "timestamp", "tick", "regime", "all_ok",
                            "inputs_json", "recommendation_json",
                            "applied_json"])
                for r in dec_rows:
                    w.writerow([r.id, r.timestamp.isoformat(), r.tick,
                                r.regime, r.all_ok,
                                r.inputs_json, r.recommendation_json,
                                r.applied_json])
                zf.writestr("naive_decisions.csv", s.getvalue())

                # Manifest so future-you knows what generated this zip
                zf.writestr("manifest.json", json.dumps(meta, indent=2))

            buf.seek(0)
            ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
            return Response(
                content=buf.read(),
                media_type="application/zip",
                headers={
                    "Content-Disposition":
                        f'attachment; filename="smartgrid-export-{ts}.zip"'
                },
            )

        # JSON format
        return {
            **meta,
            "grid_snapshots":   [_grid_row_to_dict(r)     for r in grid_rows],
            "module_snapshots": [_module_row_dict(r)      for r in mod_rows],
            "naive_decisions":  [_decision_row_to_dict(r) for r in dec_rows],
        }
    finally:
        db.close()


@app.get("/export/summary")
def export_summary():
    """Lightweight counts + earliest/latest timestamps. Useful before
    triggering a heavy /export/full call."""
    db = SessionLocal()
    try:
        def first_last(q, col):
            first = q.order_by(col.asc()).first()
            last  = q.order_by(col.desc()).first()
            return (
                first.timestamp.isoformat() if first else None,
                last.timestamp.isoformat()  if last  else None,
            )

        grid_first, grid_last = first_last(db.query(GridSnapshot),   GridSnapshot.timestamp)
        mod_first,  mod_last  = first_last(db.query(ModuleSnapshot), ModuleSnapshot.timestamp)
        dec_first,  dec_last  = first_last(db.query(NaiveDecision),  NaiveDecision.timestamp)

        return {
            "grid_snapshots":   {"count": db.query(GridSnapshot).count(),
                                 "first": grid_first, "last": grid_last},
            "module_snapshots": {"count": db.query(ModuleSnapshot).count(),
                                 "first": mod_first,  "last": mod_last},
            "naive_decisions":  {"count": db.query(NaiveDecision).count(),
                                 "first": dec_first,  "last": dec_last},
        }
    finally:
        db.close()


