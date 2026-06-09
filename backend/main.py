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
    state_from_db_rows as algo_state_from_db_rows,
    commands_to_payloads as algo_commands_to_payloads,
    commands_to_diagnostics as algo_commands_to_diagnostics,
)
from buysellalgorithm import registry as algo_registry  # noqa: E402
from buysellalgorithm import served_tracker as algo_served_tracker  # noqa: E402

app = FastAPI()

MODULE_CMD_TIMEOUT = float(os.getenv("MODULE_CMD_TIMEOUT", "2"))
POLLER_CONTROL_PATH = Path(__file__).resolve().parent / "poller_control.json"
POLLER_STATUS_PATH = Path(__file__).resolve().parent / "poller_status.json"
_poller_control_lock = threading.Lock()
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
    command_started_ns = time.time_ns()
    host = _normalize_host(MODULE_CMD_TARGETS.get(role, ""))
    if not host:
        return {
            "ok": False,
            "status": "skipped",
            "reason": f"No host configured for role {role}",
            "command_started_ns": command_started_ns,
            "command_finished_ns": time.time_ns(),
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
            "command_started_ns": command_started_ns,
            "command_finished_ns": time.time_ns(),
        }
    except OSError as exc:
        print(f"[cmd proxy] error {role} -> {host}/cmd reason={exc}")
        return {
            "ok": False,
            "status": "error",
            "url": host.rstrip("/") + "/cmd",
            "payload": payload,
            "reason": str(exc),
            "command_started_ns": command_started_ns,
            "command_finished_ns": time.time_ns(),
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
    payload["backend_tlm_received_ns"] = time.time_ns()

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
    """Thin adapter: pulls rows → builds a GridState → calls the
    currently-active algorithm's decide() → formats the response shape
    the frontend expects.

    Algorithm lookup goes through ``buysellalgorithm.registry`` so the
    operator can switch between Naive Baseline and Smart V1 (and future
    algos) at runtime via the /algo/active endpoint.

    The function name stays ``_run_naive_from_db`` for historical
    reasons; nothing about it is naive-specific any more.
    """
    if grid_row is None:
        return {"error": "No grid snapshot available"}

    pv_row  = module_rows.get("pv")
    cap_row = module_rows.get("cap")

    state = algo_state_from_db_rows(grid_row, pv_row, cap_row)
    if state is None:
        return {"error": "No grid snapshot available"}

    # Azure republishes the ORIGINAL deferrable energies every tick; the
    # algorithm needs *remaining* joules or it will re-allocate the same
    # energy every tick (LED over-driven by ~200 J/day). Mirror the
    # served_J accounting that the backtest harness does internally.
    state.deferrables = algo_served_tracker.current_remaining(
        state.deferrables, state.tick
    )

    active   = algo_registry.get_active()
    cmd      = active.decide_fn(state)
    # Ensure the algo_id is stamped even if the algo forgot to set it.
    if not getattr(cmd, "algo_id", None) or cmd.algo_id == "naive":
        cmd.algo_id = active.id
    payloads = algo_commands_to_payloads(cmd)
    diag     = algo_commands_to_diagnostics(cmd)

    return {
        "tick":     state.tick,
        "regime":   cmd.regime,
        "algo_id":  active.id,
        "algo_name": active.name,
        # Raw inputs that fed the decision (so the dashboard can show what
        # the algo was looking at this tick).
        "inputs": {
            "pv_power_W":       state.pv_p,        # PANEL side, pre-loss
            "demand_W":         state.demand_p,
            "vbus_V":           state.vbus,
            "v_cap_V":          state.v_cap,
            "energy_cap_J":     state.energy_cap,
            "deferables_count": len(state.deferrables),
        },
        # Per-module setpoints we'll dispatch.
        "suggested": {
            "cap":    payloads["cap"],
            "led":    payloads["led"],
            "grid":   payloads["grid"],
            "export": payloads["export"],
        },
        # Full bus-side energy accounting for the debug panel. Stable
        # shape — see buysellalgorithm/naive.py::commands_to_diagnostics.
        "diagnostics": diag,
        # Back-compat fields the frontend already reads.
        "remaining_surplus_W":  diag["surplus_W"],
        "remaining_deficit_W":  diag["deficit_W"],
        # Kept for back-compat with the old EDF "served" key. Now empty
        # because deferrables are smoothed across the window, not served
        # greedily. Use diagnostics.active_deferrables instead.
        "served_deferrables":   [],
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


def _read_json_file(path, default):
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def _write_json_file(path, payload):
    temp_path = path.with_suffix(".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    temp_path.replace(path)


def _next_fixed_run_day():
    db = SessionLocal()
    try:
        row = (
            db.query(GridSnapshot.day)
            .filter(GridSnapshot.day >= 1, GridSnapshot.day < 1_000_000)
            .order_by(desc(GridSnapshot.day))
            .first()
        )
        highest_day = 0 if row is None else int(row[0])
        control = _read_json_file(POLLER_CONTROL_PATH, {})
        reserved_day = _i(control.get("run_day"), 0)
        if control.get("mode") == "fixed" and 1 <= reserved_day < 1_000_000:
            highest_day = max(highest_day, reserved_day)

        next_day = highest_day + 1
        if next_day >= 1_000_000:
            raise HTTPException(
                status_code=409,
                detail="Fixed run day range 1..999999 is exhausted",
            )
        return next_day
    finally:
        db.close()


@app.get("/poller/source")
def get_poller_source():
    control = _read_json_file(
        POLLER_CONTROL_PATH,
        {"mode": "azure", "generation": "default", "run_day": None},
    )
    status = _read_json_file(POLLER_STATUS_PATH, {})
    if str(status.get("generation")) != str(control.get("generation")):
        status = {}
    return {**control, "status": status}


@app.post("/poller/source")
def set_poller_source(payload: dict):
    mode = str(payload.get("mode", "")).lower()
    if mode not in {"azure", "fixed"}:
        raise HTTPException(status_code=422, detail="mode must be azure or fixed")

    with _poller_control_lock:
        generation = str(time.time_ns())
        control = {
            "mode": mode,
            "generation": generation,
            "run_day": _next_fixed_run_day() if mode == "fixed" else None,
            "requested_at": datetime.utcnow().isoformat(),
        }
        _write_json_file(POLLER_CONTROL_PATH, control)
    return {"ok": True, **control, "status": {}}


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
        "trace_id":     row.trace_id,
        "trace_tick":   row.trace_tick,
        "fw_cmd_received_ms": row.fw_cmd_received_ms,
        "fw_cmd_applied_ms": row.fw_cmd_applied_ms,
        "fw_cmd_to_apply_ms": row.fw_cmd_to_apply_ms,
        "backend_tlm_received_ns": row.backend_tlm_received_ns,
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


@app.get("/algo/list")
def list_algorithms():
    """Return every registered algorithm with the currently-active flag.

    Frontend uses this to populate the algorithm tab strip. Stable shape:
        {
          "active": "<id>",
          "algorithms": [
            {"id": "naive", "name": "Naive Baseline", "description": "...",
             "active": true|false},
            ...
          ]
        }
    """
    aid = algo_registry.active_id()
    return {
        "active": aid,
        "algorithms": [
            {
                "id":          a.id,
                "name":        a.name,
                "description": a.description,
                "active":      a.id == aid,
            }
            for a in algo_registry.list_all()
        ],
    }


@app.get("/algo/active")
def get_active_algorithm():
    a = algo_registry.get_active()
    return {
        "id":          a.id,
        "name":        a.name,
        "description": a.description,
    }


@app.post("/algo/active")
def set_active_algorithm(payload: dict):
    """Switch the active algorithm. Takes effect immediately — the next
    /algo/naive or auto-loop tick uses the new policy.

    Payload: {"id": "<algo_id>"}
    """
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="payload must be a JSON object")
    algo_id = payload.get("id")
    if not algo_id or not isinstance(algo_id, str):
        raise HTTPException(status_code=422, detail="missing 'id' field")
    try:
        info = algo_registry.set_active(algo_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {
        "ok":          True,
        "active":      info.id,
        "name":        info.name,
        "description": info.description,
    }


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
    decision_started_ns = time.time_ns()
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

    decision_finished_ns = time.time_ns()
    trace_id = (
        f"{grid_row.day}:{grid_row.tick}:{grid_row.id}:{decision_started_ns}"
    )
    trace = {
        "trace_id": trace_id,
        "day": grid_row.day,
        "tick": grid_row.tick,
        "source_fetch_started_ns": grid_row.source_fetch_started_ns,
        "source_fetch_received_ns": grid_row.source_fetch_received_ns,
        "grid_saved_at": grid_row.timestamp.isoformat(),
        "decision_started_ns": decision_started_ns,
        "decision_finished_ns": decision_finished_ns,
    }
    recommendation["latency_trace"] = trace

    suggested = recommendation.get("suggested", {}) or {}
    targets = {}
    for role in ("cap", "led", "grid", "export"):
        payload = suggested.get(role, {})
        payload = dict(payload) if isinstance(payload, dict) else {}
        payload["_trace_id"] = trace_id
        payload["_trace_tick"] = grid_row.tick
        targets[role] = payload

    trace["dispatch_started_ns"] = time.time_ns()
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {
            role: ex.submit(_post_module_cmd, role, payload)
            for role, payload in targets.items()
        }
        applied = {role: fut.result() for role, fut in futures.items()}
    trace["dispatch_finished_ns"] = time.time_ns()

    all_ok = all(bool(r.get("ok")) for r in applied.values())

    # Only the LED actually consumes the deferrable energy. Credit the
    # served-J tracker only when its dispatch succeeded — otherwise the
    # next tick will see (correctly) that the obligation is still open.
    # Commit is idempotent per (tick, day-sig), so read-path calls to
    # /algo/naive don't double-count.
    if applied.get("led", {}).get("ok"):
        try:
            diag = recommendation.get("diagnostics", {}) or {}
            algo_served_tracker.commit(
                diag.get("active_deferrables", []) or [],
                recommendation.get("tick"),
            )
        except Exception as exc:
            print(f"[served_tracker] commit failed: {exc}")

    if log_decision:
        try:
            save_naive_decision({
                "tick":           recommendation.get("tick"),
                "regime":         recommendation.get("regime"),
                "algo_id":        recommendation.get("algo_id"),
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


_SAFE_DEFAULTS = {
    # Cap: idle (no commanded current — let the cap sit at whatever V it's at).
    "cap":    {"enable": 1, "i_cmd": 0.0},
    # LED: all channels off (no dissipation, so the bus doesn't get drained
    # by a stale setpoint after the algo stops).
    "led":    {"enable": 1, "p_red": 0.0, "p_yel": 0.0, "p_grn": 0.0},
    # Grid + Export: passive droop targets. These are what the algorithm
    # would normally hold them at anyway, but explicitly re-sending on
    # stop makes the post-stop state deterministic.
    "grid":   {"enable": 1, "vb_target": 9.9,  "i_ref_max": 2.0},
    "export": {"enable": 1, "vb_target": 10.1, "i_ref_max": 2.0},
}


@app.post("/algo/auto/stop")
def auto_naive_stop():
    """Stop the auto-loop AND broadcast safe-default commands to every
    actuator. Without this, the watchdog being disabled in the firmware
    (firmware/*/common.py: ``def watchdog_tripped: return False``) means
    each module keeps executing whatever was last commanded —
    typically a non-zero cap.i_cmd that slowly discharges or charges
    the supercap out of its operating window, eventually tripping on
    overcurrent / bus_collapse / cap_overvolt and requiring a manual
    reset_trip (which used to itself trip the PSU — see the firmware
    _reset_controllers() fix).

    Safe defaults:
      cap.i_cmd = 0    → cap idles
      led.p_*   = 0    → no dissipation
      grid/export      → droop targets (what they're at anyway)
    """
    was_running = False
    with _auto_lock:
        if _auto_state["running"]:
            was_running = True
            _auto_stop_event.set()
            _auto_state["running"]    = False
            _auto_state["stopped_at"] = datetime.utcnow().isoformat()

    # Push safe defaults regardless of prior run state — pressing Stop
    # twice should still be a clean "everything to safe defaults", not
    # a no-op.
    safe_applied = _dispatch_module_cmds(_SAFE_DEFAULTS)
    safe_ok = all(bool(r.get("ok")) for r in safe_applied.values())

    return {
        "ok":               True,
        "was_running":      was_running,
        "safe_defaults_ok": safe_ok,
        "safe_applied":     safe_applied,
        "state":            dict(_auto_state),
    }


@app.get("/algo/auto/status")
def auto_naive_status():
    with _auto_lock:
        return dict(_auto_state)


def _elapsed_ms(end_ns, start_ns):
    if end_ns is None or start_ns is None:
        return None
    return round((int(end_ns) - int(start_ns)) / 1_000_000.0, 3)


@app.get("/latency/latest")
def latest_end_to_end_latency():
    """Return the newest Azure-to-cap-telemetry latency breakdown."""
    db = SessionLocal()
    try:
        recommendation = {}
        applied = {}
        for row in (
            db.query(NaiveDecision)
            .order_by(desc(NaiveDecision.id))
            .limit(100)
            .all()
        ):
            candidate = json.loads(str(row.recommendation_json or "{}"))
            if candidate.get("latency_trace", {}).get("trace_id"):
                recommendation = candidate
                applied = json.loads(str(row.applied_json or "{}"))
                break

        if not recommendation:
            raise HTTPException(
                status_code=404,
                detail=(
                    "No traced decision yet. Check /algo/auto/status; the "
                    "auto loop may be waiting for a new tick or skipping a "
                    "tripped module."
                ),
            )

        trace = recommendation["latency_trace"]
        trace_id = trace["trace_id"]
        cap_apply = applied.get("cap", {}) or {}
        cap_payload = cap_apply.get("payload", {}) or {}
        requested_i = _f(cap_payload.get("i_cmd"))
        cap_rows = (
            db.query(ModuleSnapshot)
            .filter(
                ModuleSnapshot.role == "cap",
                ModuleSnapshot.trace_id == trace_id,
            )
            .order_by(ModuleSnapshot.id)
            .limit(30)
            .all()
        )

        def row_confirmation(row):
            command_reflected = (
                row.i_cmd is not None
                and abs(float(row.i_cmd) - requested_i) <= 0.001
            )
            if abs(requested_i) <= 0.01:
                physical_response = (
                    row.i_cmd_eff is not None
                    and row.iL is not None
                    and abs(float(row.i_cmd_eff)) <= 0.03
                    and abs(float(row.iL)) <= 0.05
                )
            else:
                physical_response = (
                    row.iL is not None
                    and float(row.iL) * requested_i > 0
                    and abs(float(row.iL)) >= min(
                        0.03, abs(requested_i) * 0.2
                    )
                )
            return command_reflected, physical_response

        cap_row = None
        for candidate in cap_rows:
            reflected, responded = row_confirmation(candidate)
            if reflected and responded:
                cap_row = candidate
                break
        if cap_row is None and cap_rows:
            cap_row = cap_rows[0]

        command_reflected = False
        physical_response = False
        confirmation = None
        if cap_row is not None:
            command_reflected, physical_response = row_confirmation(cap_row)
            confirmation = {
                "received_at": cap_row.timestamp.isoformat(),
                "control_command_reflected": command_reflected,
                "physical_response_observed": physical_response,
                "requested_i_cmd_A": requested_i,
                "effective_i_cmd_A": cap_row.i_cmd_eff,
                "measured_current_A": cap_row.iL,
                "pwm": cap_row.pwm,
                "bus_voltage_V": cap_row.vb_bus,
                "cap_voltage_V": cap_row.v_cap,
            }

        source_received_ns = trace.get("source_fetch_received_ns")
        tlm_received_ns = (
            cap_row.backend_tlm_received_ns if cap_row is not None else None
        )
        return {
            "status": (
                "confirmed"
                if command_reflected and physical_response
                else "command_reflected"
                if command_reflected
                else "awaiting_cap_telemetry"
            ),
            "trace_id": trace_id,
            "algo_id": recommendation.get("algo_id"),
            "algo_name": recommendation.get("algo_name"),
            "day": trace.get("day"),
            "tick": trace.get("tick"),
            "latency_ms": {
                "azure_http_fetch": _elapsed_ms(
                    trace.get("source_fetch_received_ns"),
                    trace.get("source_fetch_started_ns"),
                ),
                "fetch_received_to_decision_start": _elapsed_ms(
                    trace.get("decision_started_ns"), source_received_ns
                ),
                "algorithm_decision": _elapsed_ms(
                    trace.get("decision_finished_ns"),
                    trace.get("decision_started_ns"),
                ),
                "decision_to_dispatch": _elapsed_ms(
                    trace.get("dispatch_started_ns"),
                    trace.get("decision_finished_ns"),
                ),
                "parallel_dispatch": _elapsed_ms(
                    trace.get("dispatch_finished_ns"),
                    trace.get("dispatch_started_ns"),
                ),
                "cap_http_command_round_trip": _elapsed_ms(
                    cap_apply.get("command_finished_ns"),
                    cap_apply.get("command_started_ns"),
                ),
                "pico_command_receive_to_control_loop": (
                    cap_row.fw_cmd_to_apply_ms if cap_row is not None else None
                ),
                "cap_command_start_to_telemetry_received": _elapsed_ms(
                    tlm_received_ns, cap_apply.get("command_started_ns")
                ),
                "fetch_received_to_confirming_telemetry": _elapsed_ms(
                    tlm_received_ns, source_received_ns
                ),
            },
            "confirmation": confirmation,
            "measurement_note": (
                "Azure does not expose its server-side update timestamp. "
                "The E2E start is the first /demand response received by "
                "this backend that contains the new tick."
            ),
        }
    finally:
        db.close()


# ============================================================
# Phase 4b: Per-Azure-day P&L meter for the current run
# ============================================================
# Integrates grid p_import × sell_price and export p_dissip × buy_price
# per Azure day, since /algo/auto/start was last called.
#
# UNITS (confirmed against Azure smart-grid simulation):
#   - buy_price / sell_price are quoted in CURRENCY PER JOULE.
#   - energy_J = p_W × dt_s is true joules.
#   - cost = energy_J × price → currency directly. No per-kWh conversion
#     needed.
#
# PRICE CONVENTION (names are GRID-perspective, not consumer):
#   - sell_price = grid sells to us = WHAT WE PAY TO IMPORT (expensive)
#   - buy_price  = grid buys from us = WHAT WE EARN FROM EXPORT (~0.5×)
#
# Method:
#   - Grid snapshots carry per-tick (day, tick, buy_price, sell_price).
#   - Module snapshots (grid, export) carry p_import / p_dissip in watts.
#   - Group grid snapshots by Azure `day`; each group defines a [t_start,
#     t_end] window for that day. Filter module snapshots by that window.
#   - Trapezoidal integration over consecutive module snapshots:
#     avg_power × dt = energy_J. Multiply by the price in effect at the
#     earlier timestamp (binary-search into that day's grid snapshots).
#   - Gaps > 30 s are treated as missing data and skipped.

import bisect as _bisect

def _bus_cost_integrate(mod_rows, power_field, price_rows, price_field,
                        max_dt_s=30.0):
    """Trapezoidal integration of p_W × dt × price over consecutive
    module snapshots. Returns (energy_J, cost_raw, samples_used)."""
    if not mod_rows or len(mod_rows) < 2:
        return 0.0, 0.0, 0
    price_ts = [p.timestamp for p in price_rows]

    def price_at(ts):
        idx = _bisect.bisect_right(price_ts, ts)
        if idx == 0:
            return None
        return getattr(price_rows[idx - 1], price_field)

    total_e = 0.0
    total_c = 0.0
    samples = 0
    for i in range(1, len(mod_rows)):
        r0, r1 = mod_rows[i - 1], mod_rows[i]
        dt = (r1.timestamp - r0.timestamp).total_seconds()
        if dt <= 0 or dt > max_dt_s:
            continue
        p0 = max(0.0, _f(getattr(r0, power_field, 0)))
        p1 = max(0.0, _f(getattr(r1, power_field, 0)))
        p_avg = 0.5 * (p0 + p1)
        if p_avg <= 0:
            continue
        e_j = p_avg * dt
        total_e += e_j
        pr = price_at(r0.timestamp)
        if pr is not None:
            total_c += e_j * pr
        samples += 1
    return total_e, total_c, samples


def _day_cost_block(day_prices, grid_mod_all, export_mod_all):
    """Build the per-day cost summary dict for a single Azure day.

    `day_prices` is the list of GridSnapshot rows for that day (sorted).
    `grid_mod_all` / `export_mod_all` are the full module-snapshot lists
    for the run; this function slices them by the day's time window.
    """
    if not day_prices:
        return None
    t_start = day_prices[0].timestamp
    t_end   = day_prices[-1].timestamp

    day_grid_mod = [r for r in grid_mod_all
                    if t_start <= r.timestamp <= t_end]
    day_export_mod = [r for r in export_mod_all
                      if t_start <= r.timestamp <= t_end]

    # GRID-perspective pairing: import × sell_price, export × buy_price.
    imp_e, imp_c, imp_n = _bus_cost_integrate(
        day_grid_mod,   "p_import", day_prices, "sell_price"
    )
    exp_e, exp_r, exp_n = _bus_cost_integrate(
        day_export_mod, "p_dissip", day_prices, "buy_price"
    )

    # Time-weighted average prices over the day (for context).
    avg_buy = avg_sell = None
    if len(day_prices) >= 2:
        bs = ss = tt = 0.0
        for j in range(1, len(day_prices)):
            dt = (day_prices[j].timestamp - day_prices[j-1].timestamp).total_seconds()
            if dt <= 0 or dt > 60:
                continue
            bs += (_f(day_prices[j-1].buy_price)  or 0) * dt
            ss += (_f(day_prices[j-1].sell_price) or 0) * dt
            tt += dt
        if tt > 0:
            avg_buy  = bs / tt
            avg_sell = ss / tt

    ticks = [r.tick for r in day_prices if r.tick is not None]
    return {
        "day":             day_prices[0].day,
        "tick_start":      min(ticks) if ticks else None,
        "tick_end":        max(ticks) if ticks else None,
        "ticks_observed":  len(set(ticks)),
        "ticks_total":     60,
        "import_energy_J": round(imp_e, 3),
        "import_cost":     round(imp_c, 4),
        "import_samples":  imp_n,
        "export_energy_J": round(exp_e, 3),
        "export_revenue":  round(exp_r, 4),
        "export_samples":  exp_n,
        "net_cost":        round(imp_c - exp_r, 4),
        "avg_buy_price":   round(avg_buy,  4) if avg_buy  is not None else None,
        "avg_sell_price": round(avg_sell, 4) if avg_sell is not None else None,
    }


@app.get("/algo/run/cost")
def run_cost():
    """Per-Azure-day P&L since the auto-loop was last started.

    Returns 404 if no run has been started in this process. Otherwise:
        {
          run_started_at, run_stopped_at, run_running,
          today:        {day, tick_start, tick_end, ticks_observed,
                         import_cost, export_revenue, net_cost, ...},
          previous_day: {... same shape, or null if not yet recorded},
          price_units, price_ticks,
        }

    Net-cost sign: positive = we paid out, negative = we net-earned.
    """
    started_at = _get_run_started_at_dt()
    if started_at is None:
        raise HTTPException(
            status_code=404,
            detail="No active or recorded run. Start the auto-loop first.",
        )

    db = SessionLocal()
    try:
        # Prices come from grid snapshots — one per Azure tick.
        price_rows = (
            db.query(GridSnapshot)
            .filter(GridSnapshot.timestamp >= started_at)
            .order_by(GridSnapshot.timestamp)
            .all()
        )
        grid_mod = (
            db.query(ModuleSnapshot)
            .filter(ModuleSnapshot.timestamp >= started_at,
                    ModuleSnapshot.role == "grid")
            .order_by(ModuleSnapshot.timestamp)
            .all()
        )
        export_mod = (
            db.query(ModuleSnapshot)
            .filter(ModuleSnapshot.timestamp >= started_at,
                    ModuleSnapshot.role == "export")
            .order_by(ModuleSnapshot.timestamp)
            .all()
        )

        # Group prices by Azure day, preserving first-seen order.
        days_seen = []
        day_to_prices = {}
        for row in price_rows:
            if row.day is None:
                continue
            if row.day not in day_to_prices:
                day_to_prices[row.day] = []
                days_seen.append(row.day)
            day_to_prices[row.day].append(row)

        today_block = previous_block = None
        if days_seen:
            today_day = days_seen[-1]
            today_block = _day_cost_block(
                day_to_prices[today_day], grid_mod, export_mod
            )
            if len(days_seen) >= 2:
                prev_day = days_seen[-2]
                previous_block = _day_cost_block(
                    day_to_prices[prev_day], grid_mod, export_mod
                )

        with _auto_lock:
            stopped_at = _auto_state.get("stopped_at")
            running    = _auto_state.get("running")

        return {
            "run_started_at": started_at.isoformat(),
            "run_stopped_at": stopped_at,
            "run_running":    running,
            "today":          today_block,
            "previous_day":   previous_block,
            "price_units":    "currency_per_joule",
            "price_ticks":    len(price_rows),
        }
    finally:
        db.close()


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


def _build_export_response(grid_rows, mod_rows, dec_rows, meta, fmt,
                           filename_prefix="smartgrid-export"):
    """Format-dispatch helper used by every /export/* endpoint.
    Returns a FastAPI Response (csv zip) or a dict (json)."""
    if fmt == "csv":
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

            # Module snapshots (all columns)
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

            zf.writestr("manifest.json", json.dumps(meta, indent=2))

        buf.seek(0)
        ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        return Response(
            content=buf.read(),
            media_type="application/zip",
            headers={
                "Content-Disposition":
                    f'attachment; filename="{filename_prefix}-{ts}.zip"'
            },
        )

    # JSON
    return {
        **meta,
        "grid_snapshots":   [_grid_row_to_dict(r)     for r in grid_rows],
        "module_snapshots": [_module_row_dict(r)      for r in mod_rows],
        "naive_decisions":  [_decision_row_to_dict(r) for r in dec_rows],
    }


def _get_run_started_at_dt():
    """Read the current auto-loop run's start time as a naive UTC datetime,
    or None if the loop has never been started in this process."""
    with _auto_lock:
        s = _auto_state.get("started_at")
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


@app.get("/export/full")
def export_full(format: str = "json",
                since: str = None,
                until: str = None,
                last_hours: float = None):
    """Export every row in the requested range. No filter = everything."""
    db = SessionLocal()
    try:
        grid_rows, mod_rows, dec_rows, since_dt, until_dt = _query_export(
            db, since=since, until=until, last_hours=last_hours
        )
        meta = {
            "exported_at":    datetime.utcnow().isoformat(),
            "scope":          "full",
            "since":          since_dt.isoformat() if since_dt else None,
            "until":          until_dt.isoformat() if until_dt else None,
            "grid_count":     len(grid_rows),
            "module_count":   len(mod_rows),
            "decision_count": len(dec_rows),
        }
        return _build_export_response(grid_rows, mod_rows, dec_rows, meta,
                                      format, filename_prefix="smartgrid-full")
    finally:
        db.close()


@app.get("/export/run")
def export_run(format: str = "csv"):
    """Export every row recorded SINCE the most recent auto-loop start.
    Returns 404 if /algo/auto/start has not been called this process.

    This is what the dashboard "Download CSV zip" button hits — it scopes
    to a single test run rather than the full DB history."""
    started_at = _get_run_started_at_dt()
    if started_at is None:
        raise HTTPException(
            status_code=404,
            detail="No active or recorded run. Start the auto-loop first "
                   "(POST /algo/auto/start), then download.",
        )

    db = SessionLocal()
    try:
        grid_rows, mod_rows, dec_rows, since_dt, until_dt = _query_export(
            db, since=started_at.isoformat(), until=None, last_hours=None
        )
        with _auto_lock:
            stopped_at = _auto_state.get("stopped_at")
            running    = _auto_state.get("running")
        meta = {
            "exported_at":    datetime.utcnow().isoformat(),
            "scope":          "run",
            "run_started_at": started_at.isoformat(),
            "run_stopped_at": stopped_at,
            "run_running":    running,
            "since":          since_dt.isoformat() if since_dt else None,
            "grid_count":     len(grid_rows),
            "module_count":   len(mod_rows),
            "decision_count": len(dec_rows),
        }
        return _build_export_response(grid_rows, mod_rows, dec_rows, meta,
                                      format, filename_prefix="smartgrid-run")
    finally:
        db.close()


def _counts_in_range(db, since=None, until=None):
    """Counts + earliest/latest timestamps for each table within range."""
    def first_last(q, col):
        first = q.order_by(col.asc()).first()
        last  = q.order_by(col.desc()).first()
        return (
            first.timestamp.isoformat() if first else None,
            last.timestamp.isoformat()  if last  else None,
        )

    def scope(q, col):
        if since is not None: q = q.filter(col >= since)
        if until is not None: q = q.filter(col <= until)
        return q

    g_q = scope(db.query(GridSnapshot),   GridSnapshot.timestamp)
    m_q = scope(db.query(ModuleSnapshot), ModuleSnapshot.timestamp)
    d_q = scope(db.query(NaiveDecision),  NaiveDecision.timestamp)

    g_first, g_last = first_last(g_q, GridSnapshot.timestamp)
    m_first, m_last = first_last(m_q, ModuleSnapshot.timestamp)
    d_first, d_last = first_last(d_q, NaiveDecision.timestamp)

    return {
        "grid_snapshots":   {"count": g_q.count(), "first": g_first, "last": g_last},
        "module_snapshots": {"count": m_q.count(), "first": m_first, "last": m_last},
        "naive_decisions":  {"count": d_q.count(), "first": d_first, "last": d_last},
    }


@app.get("/export/summary")
def export_summary():
    """All-time counts + earliest/latest timestamps."""
    db = SessionLocal()
    try:
        return _counts_in_range(db)
    finally:
        db.close()


@app.get("/export/run/summary")
def export_run_summary():
    """Counts scoped to the current auto-loop run."""
    started_at = _get_run_started_at_dt()
    if started_at is None:
        with _auto_lock:
            stopped_at = _auto_state.get("stopped_at")
        return {
            "run_started_at": None,
            "run_stopped_at": stopped_at,
            "run_running":    False,
            "grid_snapshots":   {"count": 0, "first": None, "last": None},
            "module_snapshots": {"count": 0, "first": None, "last": None},
            "naive_decisions":  {"count": 0, "first": None, "last": None},
        }

    db = SessionLocal()
    try:
        counts = _counts_in_range(db, since=started_at)
        with _auto_lock:
            stopped_at = _auto_state.get("stopped_at")
            running    = _auto_state.get("running")
        return {
            "run_started_at": started_at.isoformat(),
            "run_stopped_at": stopped_at,
            "run_running":    running,
            **counts,
        }
    finally:
        db.close()


