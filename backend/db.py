from sqlalchemy import create_engine, Column, Integer, Float, DateTime, String, UniqueConstraint
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


class ModuleSnapshot(Base):
    """Per-role telemetry from firmware modules (pv, grid, export, cap, led)."""
    __tablename__ = "module_snapshots"

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
    # Lightweight migration: add algo_id column to naive_decisions if an
    # older DB pre-dates it. SQLite doesn't error if the column already
    # exists once we've checked PRAGMA table_info.
    with engine.connect() as conn:
        from sqlalchemy import text
        cols = conn.execute(text("PRAGMA table_info(naive_decisions)")).fetchall()
        col_names = {c[1] for c in cols}
        if "algo_id" not in col_names:
            try:
                conn.execute(text(
                    "ALTER TABLE naive_decisions ADD COLUMN algo_id TEXT DEFAULT 'naive'"
                ))
                conn.commit()
                print("[db] migrated: added algo_id column to naive_decisions")
            except Exception as exc:
                print(f"[db] migration warning: {exc}")

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
    )

    db.add(snapshot)
    db.commit()
    db.close()

    return True

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