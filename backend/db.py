from sqlalchemy import (
    create_engine, Column, Integer, BigInteger, Float, DateTime, String,
    Index, UniqueConstraint, text,
)
import json
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

DATABASE_URL = "sqlite:///smartgrid.db"

engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()

class GridSnapshot(Base):
    __tablename__ = "grid_snapshots"

    __table_args__ = (
        UniqueConstraint("day", "tick", name="unique_day_tick"),
    )

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    day = Column(Integer)
    tick = Column(Integer)
    sun = Column(Float)
    buy_price = Column(Float)
    sell_price = Column(Float)
    instant_demand = Column(Float)
    deferables_json = Column(String)
    source_fetch_started_ns = Column(BigInteger)
    source_fetch_received_ns = Column(BigInteger)


class ModuleSnapshot(Base):
    """Per-role telemetry from firmware modules (pv, grid, export, cap, led)."""
    __tablename__ = "module_snapshots"
    __table_args__ = (
        Index("ix_module_snapshots_role_id", "role", "id"),
        Index("ix_module_snapshots_role_timestamp", "role", "timestamp"),
    )

    id          = Column(Integer, primary_key=True, index=True)
    timestamp   = Column(DateTime, default=datetime.utcnow)
    role        = Column(String, index=True)

    # Common to all SMPS modules
    trip        = Column(Integer)
    trip_reason = Column(String)
    enable      = Column(Integer)
    wd          = Column(Integer)
    pwm         = Column(Integer)
    vb_bus      = Column(Float)
    iL          = Column(Float)
    i_ref       = Column(Float)
    vb_target   = Column(Float)

    # PV boost
    v_panel     = Column(Float)
    p_panel     = Column(Float)
    vmpp_target = Column(Float)
    mppt_mode   = Column(String)
    irradiance  = Column(Float)
    web_tick    = Column(Integer)

    # Grid buck
    v_psu    = Column(Float)
    p_import = Column(Float)

    # Export buck
    v_resistor = Column(Float)
    p_dissip   = Column(Float)

    # Supercap bidirectional
    v_cap     = Column(Float)
    p_cap     = Column(Float)
    soc_pct   = Column(Float)
    energy_J  = Column(Float)
    i_cmd     = Column(Float)
    i_cmd_eff = Column(Float)
    trace_id  = Column(String, index=True)
    trace_tick = Column(Integer)
    fw_cmd_received_ms = Column(Integer)
    fw_cmd_applied_ms = Column(Integer)
    fw_cmd_to_apply_ms = Column(Integer)
    backend_tlm_received_ns = Column(BigInteger)

    # LED CC driver (3 channels)
    i_red = Column(Float)
    i_yel = Column(Float)
    i_grn = Column(Float)
    v_red = Column(Float)
    v_yel = Column(Float)
    v_grn = Column(Float)
    p_red = Column(Float)
    p_yel = Column(Float)
    p_grn = Column(Float)


class NaiveDecision(Base):
    """One row per algo auto-loop iteration that produced a /cmd dispatch.
    Used to reconstruct the full-day decision history offline.

    Table name kept as "naive_decisions" for back-compat; the column
    ``algo_id`` records which algorithm (naive / smart_v1 / ...) produced
    each row so the dashboard can filter or A/B compare runs."""
    __tablename__ = "naive_decisions"

    id         = Column(Integer, primary_key=True, index=True)
    timestamp  = Column(DateTime, default=datetime.utcnow)
    tick       = Column(Integer, index=True)
    regime     = Column(String)         # "surplus" / "deficit" / "idle" / "arb_charge" / ...
    algo_id    = Column(String, index=True, default="naive")  # "naive" / "smart_v1" / ...
    all_ok     = Column(Integer)        # 1 if all four module POSTs succeeded
    # Snapshot of inputs that fed the decision (pv_p, demand, vbus, v_cap, ...)
    inputs_json         = Column(String)
    # Full recommendation dict (suggested setpoints + diagnostic fields)
    recommendation_json = Column(String)
    # Per-module response from _post_module_cmd
    applied_json        = Column(String)


def _fi(v):
    """Return float or None, safely coercing from any JSON-decoded type."""
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _ii(v):
    """Return int or None."""
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _si(v):
    """Return str or None."""
    return str(v) if v is not None else None


def init_db():
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        migrations = {
            "grid_snapshots": {
                "source_fetch_started_ns": "BIGINT",
                "source_fetch_received_ns": "BIGINT",
            },
            "module_snapshots": {
                "trace_id": "TEXT",
                "trace_tick": "INTEGER",
                "fw_cmd_received_ms": "INTEGER",
                "fw_cmd_applied_ms": "INTEGER",
                "fw_cmd_to_apply_ms": "INTEGER",
                "backend_tlm_received_ns": "BIGINT",
            },
            "naive_decisions": {
                "algo_id": "TEXT DEFAULT 'naive'",
            },
        }
        for table, additions in migrations.items():
            cols = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            col_names = {c[1] for c in cols}
            for column, sql_type in additions.items():
                if column in col_names:
                    continue
                try:
                    conn.execute(text(
                        f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}"
                    ))
                    conn.commit()
                    print(f"[db] migrated: added {table}.{column}")
                except Exception as exc:
                    print(f"[db] migration warning for {table}.{column}: {exc}")
        for index_sql in (
            "CREATE INDEX IF NOT EXISTS ix_grid_snapshots_timestamp "
            "ON grid_snapshots (timestamp)",
            "CREATE INDEX IF NOT EXISTS ix_module_snapshots_role_id "
            "ON module_snapshots (role, id)",
            "CREATE INDEX IF NOT EXISTS ix_module_snapshots_role_timestamp "
            "ON module_snapshots (role, timestamp)",
        ):
            conn.execute(text(index_sql))
        conn.commit()

