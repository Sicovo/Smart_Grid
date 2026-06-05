import { useEffect, useMemo, useRef, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";

// ─── Constants ────────────────────────────────────────────────────────────────

const ROLES = ["pv", "grid", "export", "cap", "led"];
const ALGORITHM_ROLES = ["pv", "grid", "export", "cap", "led"];

const HIST_MAX = 60;
const GAUGE_LO = 8.0;
const GAUGE_HI = 12.0;

const GRID_TARGET_DEFAULT = 9.5;
const EXPORT_TARGET_DEFAULT = 10.5;

const DEFAULT_HOSTS = {
  pv: "pv.local",
  grid: "grid.local",
  export: "export.local",
  cap: "cap.local",
  led: "led.local",
};

const ROLE_COLORS = {
  pv: "#6fb86f",
  grid: "#5a8ec9",
  export: "#b67ad9",
  cap: "#5ec9c0",
  led: "#d9a85a",
};

const ROLE_LABELS = {
  pv: "PV — boost, MPPT",
  grid: "Grid — buck, CV import",
  export: "Export — buck, CV dissipate",
  cap: "Cap — bidirectional, command-driven",
  led: "LED load — 3 × CC",
};

const GLOBAL_LINES = [
  { key: "vbus", label: "Vbus", color: "#e6e6e6", axis: "V" },
  { key: "i_pv", label: "PV iL", color: "#6fb86f", axis: "A" },
  { key: "i_grid", label: "Grid iL", color: "#5a8ec9", axis: "A" },
  { key: "i_export", label: "Export iL", color: "#b67ad9", axis: "A" },
  { key: "i_cap", label: "Cap iL", color: "#5ec9c0", axis: "A" },
  { key: "i_led", label: "LED iL Σ", color: "#d9a85a", axis: "A" },
];

const MOD_CHART_LINES = {
  pv: [
    { key: "v_panel", label: "Vpv", color: "#6fb86f" },
    { key: "vb_bus", label: "Vbus", color: "#e6e6e6" },
    { key: "iL", label: "iL", color: "#5a8ec9" },
    { key: "vmpp_target", label: "Vmpp", color: "#f5c84b", dashed: true },
  ],
  grid: [
    { key: "vb_bus", label: "Vbus", color: "#e6e6e6" },
    { key: "v_psu", label: "Vpsu", color: "#d9a85a" },
    { key: "iL", label: "iL", color: "#5a8ec9" },
  ],
  export: [
    { key: "vb_bus", label: "Vbus", color: "#e6e6e6" },
    { key: "v_resistor", label: "Vres", color: "#6fb86f" },
    { key: "iL", label: "iL", color: "#b67ad9" },
  ],
  cap: [
    { key: "v_cap", label: "Vcap", color: "#5ec9c0" },
    { key: "vb_bus", label: "Vbus", color: "#e6e6e6" },
    { key: "iL", label: "iL", color: "#5ec9c0" },
  ],
  led: [
    { key: "i_red", label: "R", color: "#e07070" },
    { key: "i_yel", label: "Y", color: "#d9c95a" },
    { key: "i_grn", label: "G", color: "#6fb86f" },
  ],
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmt(v, digits = 2) {
  if (v === null || v === undefined || (typeof v === "number" && Number.isNaN(v))) {
    return "—";
  }
  if (typeof v === "number") return v.toFixed(digits);
  return String(v);
}

function safeNumber(v) {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function normaliseHost(raw) {
  let h = String(raw || "").trim();
  if (!h) return "";
  if (!h.startsWith("http")) h = `http://${h}`;
  if (h.endsWith("/")) h = h.slice(0, -1);
  return h;
}

function firstHost(raw) {
  return String(raw || "")
    .split(/[\s,;]+/)
    .filter(Boolean)[0] || "";
}

function getBusVoltage(modules) {
  return (
    safeNumber(modules?.grid?.vb_bus) ??
    safeNumber(modules?.export?.vb_bus) ??
    safeNumber(modules?.pv?.vb_bus) ??
    safeNumber(modules?.cap?.vb_bus) ??
    null
  );
}

function busState(vbus) {
  if (vbus === null) return "no telemetry";
  if (vbus < 9.5) return "← grid importing";
  if (vbus > 10.5) return "export dissipating →";
  return "idle deadband";
}

function makeGlobalSample(modules) {
  const led = modules?.led || {};
  return {
    t: new Date().toLocaleTimeString(),
    vbus: getBusVoltage(modules),
    i_pv: safeNumber(modules?.pv?.iL),
    i_grid: safeNumber(modules?.grid?.iL),
    i_export: safeNumber(modules?.export?.iL),
    i_cap: safeNumber(modules?.cap?.iL),
    i_led:
      safeNumber(led.i_red) !== null ||
      safeNumber(led.i_yel) !== null ||
      safeNumber(led.i_grn) !== null
        ? (led.i_red || 0) + (led.i_yel || 0) + (led.i_grn || 0)
        : null,
  };
}

// ─── UI atoms ────────────────────────────────────────────────────────────────

function Btn({ children, onClick, variant = "", disabled = false }) {
  return (
    <button
      className={`smps-btn${variant ? ` smps-btn-${variant}` : ""}`}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}

function CtrlRow({ label, children }) {
  return (
    <div className="smps-ctrl-row">
      <span className="smps-ctrl-label">{label}</span>
      <div className="smps-ctrl-body">{children}</div>
    </div>
  );
}

function StatusPill({ d, status }) {
  // /modules/status is the source of truth for online/offline.
  // Expected backend shape:
  // { pv: { online: true, last_seen: "...", age_s: 1.23 }, ... }
  if (!status || status.online === false) {
    return <span className="smps-pill smps-pill-err">offline</span>;
  }

  // Once online, fault/status detail still comes from latest telemetry.
  if (d?.trip) return <span className="smps-pill smps-pill-err">TRIP</span>;
  if (d?.wd) return <span className="smps-pill smps-pill-warn">WATCHDOG</span>;
  if (d && d.enable === false) return <span className="smps-pill smps-pill-warn">disabled</span>;

  return <span className="smps-pill smps-pill-ok">online</span>;
}

function StatusLine({ status }) {
  const online = status?.online === true;
  const age =
    status?.age_s !== null && status?.age_s !== undefined && Number.isFinite(Number(status.age_s))
      ? ` · age ${Number(status.age_s).toFixed(1)}s`
      : "";
  const last = status?.last_seen ? ` · last ${status.last_seen}` : "";

  return (
    <div className="smps-mod-host">
      status: {online ? "online" : "offline"}
      {age}
      {last}
    </div>
  );
}

function Stat({ label, val, unit, digits = 2, tag = "", sub = "", wide = false }) {
  return (
    <div className={`smps-stat ${wide ? "smps-stat-wide" : ""}`} data-tag={tag || undefined}>
      <div className="smps-stat-label">{label}</div>
      <div className="smps-stat-val">
        {fmt(val, digits)}
        {unit && <span className="smps-stat-unit"> {unit}</span>}
      </div>
      {sub && <div className="smps-stat-sub">{sub}</div>}
    </div>
  );
}

// ─── Top bus gauge and global chart ──────────────────────────────────────────

function BusGauge({ vbus }) {
  const pct = vbus === null ? 0 : ((vbus - GAUGE_LO) / (GAUGE_HI - GAUGE_LO)) * 100;
  const clamped = Math.max(0, Math.min(100, pct));
  const dbLeft = ((9.5 - GAUGE_LO) / (GAUGE_HI - GAUGE_LO)) * 100;
  const dbWidth = ((10.5 - 9.5) / (GAUGE_HI - GAUGE_LO)) * 100;

  return (
    <div className="smps-gauge">
      <div className="smps-gauge-top">
        <div className="smps-gauge-v">
          <b>{vbus === null ? "--.--" : vbus.toFixed(2)}</b>V bus
        </div>
        <div className="smps-gauge-state">{busState(vbus)}</div>
      </div>

      <div className="smps-gauge-bar">
        <div
          className="smps-gauge-deadband"
          style={{ left: `${dbLeft}%`, width: `${dbWidth}%` }}
        />
        {vbus !== null && <div className="smps-gauge-marker" style={{ left: `${clamped}%` }} />}
      </div>

      <div className="smps-gauge-scale">
        <span>8.0</span>
        <span>9.0</span>
        <span>9.5</span>
        <span>10.0</span>
        <span>10.5</span>
        <span>11.0</span>
        <span>12.0</span>
      </div>
    </div>
  );
}

function GlobalChart({ data, theme = "dark" }) {
  const [visible, setVisible] = useState(() =>
    Object.fromEntries(GLOBAL_LINES.map((l) => [l.key, true]))
  );
  const isLightTheme = theme === "light";
  const axisColor = isLightTheme ? "#38475f" : "#666";
  const tooltipBackground = isLightTheme ? "#ffffff" : "#0d0d0d";
  const tooltipBorder = isLightTheme ? "#cfd9e8" : "#2c2c2c";
  const tooltipText = isLightTheme ? "#1a2333" : "#e6e6e6";
  const referenceColor = isLightTheme ? "#4b6b98" : "#5a8ec9";
  const lineColors = isLightTheme
    ? {
        vbus: "#5b6678",
        i_pv: "#1f7d3b",
        i_grid: "#2e5f93",
        i_export: "#7a4cb8",
        i_cap: "#2f7f7a",
        i_led: "#9b6a21",
      }
    : Object.fromEntries(GLOBAL_LINES.map((l) => [l.key, l.color]));

  return (
    <div className="smps-global-chart">
      <div className="smps-chart-head">
        <div className="smps-chart-title">Last 60 s</div>
        <div className="smps-chart-legend">
          {GLOBAL_LINES.map((l) => (
            <button
              key={l.key}
              className={`smps-legend-toggle ${visible[l.key] ? "on" : ""}`}
              onClick={() => setVisible((p) => ({ ...p, [l.key]: !p[l.key] }))}
            >
              <span className="smps-swatch" style={{ background: lineColors[l.key] }} />
              {l.label}
            </button>
          ))}
        </div>
      </div>

      <div className="smps-chart-box">
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: -16 }}>
            <XAxis dataKey="t" tick={{ fontSize: 10, fill: axisColor }} />
            <YAxis tick={{ fontSize: 10, fill: axisColor }} width={42} />
            <Tooltip
              contentStyle={{
                background: tooltipBackground,
                border: `1px solid ${tooltipBorder}`,
                borderRadius: 6,
                fontSize: 11,
              }}
              itemStyle={{ color: tooltipText }}
            />
            <ReferenceLine y={9.5} stroke={referenceColor} strokeDasharray="3 3" />
            <ReferenceLine y={10.5} stroke={referenceColor} strokeDasharray="3 3" />

            {GLOBAL_LINES.filter((l) => visible[l.key]).map((l) => (
              <Line
                key={l.key}
                type="linear"
                dataKey={l.key}
                name={l.label}
                stroke={lineColors[l.key]}
                strokeWidth={l.axis === "V" ? 2 : 1.5}
                dot={false}
                connectNulls={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="smps-chart-foot">
        left axis mixed: V and A · main reference: Vbus deadband 9.5–10.5 V
      </div>
    </div>
  );
}

// ─── Stat blocks ─────────────────────────────────────────────────────────────

function PVStats({ d }) {
  if (!d) return null;
  const irrPct = typeof d.irradiance === "number" ? d.irradiance * 100 : null;
  const mode = d.mppt_mode || null;
  return (
    <>
      <Stat label="PV voltage Vb" val={d.v_panel} unit="V" tag="pv" />
      <Stat label="Bus voltage Va" val={d.vb_bus} unit="V" tag="bus" />
      <Stat label="Inductor iL" val={d.iL} unit="A" digits={3} tag="bus" />
      <Stat label="PV power" val={d.p_panel} unit="W" tag="pwr-in" />
      <Stat label="Ppv 3s avg" val={d.p_avg3s} unit="W" digits={3} sub="resets on mode change" />
      <Stat label="i_ref" val={d.i_ref} unit="A" digits={3} />
      <Stat label="Vmpp target" val={d.vmpp_target} unit="V" sub={mode === "web" ? "auto (web)" : "manual"} />
      <Stat label="MPPT mode" val={mode ? mode.toUpperCase() : null} tag="sun" />
      <Stat
        label="Irradiance"
        val={irrPct}
        unit="%"
        digits={0}
        tag="sun"
        sub={d.web_tick !== undefined && d.web_tick !== null ? `server tick ${d.web_tick}` : "no fetch yet"}
      />
    </>
  );
}

function GridStats({ d }) {
  if (!d) return null;
  return (
    <>
      <Stat label="Grid PSU Va" val={d.v_psu} unit="V" tag="bus" />
      <Stat label="Bus voltage Vb" val={d.vb_bus} unit="V" tag="bus" />
      <Stat label="Inductor iL" val={d.iL} unit="A" digits={3} tag="bus" />
      <Stat label="Import power" val={d.p_import} unit="W" tag="pwr-in" />
      <Stat label="Pimp 3s avg" val={d.p_avg3s} unit="W" digits={3} sub="resets on target change" />
      <Stat label="i_ref" val={d.i_ref} unit="A" digits={3} />
      <Stat label="Bus target" val={d.vb_target} unit="V" />
    </>
  );
}

function ExportStats({ d }) {
  if (!d) return null;
  return (
    <>
      <Stat label="Bus voltage Va" val={d.vb_bus} unit="V" tag="bus" />
      <Stat label="Load voltage Vb" val={d.v_resistor} unit="V" tag="pv" />
      <Stat label="Load current iL" val={d.iL} unit="A" digits={3} tag="bus" />
      <Stat label="Dissipated power" val={d.p_dissip} unit="W" tag="pwr-out" />
      <Stat label="i_ref" val={d.i_ref} unit="A" digits={3} />
      <Stat label="Bus target" val={d.vb_target} unit="V" />
    </>
  );
}

function CapStats({ d }) {
  if (!d) return null;

  const soc = typeof d.soc_pct === "number" ? Math.max(0, Math.min(100, d.soc_pct)) : 0;

  let dir = "—";
  if (typeof d.iL === "number") {
    if (d.iL > 0.02) dir = "CHARGING";
    else if (d.iL < -0.02) dir = "DISCHARGING";
    else dir = "IDLE";
  }

  let cmdSub = "";
  if (
    typeof d.i_cmd === "number" &&
    typeof d.i_cmd_eff === "number" &&
    Math.abs(d.i_cmd - d.i_cmd_eff) > 0.005
  ) {
    cmdSub = `limited → ${d.i_cmd_eff.toFixed(3)} A`;
  }

  return (
    <>
      <Stat label="Cap voltage Va" val={d.v_cap} unit="V" tag="cap" />
      <Stat label="Bus voltage Vb" val={d.vb_bus} unit="V" tag="bus" />
      <Stat label="Inductor iL" val={d.iL} unit="A" digits={3} tag="cap" />
      <Stat
        label="Cap power"
        val={d.p_cap}
        unit="W"
        tag="pwr-in"
        sub={typeof d.p_cap === "number" && d.p_cap < 0 ? "discharging" : "charging"}
      />
      <Stat label="Pcap 3s avg" val={d.p_avg3s} unit="W" digits={3} sub="resets on i_cmd change" />
      <Stat label="i_cmd" val={d.i_cmd} unit="A" digits={3} sub={cmdSub} />
      <Stat label="Direction" val={dir} tag="cap" />

      <div className="smps-stat smps-stat-wide" data-tag="cap">
        <div className="smps-stat-label">State of charge</div>
        <div className="smps-stat-val">
          {fmt(d.soc_pct, 0)}
          <span className="smps-stat-unit"> %</span>
        </div>
        <div className="smps-soc-track">
          <div className="smps-soc-fill" style={{ width: `${soc}%` }} />
        </div>
      </div>

      <Stat label="Energy stored" val={d.energy_J} unit="J" digits={1} />
    </>
  );
}

function LEDStats({ d, lastBusVoltage }) {
  if (!d) return null;
  const total = (d.p_red || 0) + (d.p_yel || 0) + (d.p_grn || 0);

  return (
    <div className="smps-led-wrap">
      <div className="smps-stats-grid">
        <Stat label="Bus voltage VIN" val={lastBusVoltage} unit="V" tag="bus" />
        <Stat label="Total load" val={total} unit="W" tag="pwr-in" />
      </div>

      <div className="smps-led-table">
        <div className="smps-led-header">
          <span>CH</span>
          <span>I</span>
          <span>V</span>
          <span>P</span>
        </div>

        {["red", "yel", "grn"].map((c) => (
          <div key={c} className="smps-led-row">
            <span className={`smps-led-color smps-led-${c}`}>{c.toUpperCase()}</span>
            <span>{fmt(d[`i_${c}`], 2)} A</span>
            <span>{fmt(d[`v_${c}`], 2)} V</span>
            <span>{fmt(d[`p_${c}`], 2)} W</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Controls ────────────────────────────────────────────────────────────────

function PVControls({ d, onCmd }) {
  const [vmpp, setVmpp] = useState("6.23");
  const mode = d?.mppt_mode || "";

  return (
    <>
      <CtrlRow label="MPPT mode">
        <Btn variant={mode === "fixed" ? "active" : ""} onClick={() => onCmd({ mppt_mode: "fixed" })}>
          Fixed
        </Btn>
        <Btn variant={mode === "web" ? "active" : ""} onClick={() => onCmd({ mppt_mode: "web" })}>
          Web
        </Btn>
        <Btn variant={mode === "po" ? "active" : ""} onClick={() => onCmd({ mppt_mode: "po" })}>
          P&amp;O
        </Btn>
      </CtrlRow>

      <CtrlRow label="Vmpp target">
        <input
          className="smps-num-input"
          type="number"
          value={vmpp}
          step="0.01"
          min="3"
          max="9"
          onChange={(e) => setVmpp(e.target.value)}
        />
        <span className="smps-unit-hint">V</span>
        <Btn onClick={() => onCmd({ vmpp_target: parseFloat(vmpp), mppt_mode: "fixed" })}>
          Apply Fixed
        </Btn>
      </CtrlRow>

      <div className="smps-quickbar">
        <Btn onClick={() => onCmd({ enable: 1 })}>Enable</Btn>
        <Btn variant="danger" onClick={() => onCmd({ enable: 0 })}>
          Disable
        </Btn>
        <Btn variant="warn" onClick={() => onCmd({ reset_trip: 1 })}>
          Reset Trip
        </Btn>
      </div>
    </>
  );
}

function GridControls({ onCmd }) {
  const [vbt, setVbt] = useState(String(GRID_TARGET_DEFAULT));
  const [imax, setImax] = useState("2.0");

  return (
    <>
      <CtrlRow label="vb_target">
        <input
          className="smps-num-input"
          type="number"
          value={vbt}
          step="0.05"
          min="0"
          max="12"
          onChange={(e) => setVbt(e.target.value)}
        />
        <span className="smps-unit-hint">V</span>
        <Btn onClick={() => onCmd({ vb_target: parseFloat(vbt) })}>Apply</Btn>
      </CtrlRow>

      <CtrlRow label="i_ref_max">
        <input
          className="smps-num-input"
          type="number"
          value={imax}
          step="0.1"
          min="0"
          max="2"
          onChange={(e) => setImax(e.target.value)}
        />
        <span className="smps-unit-hint">A</span>
        <Btn onClick={() => onCmd({ i_ref_max: parseFloat(imax) })}>Apply</Btn>
      </CtrlRow>

      <div className="smps-quickbar">
        <Btn onClick={() => onCmd({ enable: 1, vb_target: GRID_TARGET_DEFAULT })}>
          On ({GRID_TARGET_DEFAULT}V)
        </Btn>
        <Btn variant="danger" onClick={() => onCmd({ vb_target: 0 })}>
          Off
        </Btn>
        <Btn variant="warn" onClick={() => onCmd({ reset_trip: 1 })}>
          Reset Trip
        </Btn>
      </div>
    </>
  );
}

function ExportControls({ onCmd }) {
  const [vbt, setVbt] = useState(String(EXPORT_TARGET_DEFAULT));
  const [imax, setImax] = useState("2.0");

  return (
    <>
      <CtrlRow label="vb_target">
        <input
          className="smps-num-input"
          type="number"
          value={vbt}
          step="0.05"
          min="0"
          max="12"
          onChange={(e) => setVbt(e.target.value)}
        />
        <span className="smps-unit-hint">V</span>
        <Btn onClick={() => onCmd({ vb_target: parseFloat(vbt) })}>Apply</Btn>
      </CtrlRow>

      <CtrlRow label="i_ref_max">
        <input
          className="smps-num-input"
          type="number"
          value={imax}
          step="0.1"
          min="0"
          max="2"
          onChange={(e) => setImax(e.target.value)}
        />
        <span className="smps-unit-hint">A</span>
        <Btn onClick={() => onCmd({ i_ref_max: parseFloat(imax) })}>Apply</Btn>
      </CtrlRow>

      <div className="smps-quickbar">
        <Btn onClick={() => onCmd({ enable: 1, vb_target: EXPORT_TARGET_DEFAULT })}>
          On ({EXPORT_TARGET_DEFAULT}V)
        </Btn>
        <Btn variant="danger" onClick={() => onCmd({ vb_target: 0 })}>
          Off
        </Btn>
        <Btn variant="warn" onClick={() => onCmd({ reset_trip: 1 })}>
          Reset Trip
        </Btn>
      </div>
    </>
  );
}

function CapCycleTest({ onCmd, data }) {
  const [chargeI, setChargeI] = useState("0.20");
  const [dischargeI, setDischargeI] = useState("0.20");
  const [holdS, setHoldS] = useState(0);
  const [running, setRunning] = useState(false);
  const [samples, setSamples] = useState([]);

  useEffect(() => {
    if (!data) return;

    const phase = data.test_phase || "idle";

    if (running || phase !== "idle") {
      setSamples((prev) => {
        const next = [
          ...prev,
          {
            t_ms: data.test_t_ms || 0,
            phase,
            v_cap: data.v_cap,
            v_bus: data.vb_bus,
            iL: data.iL,
            p_bus_W: data.p_cap,
            E_in_J: data.test_E_in_J,
            E_out_J: data.test_E_out_J,
            i_cmd_eff: data.i_cmd_eff,
          },
        ];
        return next.slice(-2000);
      });
    }

    if (phase === "done" || phase === "aborted") {
      setRunning(false);
    }
  }, [data, running]);

  const start = () => {
    const ic = parseFloat(chargeI);
    const id = parseFloat(dischargeI);
    if (!Number.isFinite(ic) || ic <= 0 || !Number.isFinite(id) || id <= 0) {
      window.alert("Enter valid charge / discharge currents.");
      return;
    }
    setSamples([]);
    setRunning(true);
    onCmd({
      test_start: 1,
      test_i_charge: ic,
      test_i_discharge: id,
      test_hold_s: Number(holdS) || 0,
    });
  };

  const abort = () => {
    onCmd({ test_abort: 1 });
  };

  const downloadCsv = () => {
    if (!samples.length) return;

    const header = "t_ms,phase,v_cap,v_bus,iL,p_bus_W,E_in_J,E_out_J,i_cmd_eff";
    const rows = samples.map((s) =>
      [
        s.t_ms ?? "",
        s.phase ?? "",
        s.v_cap ?? "",
        s.v_bus ?? "",
        s.iL ?? "",
        s.p_bus_W ?? "",
        s.E_in_J ?? "",
        s.E_out_J ?? "",
        s.i_cmd_eff ?? "",
      ].join(",")
    );

    const blob = new Blob([[header, ...rows].join("\n") + "\n"], {
      type: "text/csv;charset=utf-8",
    });

    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    a.href = url;
    a.download = `cap_cycle_${ts}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const phase = data?.test_phase || "idle";
  const f = (x, d = 2) => (typeof x === "number" && Number.isFinite(x) ? x.toFixed(d) : "—");
  const pct = (x) => (typeof x === "number" && Number.isFinite(x) ? (100 * x).toFixed(1) : "—");

  return (
    <div className="smps-cycle">
      <div className="smps-cycle-title">CYCLE TEST</div>

      <CtrlRow label="Charge I">
        <input
          className="smps-num-input"
          type="number"
          step="0.05"
          min="0.05"
          max="0.60"
          value={chargeI}
          onChange={(e) => setChargeI(e.target.value)}
        />
        <span className="smps-unit-hint">A</span>
      </CtrlRow>

      <CtrlRow label="Discharge I">
        <input
          className="smps-num-input"
          type="number"
          step="0.05"
          min="0.05"
          max="0.60"
          value={dischargeI}
          onChange={(e) => setDischargeI(e.target.value)}
        />
        <span className="smps-unit-hint">A</span>
      </CtrlRow>

      <CtrlRow label="Hold">
        <input
          className="smps-slider"
          type="range"
          min="0"
          max="600"
          step="1"
          value={holdS}
          onChange={(e) => setHoldS(parseFloat(e.target.value))}
        />
        <span className="smps-now">{holdS} s</span>
      </CtrlRow>

      <div className="smps-quickbar">
        <Btn onClick={start} disabled={running}>
          Start cycle
        </Btn>
        <Btn variant="danger" onClick={abort} disabled={!running}>
          Abort
        </Btn>
        <Btn onClick={downloadCsv} disabled={!samples.length}>
          Download CSV
        </Btn>
      </div>

      <div className="smps-cycle-status">
        <b>Phase:</b> {phase} · <b>t:</b> {f((data?.test_t_ms || 0) / 1000, 1)} s ·{" "}
        <b>samples:</b> {samples.length}
        <br />
        <b>E_in:</b> {f(data?.test_E_in_J)} J · <b>E_out:</b> {f(data?.test_E_out_J)} J
        {phase === "done" && (
          <>
            <br />
            <b>η_charge:</b> {pct(data?.test_eta_charge)}% · <b>η_discharge:</b>{" "}
            {pct(data?.test_eta_discharge)}% · <b>η_roundtrip:</b>{" "}
            {pct(data?.test_eta_roundtrip)}%
          </>
        )}
      </div>
    </div>
  );
}

function CapControls({ d, onCmd }) {
  const [icmd, setIcmd] = useState(0);

  const apply = (v) => {
    setIcmd(v);
    onCmd({ i_cmd: v });
  };

  return (
    <>
      <CtrlRow label="i_cmd">
        <input
          className="smps-slider"
          type="range"
          min="-0.60"
          max="0.60"
          step="0.01"
          value={icmd}
          onChange={(e) => setIcmd(parseFloat(e.target.value))}
        />
        <span className="smps-now">
          {icmd >= 0 ? "+" : ""}
          {icmd.toFixed(2)} A
        </span>
        <Btn onClick={() => onCmd({ i_cmd: icmd })}>Apply</Btn>
      </CtrlRow>

      <div className="smps-ctrl-hint">+ charges cap · − discharges cap · ±0.60 A max</div>

      <div className="smps-quickbar">
        <Btn onClick={() => apply(0.2)}>Charge 0.2A</Btn>
        <Btn onClick={() => apply(-0.2)}>Discharge 0.2A</Btn>
        <Btn onClick={() => apply(0)}>Stop</Btn>
      </div>

      <div className="smps-quickbar">
        <Btn onClick={() => onCmd({ enable: 1 })}>Enable</Btn>
        <Btn variant="danger" onClick={() => onCmd({ enable: 0, i_cmd: 0 })}>
          Disable
        </Btn>
        <Btn variant="warn" onClick={() => onCmd({ reset_trip: 1 })}>
          Reset Trip
        </Btn>
      </div>

      <CapCycleTest data={d} onCmd={onCmd} />
    </>
  );
}

function LEDControls({ onCmd }) {
  const [p, setP] = useState({ red: 0, yel: 0, grn: 0 });

  const update = (ch, v) => setP((prev) => ({ ...prev, [ch]: v }));

  return (
    <>
      {["red", "yel", "grn"].map((c) => (
        <CtrlRow key={c} label={`p_${c}`}>
          <input
            className="smps-slider"
            type="range"
            min="0"
            max="3"
            step="0.05"
            value={p[c]}
            onChange={(e) => update(c, parseFloat(e.target.value))}
          />
          <span className="smps-now">{p[c].toFixed(2)} W</span>
          <Btn onClick={() => onCmd({ [`p_${c}`]: p[c] })}>Apply</Btn>
        </CtrlRow>
      ))}

      <div className="smps-quickbar">
        <Btn
          onClick={() => {
            setP({ red: 0, yel: 0, grn: 0 });
            onCmd({ p_red: 0, p_yel: 0, p_grn: 0 });
          }}
        >
          All Off
        </Btn>
        <Btn onClick={() => onCmd({ enable: 1 })}>Enable</Btn>
        <Btn variant="warn" onClick={() => onCmd({ reset_trip: 1 })}>
          Reset Trip
        </Btn>
      </div>
    </>
  );
}

// ─── Module card ─────────────────────────────────────────────────────────────

function ModuleCard({ role, data, status, history, host, onCmd, lastBusVoltage, theme = "dark" }) {
  const isLightTheme = theme === "light";
  const color = isLightTheme
    ? {
        pv: "#1f7d3b",
        grid: "#2e5f93",
        export: "#7a4cb8",
        cap: "#2f7f7a",
        led: "#8b6a21",
      }[role]
    : ROLE_COLORS[role];
  const lines = (MOD_CHART_LINES[role] || []).map((line) => {
    const darker = {
      "#6fb86f": "#1f7d3b",
      "#e6e6e6": "#5b6678",
      "#5a8ec9": "#2e5f93",
      "#f5c84b": "#9b6b00",
      "#d9a85a": "#8b6a21",
      "#b67ad9": "#7a4cb8",
      "#5ec9c0": "#2f7f7a",
      "#e07070": "#b63a59",
      "#d9c95a": "#9b7f24",
    };

    return isLightTheme ? { ...line, color: darker[line.color] || line.color } : line;
  });
  const axisColor = isLightTheme ? "#38475f" : "#555";
  const tooltipBackground = isLightTheme ? "#ffffff" : "#0d0d0d";
  const tooltipBorder = isLightTheme ? "#cfd9e8" : "#2c2c2c";
  const tooltipText = isLightTheme ? "#1a2333" : "#e6e6e6";

  const stats = {
    pv: <PVStats d={data} />,
    grid: <GridStats d={data} />,
    export: <ExportStats d={data} />,
    cap: <CapStats d={data} />,
    led: <LEDStats d={data} lastBusVoltage={lastBusVoltage} />,
  }[role];

  const controls = {
    pv: <PVControls d={data} onCmd={onCmd} />,
    grid: <GridControls onCmd={onCmd} />,
    export: <ExportControls onCmd={onCmd} />,
    cap: <CapControls d={data} onCmd={onCmd} />,
    led: <LEDControls onCmd={onCmd} />,
  }[role];

  const netMode = data?.net_mode || "offline";
  const wifi = data?.wifi_connected ? "connected" : "disconnected";
  const backend = data?.backend_post_ok ? "ok" : "fail";

  return (
    <div
      className={[
        "smps-card",
        status?.online === false ? "smps-card-offline" : "",
        data?.trip ? "smps-card-trip" : "",
      ].join(" ")}
      style={{ borderTopColor: color }}
    >
      <div className="smps-card-header">
        <span className="smps-card-title" style={{ color }}>
          {ROLE_LABELS[role]}
        </span>

        <span className="smps-card-pills">
          {role === "pv" && data?.mppt_mode && (
            <span className={data.mppt_mode === "web" ? "smps-pill smps-pill-sun" : "smps-pill"}>
              {data.mppt_mode.toUpperCase()}
            </span>
          )}
          <StatusPill d={data} status={status} />
        </span>
      </div>

      <div className="smps-mod-host">host: {firstHost(host) || "—"}</div>
      <StatusLine status={status} />

      {data?.trip && (
        <div className="smps-trip-banner">
          <b>TRIP</b> · reason: <b>{data.trip_reason || "unknown"}</b> · auto-recovers once fault clears
        </div>
      )}

      {data ? (
        <>
          <div className={role === "led" ? "" : "smps-stats-grid"}>{stats}</div>

          <div className="smps-netline">
            net {netMode} · wifi {wifi} · backend {backend}
          </div>
        </>
      ) : (
        <div className="smps-offline-msg">No telemetry — module offline</div>
      )}

      <div className="smps-mini-chart">
        <ResponsiveContainer width="100%" height={112}>
          <LineChart data={history} margin={{ top: 6, right: 10, bottom: 0, left: -18 }}>
            <XAxis hide />
            <YAxis tick={{ fontSize: 9, fill: axisColor }} width={36} />
            <Tooltip
              contentStyle={{
                background: tooltipBackground,
                border: `1px solid ${tooltipBorder}`,
                borderRadius: 5,
                fontSize: 11,
              }}
              itemStyle={{ color: tooltipText }}
            />
            {lines.map((l) => (
              <Line
                key={l.key}
                type="linear"
                dataKey={l.key}
                name={l.label}
                stroke={l.color}
                strokeWidth={1.5}
                strokeDasharray={l.dashed ? "4 3" : undefined}
                dot={false}
                connectNulls={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>

        <div className="smps-mini-legend">
          {lines.map((l) => (
            <span key={l.key}>
              <span className="smps-swatch" style={{ background: l.color }} />
              {l.label}
            </span>
          ))}
        </div>
      </div>

      <div className="smps-controls">{controls}</div>
    </div>
  );
}

// ─── Root component ──────────────────────────────────────────────────────────

export default function SmpsModules({ apiBase = "", theme = "dark" }) {
  const [hosts, setHosts] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("smps-module-hosts") || "null") || { ...DEFAULT_HOSTS };
    } catch {
      return { ...DEFAULT_HOSTS };
    }
  });

  const [showHosts, setShowHosts] = useState(false);
  const [showAlgo, setShowAlgo] = useState(false);
  const [hostMsg, setHostMsg] = useState("");
  const [modules, setModules] = useState({});
  const [statuses, setStatuses] = useState({});
  const [lastUpdated, setLastUpdated] = useState(null);

  const histRef = useRef(Object.fromEntries(ROLES.map((r) => [r, []])));
  const globalHistRef = useRef([]);

  const [hist, setHist] = useState(Object.fromEntries(ROLES.map((r) => [r, []])));
  const [globalHist, setGlobalHist] = useState([]);

  const vbus = useMemo(() => getBusVoltage(modules), [modules]);

  const saveHosts = async () => {
    localStorage.setItem("smps-module-hosts", JSON.stringify(hosts));

    try {
      const res = await fetch(`${apiBase}/algo/module-hosts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ hosts }),
      });

      if (res.ok) {
        setHostMsg("Saved backend hosts");
      } else {
        const body = await res.text();
        console.warn("Failed to save backend hosts", res.status, body);
        setHostMsg("Saved locally, backend update failed");
      }
    } catch (e) {
      console.warn("Failed to save backend hosts", e.message);
      setHostMsg("Saved locally, backend update failed");
    }

    setShowHosts(false);
    window.setTimeout(() => setHostMsg(""), 1800);
  };

  const sendCmd = async (role, payload) => {
    try {
      const res = await fetch(`${apiBase}/modules/cmd/${role}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) return true;
      console.warn(`[smps] backend cmd to ${role} failed:`, res.status, await res.text());
    } catch (e) {
      console.warn(`[smps] backend cmd to ${role} failed:`, e.message);
    }

    return false;
  };

  const sendAlgorithmControl = async (enable) => {
    await Promise.all(ALGORITHM_ROLES.map((role) => sendCmd(role, { enable: enable ? 1 : 0 })));
  };

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const [latestRes, statusRes] = await Promise.all([
          fetch(`${apiBase}/modules/latest`, { cache: "no-store" }),
          fetch(`${apiBase}/modules/status`, { cache: "no-store" }),
        ]);

        if (!latestRes.ok) return;

        const data = await latestRes.json();
        const statusData = statusRes.ok ? await statusRes.json() : {};

        if (cancelled) return;

        setModules(data);
        setStatuses(statusData);
        setLastUpdated(new Date());

        ROLES.forEach((role) => {
          const h = histRef.current[role];
          h.push({
            t: new Date().toLocaleTimeString(),
            ...(data[role] || {}),
          });
          while (h.length > HIST_MAX) h.shift();
        });

        globalHistRef.current.push(makeGlobalSample(data));
        while (globalHistRef.current.length > HIST_MAX) globalHistRef.current.shift();

        setHist(Object.fromEntries(ROLES.map((r) => [r, [...histRef.current[r]]])));
        setGlobalHist([...globalHistRef.current]);
      } catch {
        // backend down / network unavailable
      }
    }

    async function loadBackendHosts() {
      try {
        const res = await fetch(`${apiBase}/algo/module-hosts`, { cache: "no-store" });
        if (!res.ok) return;
        const data = await res.json();
        if (data && typeof data.hosts === "object") {
          setHosts((prev) => ({ ...prev, ...data.hosts }));
        }
      } catch (e) {
        console.warn("Failed to load backend hosts", e.message);
      }
    }

    poll();
    loadBackendHosts();
    const id = setInterval(poll, 1000);

    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [apiBase]);

  return (
    <div className="smps-root">
      <div className="smps-top-actions">
        <button className="smps-host-toggle" onClick={() => setShowAlgo((v) => !v)}>
          {showAlgo ? "Hide Algorithm Control" : "Algorithm Control"}
        </button>

        <button className="smps-host-toggle" onClick={() => setShowHosts((v) => !v)}>
          {showHosts ? "Hide host config" : "Configure module hosts"}
        </button>

        <span className="smps-last-updated">
          latest: {lastUpdated ? lastUpdated.toLocaleTimeString() : "—"}
        </span>
      </div>

      {showAlgo && (
        <div className="smps-algo-panel">
          <div className="smps-ctrl-row">
            <span className="smps-ctrl-label">Global Control</span>
            <div className="smps-quickbar">
              <Btn onClick={() => sendAlgorithmControl(true)}>Enable Algorithms</Btn>
              <Btn variant="danger" onClick={() => sendAlgorithmControl(false)}>
                Disable Algorithms
              </Btn>
            </div>
          </div>
        </div>
      )}

      {showHosts && (
        <div className="smps-host-panel">
          <div className="smps-host-hint">
            Hostname or IP for each Pico HTTP server. Saved hosts are sent to the backend proxy and used when sending commands.
          </div>

          <div className="smps-host-grid">
            {ROLES.map((r) => (
              <div key={r} className="smps-host-row">
                <label>{r}</label>
                <input
                  value={hosts[r] || ""}
                  placeholder={DEFAULT_HOSTS[r]}
                  onChange={(e) => setHosts((h) => ({ ...h, [r]: e.target.value }))}
                />
              </div>
            ))}
          </div>

          <button className="smps-host-save" onClick={saveHosts}>
            Save backend hosts
          </button>
          {hostMsg && <div className="smps-host-msg">{hostMsg}</div>}
        </div>
      )}

      <BusGauge vbus={vbus} />
      <GlobalChart data={globalHist} theme={theme} />

      <div className="smps-grid">
        {ROLES.map((role) => (
          <ModuleCard
            key={role}
            role={role}
            data={modules[role] || null}
            status={statuses[role] || null}
            history={hist[role] || []}
            host={hosts[role] || ""}
            onCmd={(payload) => sendCmd(role, payload)}
            lastBusVoltage={vbus}
            theme={theme}
          />
        ))}
      </div>
    </div>
  );
}