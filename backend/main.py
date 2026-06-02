import json
import os
import socket
import threading
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import desc
from db import (SessionLocal, GridSnapshot, ModuleSnapshot,
                init_db, save_module_snapshot)
from datetime import datetime

app = FastAPI()

MODULE_CMD_TIMEOUT = float(os.getenv("MODULE_CMD_TIMEOUT", "2"))
MODULE_CMD_TARGETS = {
    "pv": os.getenv("PICO_PV_URL", "http://192.168.137.21"),
    "grid": os.getenv("PICO_GRID_URL", "http://192.168.137.22"),
    "cap": os.getenv("PICO_CAP_URL", "http://192.168.137.23"),
    "led": os.getenv("PICO_LED_URL", "http://192.168.137.24"),
    "export": os.getenv("PICO_EXPORT_URL", "http://192.168.137.25"),
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
    path = parsed.path.rstrip("/") + "/cmd"
    body = json.dumps(payload)
    req = (
        f"POST {path} HTTP/1.1\r\n"
        f"Host: {hostname}\r\n"
        "Content-Type: text/plain;charset=UTF-8\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n"
        "\r\n"
        f"{body}"
    ).encode("utf-8")

    try:
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

        return {
            "ok": 200 <= status_code < 300,
            "status": status_code,
            "url": host.rstrip("/") + "/cmd",
            "payload": payload,
            "response": response_body[:200],
        }
    except OSError as exc:
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
    if grid_row is None:
        return {
            "error": "No grid snapshot available",
        }

    pv_row = module_rows.get("pv")
    cap_row = module_rows.get("cap")

    tick = _i(grid_row.tick, 0)
    pv_power = max(0.0, _f(getattr(pv_row, "p_panel", None), 0.0))
    demand = max(0.0, _f(grid_row.instant_demand, 0.0))

    deferables = json.loads(str(grid_row.deferables_json or "[]"))
    if not isinstance(deferables, list):
        deferables = []

    vbus = _f(getattr(cap_row, "vb_bus", None), 0.0)
    if vbus <= 0:
        vbus = _f(getattr(pv_row, "vb_bus", None), 0.0)
    if vbus <= 0:
        vbus = 9.5

    energy_cap = max(0.0, _f(getattr(cap_row, "energy_J", None), 0.0))

    led_total_power = 0.0
    cap_i_cmd = 0.0
    power_left = max(0.0, pv_power - demand)
    served_deferrables = []

    if pv_power > demand:
        # Earliest-deadline-first service for active deferrable jobs.
        candidates = []
        for idx, item in enumerate(deferables):
            if not isinstance(item, dict):
                continue
            start_tick = _get_window_tick(item, "tick_start", "start")
            end_tick = _get_window_tick(item, "tick_end", "end")
            start_tick = _i(start_tick)
            end_tick = _i(end_tick)
            if start_tick is None or end_tick is None:
                continue
            candidates.append((end_tick, idx, start_tick, dict(item)))

        for _, idx, start_tick, job in sorted(candidates, key=lambda x: x[0]):
            if power_left <= 0:
                break

            end_tick = _i(_get_window_tick(job, "tick_end", "end"))
            if end_tick is None:
                continue
            if not (start_tick <= tick <= end_tick):
                continue

            energy = max(0.0, _f(job.get("energy"), 0.0))
            if energy <= 0:
                continue

            served = min(energy, power_left)
            remaining = energy - served
            power_left -= served

            served_deferrables.append(
                {
                    "index": idx,
                    "served_energy": served,
                    "remaining_energy": remaining,
                    "tick_start": start_tick,
                    "tick_end": end_tick,
                }
            )

        led_total_power = pv_power - power_left
        cap_i_cmd = power_left / vbus if power_left > 0 else 0.0
    elif energy_cap > 0:
        led_total_power = demand
        cap_i_cmd = -0.60
    else:
        led_total_power = pv_power
        cap_i_cmd = 0.0

    led_each = led_total_power / 3.0

    return {
        "tick": tick,
        "inputs": {
            "pv_power_W": pv_power,
            "demand_W": demand,
            "vbus_V": vbus,
            "energy_cap_J": energy_cap,
            "deferables_count": len(deferables),
        },
        "suggested": {
            "cap": {
                "i_cmd": round(cap_i_cmd, 4),
            },
            "led": {
                "p_red": round(led_each, 4),
                "p_yel": round(led_each, 4),
                "p_grn": round(led_each, 4),
            },
        },
        "served_deferrables": served_deferrables,
        "remaining_surplus_W": round(max(0.0, power_left), 4),
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


@app.post("/algo/naive/apply")
def apply_naive_recommendation():
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

        recommendation = _run_naive_from_db(grid_row, module_rows)
        if "error" in recommendation:
            raise HTTPException(status_code=404, detail=recommendation["error"])

        suggested = recommendation.get("suggested", {})
        if not isinstance(suggested, dict):
            suggested = {}

        cap_payload = suggested.get("cap", {})
        led_payload = suggested.get("led", {})
        if not isinstance(cap_payload, dict):
            cap_payload = {}
        if not isinstance(led_payload, dict):
            led_payload = {}

        cap_result = _post_module_cmd("cap", cap_payload)
        led_result = _post_module_cmd("led", led_payload)

        return {
            "ok": bool(cap_result.get("ok") and led_result.get("ok")),
            "recommendation": recommendation,
            "applied": {
                "cap": cap_result,
                "led": led_result,
            },
        }
    finally:
        db.close()