def save_snapshot(state):
    db = SessionLocal()

    existing = (
        db.query(GridSnapshot)
        .filter(
            GridSnapshot.day == state["day"],
            GridSnapshot.tick == state["tick"],
        )
        .first()
    )

    if existing is not None:
        db.close()
        return False

    snapshot = GridSnapshot(
        day=state["day"],
        tick=state["tick"],
        sun=state["sun"],
        buy_price=state["buy_price"],
        sell_price=state["sell_price"],
        instant_demand=state["instant_demand"],
        deferables_json=json.dumps(state.get("deferables", [])),
        source_fetch_started_ns=_ii(state.get("source_fetch_started_ns")),
        source_fetch_received_ns=_ii(state.get("source_fetch_received_ns")),
    )

    db.add(snapshot)
    db.commit()
    db.close()

    return True


def get_latest_grid_tick(day):
    db = SessionLocal()
    try:
        row = (
            db.query(GridSnapshot.tick)
            .filter(GridSnapshot.day == day)
            .order_by(GridSnapshot.tick.desc())
            .first()
        )
        return int(row[0]) if row is not None else None
    finally:
        db.close()


def save_module_snapshot(payload):
    """Store one telemetry frame from any firmware module (identified by role)."""
    g = payload.get
    db = SessionLocal()
    snap = ModuleSnapshot(
        role        = _si(g('role')),
        trip        = _ii(g('trip')),
        trip_reason = _si(g('trip_reason')),
        enable      = _ii(g('enable')),
        wd          = _ii(g('wd')),
        pwm         = _ii(g('pwm')),
        vb_bus      = _fi(g('vb_bus')),
        iL          = _fi(g('iL')),
        i_ref       = _fi(g('i_ref')),
        vb_target   = _fi(g('vb_target')),
        v_panel     = _fi(g('v_panel')),
        p_panel     = _fi(g('p_panel')),
        vmpp_target = _fi(g('vmpp_target')),
        mppt_mode   = _si(g('mppt_mode')),
        irradiance  = _fi(g('irradiance')),
        web_tick    = _ii(g('web_tick')),
        v_psu       = _fi(g('v_psu')),
        p_import    = _fi(g('p_import')),
        v_resistor  = _fi(g('v_resistor')),
        p_dissip    = _fi(g('p_dissip')),
        v_cap       = _fi(g('v_cap')),
        p_cap       = _fi(g('p_cap')),
        soc_pct     = _fi(g('soc_pct')),
        energy_J    = _fi(g('energy_J')),
        i_cmd       = _fi(g('i_cmd')),
        i_cmd_eff   = _fi(g('i_cmd_eff')),
        trace_id    = _si(g('trace_id')),
        trace_tick  = _ii(g('trace_tick')),
        fw_cmd_received_ms = _ii(g('fw_cmd_received_ms')),
        fw_cmd_applied_ms = _ii(g('fw_cmd_applied_ms')),
        fw_cmd_to_apply_ms = _ii(g('fw_cmd_to_apply_ms')),
        backend_tlm_received_ns = _ii(g('backend_tlm_received_ns')),
        i_red       = _fi(g('i_red')),
        i_yel       = _fi(g('i_yel')),
        i_grn       = _fi(g('i_grn')),
        v_red       = _fi(g('v_red')),
        v_yel       = _fi(g('v_yel')),
        v_grn       = _fi(g('v_grn')),
        p_red       = _fi(g('p_red')),
        p_yel       = _fi(g('p_yel')),
        p_grn       = _fi(g('p_grn')),
    )
    db.add(snap)
    db.commit()
    db.close()
    return True


def save_naive_decision(decision):
    """Persist one algo decision. ``decision`` is a dict with keys:
    tick, regime, algo_id, all_ok, inputs, recommendation, applied."""
    db = SessionLocal()
    try:
        row = NaiveDecision(
            tick                = _ii(decision.get("tick")),
            regime              = _si(decision.get("regime")),
            algo_id             = _si(decision.get("algo_id")) or "naive",
            all_ok              = 1 if decision.get("all_ok") else 0,
            inputs_json         = json.dumps(decision.get("inputs", {})),
            recommendation_json = json.dumps(decision.get("recommendation", {})),
            applied_json        = json.dumps(decision.get("applied", {})),
        )
        db.add(row)
        db.commit()
    finally:
        db.close()
    return True
