import { useEffect, useRef, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
} from "recharts";

const ROLES = ["pv", "grid", "export", "cap", "led"];
const HIST_MAX = 60;
const OVERVIEW_LIMIT = 60;
const STALE_AFTER_MS = 5000;
const TICK_SECONDS = 5;

const ROLE_LABELS = {
  pv: "PV",
  grid: "Grid",
  export: "Export",
  cap: "Capacitor",
  led: "LED Load",
};

const ROLE_COLORS = {
  pv: "#00e676",
  grid: "#00f0ff",
  export: "#b67ad9",
  cap: "#5ec9c0",
  led: "#ff9100",
};

const ROLE_LINES = {
  pv: [
    { key: "v_panel", name: "Vpv", color: "#00e676" },
    { key: "vb_bus", name: "Vbus", color: "#00f0ff" },
    { key: "p_panel", name: "Ppv", color: "#ffc800" },
  ],
  grid: [
    { key: "vb_bus", name: "Vbus", color: "#00f0ff" },
    { key: "v_psu", name: "Vpsu", color: "#ffc800" },
    { key: "p_import", name: "P import", color: "#ff9100" },
  ],
  export: [
    { key: "vb_bus", name: "Vbus", color: "#00f0ff" },
    { key: "v_resistor", name: "Vres", color: "#b67ad9" },
    { key: "p_dissip", name: "P dissip", color: "#ff4d6d" },
  ],
  cap: [
    { key: "v_cap", name: "Vcap", color: "#5ec9c0" },
    { key: "vb_bus", name: "Vbus", color: "#00f0ff" },
    { key: "p_cap", name: "Pcap", color: "#ffc800" },
  ],
  led: [
    { key: "p_red", name: "Red", color: "#ff4d6d" },
    { key: "p_yel", name: "Yellow", color: "#ffc800" },
    { key: "p_grn", name: "Green", color: "#00e676" },
  ],
};

function getModuleStatus(module) {
  if (!module) return "offline";

  const t = new Date(module.timestamp).getTime();
  if (!Number.isFinite(t)) return "offline";

  if (Date.now() - t > STALE_AFTER_MS) return "stale";
  if (module.trip) return "trip";
  if (module.wd) return "watchdog";
  if (!module.enable) return "disabled";

  return "online";
}

function fmt(v, digits = 2) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  if (typeof v === "number") return v.toFixed(digits);
  return String(v);
}

function StatusBadge({ status }) {
  return (
    <span className={`module-status-label module-status-text-${status}`}>
      <span className={`module-status-dot module-status-${status}`} />
      {status}
    </span>
  );
}

function toNumber(value, fallback = 0) {
  const num = Number(value);
  return Number.isFinite(num) ? num : fallback;
}

function getJobWindow(job) {
  const start = Number(job?.tick_start ?? job?.start);
  const end = Number(job?.tick_end ?? job?.end);
  if (!Number.isFinite(start) || !Number.isFinite(end)) return null;
  return { start, end };
}

function getDeferrableDemand(snapshot) {
  const tick = Number(snapshot?.tick);
  if (!Number.isFinite(tick)) return 0;

  const jobs = Array.isArray(snapshot?.deferables) ? snapshot.deferables : [];
  return jobs.reduce((sum, job) => {
    const window = getJobWindow(job);
    if (!window) return sum;
    if (tick < window.start || tick > window.end) return sum;
    return sum + Math.max(0, toNumber(job?.energy));
  }, 0);
}

function getDeferrableSeriesValue(snapshot, index) {
  const tick = Number(snapshot?.tick);
  if (!Number.isFinite(tick)) return 0;

  const jobs = Array.isArray(snapshot?.deferables) ? snapshot.deferables : [];
  const job = jobs[index];
  if (!job) return 0;

  const window = getJobWindow(job);
  if (!window) return 0;
  if (tick < window.start || tick > window.end) return 0;
  return Math.max(0, toNumber(job?.energy));
}

function buildOverviewSeries(gridSnapshots, pvHistory, gridHistory, exportHistory) {
  const pvByTick = new Map();
  const gridByTick = new Map();
  const exportByTick = new Map();

  pvHistory.forEach((row) => {
    const tick = Number(row?.web_tick);
    if (Number.isFinite(tick)) pvByTick.set(tick, row);
  });
  gridHistory.forEach((row) => {
    const tick = Number(row?.web_tick);
    if (Number.isFinite(tick)) gridByTick.set(tick, row);
  });
  exportHistory.forEach((row) => {
    const tick = Number(row?.web_tick);
    if (Number.isFinite(tick)) exportByTick.set(tick, row);
  });

  let cumulativeImportJ = 0;
  let cumulativeExportJ = 0;

  return gridSnapshots.map((snapshot) => {
    const tick = Number(snapshot?.tick);
    const pvRow = pvByTick.get(tick);
    const gridRow = gridByTick.get(tick);
    const exportRow = exportByTick.get(tick);

    const importPower = Math.max(0, toNumber(gridRow?.p_import));
    const exportPower = Math.max(0, toNumber(exportRow?.p_dissip));
    cumulativeImportJ += importPower * TICK_SECONDS;
    cumulativeExportJ += exportPower * TICK_SECONDS;

    return {
      tick,
      pv_power_W: Math.max(0, toNumber(pvRow?.p_panel)),
      instant_demand_W: Math.max(0, toNumber(snapshot?.instant_demand)),
      total_deferrable_J: getDeferrableDemand(snapshot),
      deferrable_1_J: getDeferrableSeriesValue(snapshot, 0),
      deferrable_2_J: getDeferrableSeriesValue(snapshot, 1),
      deferrable_3_J: getDeferrableSeriesValue(snapshot, 2),
      cumulative_import_J: cumulativeImportJ,
      cumulative_export_J: cumulativeExportJ,
    };
  });
}

function OverviewGraphCard({ data }) {
  const latest = data[data.length - 1];

  return (
    <section className="card smps-plot-card smps-overview-card smps-overview-graph-card">
      <div className="smps-plot-header">
        <div>
          <div className="smps-plot-title" style={{ color: "#00f0ff" }}>
            System Dispatch Overview
          </div>
          <div className="smps-plot-sub">
            PV, demand, three deferrable demands, and cumulative grid energy versus tick.
          </div>
        </div>
      </div>

      <div className="smps-plot-stats smps-overview-stats">
        <div className="smps-plot-stat">
          <p>PV Power</p>
          <h3>{latest ? `${fmt(latest.pv_power_W)} W` : "—"}</h3>
        </div>
        <div className="smps-plot-stat">
          <p>Demand</p>
          <h3>{latest ? `${fmt(latest.instant_demand_W)} W` : "—"}</h3>
        </div>
        <div className="smps-plot-stat">
          <p>Total Deferrable</p>
          <h3>{latest ? `${fmt(latest.total_deferrable_J)} J` : "—"}</h3>
        </div>
        <div className="smps-plot-stat">
          <p>Import / Export</p>
          <h3>{latest ? `${fmt(latest.cumulative_import_J, 0)} / ${fmt(latest.cumulative_export_J, 0)} J` : "—"}</h3>
        </div>
      </div>

      <div className="smps-plot-wrapper">
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={data}>
            <XAxis
              dataKey="tick"
              stroke="#a69ec4"
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              yAxisId="power"
              stroke="#a69ec4"
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={48}
            />
            <YAxis
              yAxisId="energy"
              orientation="right"
              stroke="#a69ec4"
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={56}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#14052e",
                borderColor: "#27134d",
                borderRadius: "8px",
              }}
              labelStyle={{ color: "#ffffff" }}
            />
            <Legend wrapperStyle={{ color: "#a69ec4", fontSize: 12 }} />
            <Line yAxisId="power" type="monotone" dataKey="pv_power_W" name="PV power" stroke="#00e676" strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line yAxisId="power" type="monotone" dataKey="instant_demand_W" name="Demand" stroke="#00f0ff" strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line yAxisId="power" type="monotone" dataKey="deferrable_1_J" name="Deferrable 1" stroke="#ffc800" strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line yAxisId="power" type="monotone" dataKey="deferrable_2_J" name="Deferrable 2" stroke="#ff9100" strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line yAxisId="power" type="monotone" dataKey="deferrable_3_J" name="Deferrable 3" stroke="#5ec9c0" strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line yAxisId="energy" type="monotone" dataKey="cumulative_export_J" name="Cumulative export" stroke="#ff4d6d" strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line yAxisId="energy" type="monotone" dataKey="cumulative_import_J" name="Cumulative import" stroke="#b67ad9" strokeWidth={2} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

// ---- Algorithm tab strip ----
// Reads /algo/list, renders one tab per registered algorithm, POSTs
// /algo/active on click. Algorithms are added/removed by editing
// buysellalgorithm/registry.py — the frontend is data-driven.
function AlgorithmTabs({ apiBase, activeId, onSwitch, switching, switchMsg }) {
  const [algos, setAlgos] = useState([]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch(`${apiBase}/algo/list`);
        if (!res.ok) return;
        const data = await res.json();
        if (!cancelled) setAlgos(Array.isArray(data?.algorithms) ? data.algorithms : []);
      } catch (err) {
        console.error("Failed to load algorithm list", err);
      }
    }
    load();
    const id = setInterval(load, 5000);
    return () => { cancelled = true; clearInterval(id); };
  }, [apiBase]);

  if (algos.length === 0) {
    return <div className="algo-tabs-empty">loading algorithms…</div>;
  }

  return (
    <div className="algo-tabs-wrap">
      <div className="algo-tabs">
        {algos.map((a) => {
          const isActive = a.id === activeId;
          return (
            <button
              key={a.id}
              className={`algo-tab ${isActive ? "active" : ""}`}
              onClick={() => !isActive && !switching && onSwitch(a.id)}
              disabled={switching}
              title={a.description}
            >
              <span className="algo-tab-dot">{isActive ? "●" : "○"}</span>
              <span className="algo-tab-label">{a.name}</span>
            </button>
          );
        })}
      </div>
      {switchMsg && <div className="algo-tabs-msg">{switchMsg}</div>}
    </div>
  );
}


// ---- Smart V1 (and future algos) extras panel ----
// Renders the algorithm-specific diagnostics dict (cmd.algo_extras) as a
// glanceable grid. Hidden when the active algorithm provides no extras.
function AlgoExtrasPanel({ naive }) {
  const extras = naive?.diagnostics?.algo_extras;
  if (!extras || Object.keys(extras).length === 0) return null;

  const panelStyle = {
    border: "1px solid rgba(128,128,128,0.25)",
    background: "rgba(127,127,127,0.08)",
    borderRadius: 6,
    padding: "8px 10px",
    fontSize: 13,
    color: "inherit",
    marginTop: 10,
  };
  const mutedStyle = { color: "rgba(127,127,127,0.85)" };

  // Pretty-print the Smart V1 shape if recognised, otherwise dump generically.
  const isSmartV1 =
    "cap_action_reason" in extras || "forecast_now" in extras;

  if (isSmartV1) {
    const fn = extras.forecast_now || {};
    return (
      <div style={panelStyle}>
        <div style={{ fontWeight: 600, marginBottom: 6 }}>
          Smart V1 forecast & decision
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 6 }}>
          <div>
            <div style={mutedStyle}>cap action</div>
            <strong>{extras.cap_action_reason || "—"}</strong>
          </div>
          <div>
            <div style={mutedStyle}>target W (bus)</div>
            <strong>{extras.cap_action_target_W?.toFixed?.(2) ?? "—"}</strong>
          </div>
          <div>
            <div style={mutedStyle}>arb gain (¢/J)</div>
            <strong>{extras.cap_arb_gain?.toFixed?.(1) ?? "—"}</strong>
          </div>
          <div>
            <div style={mutedStyle}>horizon (ticks)</div>
            <strong>{extras.cap_arb_horizon_t ?? "—"}</strong>
          </div>
        </div>
        <div style={{ marginTop: 8, ...mutedStyle, fontSize: 12 }}>
          forecast at this tick — sell <strong>{fn.sell_price ?? "—"}</strong>  ·
          buy <strong>{fn.buy_price ?? "—"}</strong> ·
          PV <strong>{fn.pv_bus_W ?? "—"} W</strong> ·
          demand <strong>{fn.demand_W ?? "—"} W</strong>
        </div>
      </div>
    );
  }

  // Generic fallback — list keys/values.
  return (
    <div style={panelStyle}>
      <div style={{ fontWeight: 600, marginBottom: 6 }}>Algorithm extras</div>
      <pre style={{ margin: 0, fontSize: 11, overflowX: "auto" }}>
        {JSON.stringify(extras, null, 2)}
      </pre>
    </div>
  );
}


function NaiveDispatchCard({
  apiBase,
  naive,
  applyBusy,
  applyMsg,
  onApply,
  showHostConfig,
  onToggleHostConfig,
  backendHosts,
  onHostsChange,
  onSaveHosts,
  hostsMsg,
  autoApply,
  onAutoApplyChange,
  cooldownSec,
  onCooldownChange,
  activeAlgoId,
  onSwitchAlgo,
  switchingAlgo,
  switchAlgoMsg,
}) {
  const algoLabel = naive?.algo_name || naive?.diagnostics?.algo_id || activeAlgoId || "—";
  return (
    <section className="card smps-plot-card smps-overview-card">
      <div className="card-header">
        <span className="icon-green">●</span> Algorithm Dispatch
        <span style={{ marginLeft: 8, fontSize: 12, color: "rgba(127,127,127,0.85)", fontWeight: 400 }}>
          · {algoLabel}
        </span>
      </div>

      <AlgorithmTabs
        apiBase={apiBase}
        activeId={activeAlgoId}
        onSwitch={onSwitchAlgo}
        switching={switchingAlgo}
        switchMsg={switchAlgoMsg}
      />

      <NaiveDebugPanel naive={naive} />

      <AlgoExtrasPanel naive={naive} />

      <div className="naive-toolbar">
        <label className="naive-auto-label">
          <input
            type="checkbox"
            checked={autoApply}
            onChange={(e) => onAutoApplyChange(e.target.checked)}
          />
          Auto apply
        </label>

        <label className="naive-auto-label">
          Cooldown
          <input
            className="naive-cooldown-input"
            type="number"
            min="1"
            step="1"
            value={cooldownSec}
            onChange={(e) => onCooldownChange(Number(e.target.value) || 1)}
          />
          s
        </label>

        <button className="naive-host-toggle" onClick={onToggleHostConfig}>
          {showHostConfig ? "Hide backend hosts" : "Edit backend hosts"}
        </button>
      </div>

      {showHostConfig && (
        <div className="naive-host-panel">
          <div className="naive-host-grid">
            <label>
              cap
              <input
                value={backendHosts.cap}
                onChange={(e) => onHostsChange({ ...backendHosts, cap: e.target.value })}
                placeholder="http://192.168.137.23"
              />
            </label>
            <label>
              led
              <input
                value={backendHosts.led}
                onChange={(e) => onHostsChange({ ...backendHosts, led: e.target.value })}
                placeholder="http://192.168.137.24"
              />
            </label>
          </div>
          <div className="naive-host-actions">
            <button className="naive-host-save" onClick={onSaveHosts}>Save backend hosts</button>
            {hostsMsg && <span className="naive-host-msg">{hostsMsg}</span>}
          </div>
        </div>
      )}

      <button className="btn-pink" onClick={() => onApply()} disabled={applyBusy || !naive}>
        {applyBusy ? "Applying..." : "Apply to all 4 modules (cap, led, grid, export)"}
      </button>

      {applyMsg && <p className="naive-apply-msg">{applyMsg}</p>}

      <RunCostPanel       apiBase={apiBase} />
      <ServerAutoLoopPanel apiBase={apiBase} />
      <DataExportPanel    apiBase={apiBase} />
    </section>
  );
}


// ---- "What is the algorithm doing right now?" debug panel ----
// Reads `naive.diagnostics` (populated by buysellalgorithm/naive.py's
// commands_to_diagnostics) and renders a compact, glanceable view.
function NaiveDebugPanel({ naive }) {
  const d   = naive?.diagnostics || {};
  const inp = naive?.inputs || {};
  const fmt = (v, n = 2, suf = "") =>
    typeof v === "number" ? `${v.toFixed(n)}${suf}` : "—";

  const regime = d.regime || naive?.regime || "—";
  const regimeColor =
    regime === "surplus" ? "#1f9d55" :
    regime === "deficit" ? "#d4351c" :
    regime === "idle"    ? "#666"    : "#aaa";

  const active = Array.isArray(d.active_deferrables) ? d.active_deferrables : [];
  const clamp  = d.cap_clamped || "";
  const clampLabel = {
    ceiling: "cap at ceiling (≥15.7 V — refusing charge)",
    floor:   "cap at floor (≤10.5 V — SMPS can't transfer)",
    taper:   "cap in soft-taper region (10.5–11.0 V — limited discharge)",
    i_max:   "cap at |i|=0.6 A current limit",
    "":      "",
  }[clamp];

  // Theme-aware colors: semi-transparent so we pick up whatever bg colour
  // the page is using (dark or light) without fighting it.
  const panelStyle = {
    border: "1px solid rgba(128,128,128,0.25)",
    background: "rgba(127,127,127,0.08)",
    borderRadius: 6,
    padding: "8px 10px",
    fontSize: 13,
    color: "inherit",
  };
  const mutedStyle  = { color: "rgba(127,127,127,0.85)" };
  const accentGreen = "#3fc380";
  const accentRed   = "#ef5350";

  return (
    <div className="naive-debug" style={{ display: "grid", gap: 10, color: "inherit" }}>
      {/* Top status strip */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <span
          style={{
            background: regimeColor, color: "#fff", padding: "2px 10px",
            borderRadius: 4, fontWeight: 600, textTransform: "uppercase",
            fontSize: 12, letterSpacing: 0.5,
          }}
        >
          {regime}
        </span>
        <span style={{ fontSize: 13, ...mutedStyle }}>
          tick <strong style={{ color: "inherit" }}>{naive?.tick ?? "—"}</strong>
        </span>
        <span style={{ fontSize: 13, ...mutedStyle }}>
          net <strong style={{ color: "inherit" }}>{fmt(d.net_W, 2, " W")}</strong>
        </span>
        {regime === "surplus" && d.surplus_W > 0.05 && (
          <span style={{ fontSize: 13, color: accentGreen }}>
            exporting {fmt(d.surplus_W, 2, " W")} (cap saturated)
          </span>
        )}
        {regime === "deficit" && d.deficit_W > 0.05 && (
          <span style={{ fontSize: 13, color: accentRed }}>
            importing {fmt(d.deficit_W, 2, " W")} (cap can't cover)
          </span>
        )}
      </div>

      {/* Bus-side energy balance */}
      <div style={{ ...panelStyle, lineHeight: 1.7 }}>
        <div style={{ fontWeight: 600, marginBottom: 4 }}>Bus-side energy balance</div>
        <div>
          PV panel <strong>{fmt(d.pv_panel_W, 2, " W")}</strong>
          {" × η="}<code>{fmt(d.pv_eta_used, 2)}</code>
          {" → bus "}<strong style={{ color: accentGreen }}>{fmt(d.pv_bus_W, 2, " W")}</strong>
        </div>
        <div>
          load = demand <strong>{fmt(d.demand_W, 2, " W")}</strong>
          {" + deferrable rate "}<strong>{fmt(d.def_rate_total_W, 2, " W")}</strong>
          {" = "}<strong style={{ color: accentRed }}>{fmt(d.effective_load_W, 2, " W")}</strong>
        </div>
        <div>
          net = pv_bus − load = <strong>{fmt(d.net_W, 2, " W")}</strong>
        </div>
        <div>
          cap absorbs <strong>{fmt(d.cap_p_W, 2, " W")}</strong>
          {" (i_cmd "}<code>{fmt(naive?.suggested?.cap?.i_cmd, 3, " A")}</code>{")"}
          {clampLabel && (
            <span style={{ marginLeft: 8, color: accentRed, fontSize: 12 }}>
              ⚠ {clampLabel}
            </span>
          )}
        </div>
      </div>

      {/* Active deferrables — the "what's filling up" view */}
      <div style={panelStyle}>
        <div style={{ fontWeight: 600, marginBottom: 6 }}>
          Active deferrables ({active.length})
        </div>
        {active.length === 0 ? (
          <div style={{ color: "#888" }}>
            no deferrable in window — algorithm idle on def_rate
          </div>
        ) : (
          <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ ...mutedStyle, textAlign: "left" }}>
                <th style={{ padding: "2px 4px" }}>#</th>
                <th style={{ padding: "2px 4px" }}>window</th>
                <th style={{ padding: "2px 4px" }}>remaining</th>
                <th style={{ padding: "2px 4px" }}>ticks left</th>
                <th style={{ padding: "2px 4px" }}>rate now</th>
                <th style={{ padding: "2px 4px", width: 120 }}>filling</th>
              </tr>
            </thead>
            <tbody>
              {active.map((ad) => {
                const windowLen = ad.tick_end - ad.tick_start + 1;
                const notionalTotal = Math.max(ad.remaining_energy, ad.rate_W * windowLen);
                const served = Math.max(0, notionalTotal - ad.remaining_energy);
                const pct    = notionalTotal > 0 ? (served / notionalTotal) * 100 : 0;
                return (
                  <tr key={ad.index} style={{ borderTop: "1px solid rgba(128,128,128,0.2)" }}>
                    <td style={{ padding: "4px" }}>{ad.index}</td>
                    <td style={{ padding: "4px" }}>{ad.tick_start}–{ad.tick_end}</td>
                    <td style={{ padding: "4px" }}>{fmt(ad.remaining_energy, 2)}</td>
                    <td style={{ padding: "4px" }}>{ad.ticks_remaining}</td>
                    <td style={{ padding: "4px" }}>
                      <strong>{fmt(ad.rate_W, 2, " W")}</strong>
                    </td>
                    <td style={{ padding: "4px" }}>
                      <div style={{
                        background: "rgba(127,127,127,0.2)", height: 10, borderRadius: 3,
                        overflow: "hidden", position: "relative",
                      }}>
                        <div style={{
                          width: `${Math.min(100, pct).toFixed(1)}%`,
                          height: "100%",
                          background: "linear-gradient(90deg, #4caf50, #2e7d32)",
                        }} />
                      </div>
                      <div style={{ fontSize: 10, ...mutedStyle, marginTop: 1 }}>
                        ~{pct.toFixed(0)}% served
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Outgoing setpoints */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 6, fontSize: 12 }}>
        {[
          ["cap.i_cmd", fmt(naive?.suggested?.cap?.i_cmd, 3, " A")],
          ["LED each",  fmt(naive?.suggested?.led?.p_red, 2, " W")],
          ["v_cap",     fmt(inp.v_cap_V, 2, " V")],
          ["vbus",      fmt(inp.vbus_V, 2, " V")],
        ].map(([label, value]) => (
          <div key={label} style={{
            background: "rgba(127,127,127,0.12)", padding: 6, borderRadius: 4,
            border: "1px solid rgba(128,128,128,0.2)",
          }}>
            <p style={{ margin: 0, ...mutedStyle }}>{label}</p>
            <h3 style={{ margin: 0, color: "inherit" }}>{value}</h3>
          </div>
        ))}
      </div>

      {d.led_clamped_W > 0.01 && (
        <p style={{ color: accentRed, fontSize: 12 }}>
          ⚠ LED setpoint clamped — {fmt(d.led_clamped_W, 2, " W")} couldn't be dissipated
          (each channel hit 3 W cap)
        </p>
      )}
    </div>
  );
}


// ---- Per-Azure-day P&L for the current run ----
// Polls /algo/run/cost every 3 s. Renders two cards: previous Azure day
// and today. "Today" = current Azure day; "previous day" = the most
// recent earlier day we've recorded (may be partial if we started
// mid-day). Price pairing: import × sell_price (we pay), export ×
// buy_price (we earn). Net = import_cost − export_revenue.
function RunCostPanel({ apiBase }) {
  const [cost, setCost] = useState(null);
  const [err,  setErr]  = useState("");

  useEffect(() => {
    let cancelled = false;
    async function poll() {
      try {
        const res = await fetch(`${apiBase}/algo/run/cost`);
        if (res.status === 404) {
          if (!cancelled) { setCost(null); setErr(""); }
          return;
        }
        if (!res.ok) {
          if (!cancelled) setErr(`cost fetch failed: ${res.status}`);
          return;
        }
        const data = await res.json();
        if (!cancelled) { setCost(data); setErr(""); }
      } catch (e) {
        if (!cancelled) setErr(String(e?.message || e));
      }
    }
    poll();
    const id = setInterval(poll, 3000);
    return () => { cancelled = true; clearInterval(id); };
  }, [apiBase]);

  if (!cost && !err) {
    return (
      <div className="naive-host-panel" style={{ marginTop: 12 }}>
        <div className="naive-toolbar"><strong>Daily P&L:</strong></div>
        <p className="naive-host-msg">no run started yet</p>
      </div>
    );
  }

  return (
    <div className="naive-host-panel" style={{ marginTop: 12, color: "inherit" }}>
      <div className="naive-toolbar" style={{ alignItems: "baseline" }}>
        <strong>Daily P&L</strong>
        <span style={{ fontSize: 11, color: "rgba(127,127,127,0.85)" }}>
          since {cost?.run_started_at ? new Date(cost.run_started_at).toLocaleTimeString() : "—"}
          {" · "}
          {cost?.run_running === false && "stopped · "}
          {cost?.price_ticks ?? 0} ticks recorded
        </span>
      </div>

      {err && (
        <p className="naive-apply-msg" style={{ color: "#ef5350" }}>{err}</p>
      )}

      <div style={{
        display: "flex", flexWrap: "wrap", gap: 10, marginTop: 6,
      }}>
        <DayCostCard label="Previous day" block={cost?.previous_day}
                     emptyMsg="no previous day yet — waiting for tick rollover" />
        <DayCostCard label="Today"        block={cost?.today}
                     emptyMsg="no ticks recorded yet" />
      </div>

      <p className="naive-host-msg" style={{
        marginTop: 6, fontSize: 11, color: "rgba(127,127,127,0.85)",
      }}>
        net = ∫ p_import·sell_price dt − ∫ p_export·buy_price dt.
        Positive = paid out, negative = net earned. 1 tick = 5 s.
      </p>
    </div>
  );
}


function DayCostCard({ label, block, emptyMsg }) {
  const fmt  = (v, n = 2) => (typeof v === "number" ? v.toFixed(n) : "—");
  const fmtJ = (v) => (typeof v === "number" ? `${v.toFixed(1)} J` : "—");

  const cardBase = {
    flex: "1 1 240px",
    background: "rgba(127,127,127,0.08)",
    border: "1px solid rgba(128,128,128,0.25)",
    borderRadius: 6, padding: "10px 14px",
  };

  if (!block) {
    return (
      <div style={cardBase}>
        <div style={{
          fontSize: 11, color: "rgba(127,127,127,0.85)",
          textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 2,
        }}>{label}</div>
        <div style={{ fontSize: 13, color: "rgba(127,127,127,0.75)", marginTop: 6 }}>
          {emptyMsg}
        </div>
      </div>
    );
  }

  const net      = block.net_cost ?? 0;
  const netSign  = net > 0 ? "+" : net < 0 ? "−" : "";
  const netColor = net > 0 ? "#ef5350" : net < 0 ? "#3fc380" : "inherit";
  const netAbs   = Math.abs(net);

  const ts = block.tick_start ?? "?";
  const te = block.tick_end   ?? "?";
  const tn = block.ticks_observed ?? 0;
  const isPartial = tn < (block.ticks_total ?? 60);
  const coverage = `tick ${ts}–${te}` + (isPartial ? ` (partial: ${tn}/60)` : ` (${tn}/60)`);

  return (
    <div style={cardBase}>
      <div style={{
        fontSize: 11, color: "rgba(127,127,127,0.85)",
        textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 2,
      }}>
        {label} · Azure day {block.day}
      </div>

      <div style={{ fontSize: 11, color: "rgba(127,127,127,0.85)", marginBottom: 4 }}>
        {coverage}
      </div>

      <div style={{ fontSize: 22, fontWeight: 700, color: netColor, lineHeight: 1.1 }}>
        {netSign}{fmt(netAbs, 2)}
      </div>
      <div style={{ fontSize: 11, color: "rgba(127,127,127,0.85)", marginTop: 2, marginBottom: 6 }}>
        {net > 0 ? "paid out (net)" : net < 0 ? "net earned" : "break-even"}
      </div>

      <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
        <tbody>
          <tr style={{ borderTop: "1px solid rgba(128,128,128,0.2)" }}>
            <td style={{ padding: "3px 4px", color: "#ef5350", whiteSpace: "nowrap" }}>↓ import</td>
            <td style={{ padding: "3px 4px", textAlign: "right" }}>{fmtJ(block.import_energy_J)}</td>
            <td style={{ padding: "3px 4px", textAlign: "right", color: "#ef5350" }}>
              +{fmt(block.import_cost, 2)}
            </td>
          </tr>
          <tr>
            <td style={{ padding: "3px 4px", color: "#3fc380", whiteSpace: "nowrap" }}>↑ export</td>
            <td style={{ padding: "3px 4px", textAlign: "right" }}>{fmtJ(block.export_energy_J)}</td>
            <td style={{ padding: "3px 4px", textAlign: "right", color: "#3fc380" }}>
              −{fmt(block.export_revenue, 2)}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}


// ---- Server-side auto-loop (runs on the backend, survives browser close) ----
function ServerAutoLoopPanel({ apiBase }) {
  const [status, setStatus] = useState(null);
  const [busy,   setBusy]   = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function poll() {
      try {
        const res = await fetch(`${apiBase}/algo/auto/status`);
        if (!res.ok) return;
        const data = await res.json();
        if (!cancelled) setStatus(data);
      } catch {}
    }
    poll();
    const id = setInterval(poll, 2000);
    return () => { cancelled = true; clearInterval(id); };
  }, [apiBase]);

  async function toggle() {
    if (busy) return;
    setBusy(true);
    try {
      const action = status?.running ? "stop" : "start";
      await fetch(`${apiBase}/algo/auto/${action}`, { method: "POST" });
    } finally {
      setBusy(false);
    }
  }

  const running = !!status?.running;
  return (
    <div className="naive-host-panel" style={{ marginTop: 12 }}>
      <div className="naive-toolbar">
        <strong>Server auto-loop:</strong>
        <button className="naive-host-save" onClick={toggle} disabled={busy}>
          {running ? "Stop" : "Start"}
        </button>
        <span className="naive-host-msg">
          {running ? "running" : "stopped"}
          {status?.last_regime && ` · last: ${status.last_regime}`}
          {status?.applied_count != null &&
            ` · applied=${status.applied_count} / skipped=${status.skipped_count}`}
        </span>
      </div>
      {status?.last_error && (
        <p className="naive-apply-msg" style={{ color: "#c00" }}>
          error: {status.last_error}
        </p>
      )}
    </div>
  );
}


// ---- Current-run data export (downloads a zip of CSVs) ----
// Scoped to the auto-loop's most recent /algo/auto/start, not the full DB
// history. Re-pressing Start defines a new run; the next download covers
// only what was logged after that.
function DataExportPanel({ apiBase }) {
  const [summary, setSummary] = useState(null);
  const [busy,    setBusy]    = useState(false);
  const [error,   setError]   = useState("");

  async function refreshSummary() {
    try {
      const res = await fetch(`${apiBase}/export/run/summary`);
      if (res.ok) setSummary(await res.json());
    } catch {}
  }

  useEffect(() => {
    refreshSummary();
    const id = setInterval(refreshSummary, 5000);
    return () => clearInterval(id);
  }, [apiBase]);

  async function downloadZip() {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const res = await fetch(`${apiBase}/export/run?format=csv`);
      if (res.status === 404) {
        setError("Start the auto-loop first — there's no run to download yet.");
        return;
      }
      if (!res.ok) throw new Error(`export failed: ${res.status}`);
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement("a");
      const ts   = new Date().toISOString().replace(/[:.]/g, "-");
      a.href = url;
      a.download = `smartgrid-run-${ts}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  }

  const startedAt = summary?.run_started_at;
  const runActive = !!startedAt;
  const fmt = (s) => (s?.count ?? 0) + " rows";

  return (
    <div className="naive-host-panel" style={{ marginTop: 12 }}>
      <div className="naive-toolbar">
        <strong>Current-run export:</strong>
        <button
          className="naive-host-save"
          onClick={downloadZip}
          disabled={busy || !runActive}
          title={runActive ? "" : "Press Start on the server auto-loop first"}
        >
          {busy ? "Preparing..." : "Download CSV zip (this run)"}
        </button>
        <button className="naive-host-toggle" onClick={refreshSummary}>
          Refresh
        </button>
      </div>
      <p className="naive-host-msg" style={{ marginTop: 6 }}>
        {runActive ? (
          <>
            run started: {new Date(startedAt).toLocaleString()}
            {summary?.run_running === false && " (stopped)"}
            {" · "}
            grid: {fmt(summary?.grid_snapshots)} · modules: {fmt(summary?.module_snapshots)} · decisions: {fmt(summary?.naive_decisions)}
          </>
        ) : (
          "no run started yet — press Start on the server auto-loop above"
        )}
      </p>
      {error && (
        <p className="naive-apply-msg" style={{ color: "#c00" }}>{error}</p>
      )}
    </div>
  );
}

function ModulePlotCard({ role, data, history }) {
  const status = getModuleStatus(data);
  const lines = ROLE_LINES[role] || [];
  const color = ROLE_COLORS[role];

  const latestStats = {
    pv: [
      ["Vpv", data?.v_panel, "V"],
      ["Vbus", data?.vb_bus, "V"],
      ["Ppv", data?.p_panel, "W"],
    ],
    grid: [
      ["Vbus", data?.vb_bus, "V"],
      ["Vpsu", data?.v_psu, "V"],
      ["Import", data?.p_import, "W"],
    ],
    export: [
      ["Vbus", data?.vb_bus, "V"],
      ["Vres", data?.v_resistor, "V"],
      ["Dissip", data?.p_dissip, "W"],
    ],
    cap: [
      ["Vcap", data?.v_cap, "V"],
      ["SoC", data?.soc_pct, "%"],
      ["Energy", data?.energy_J, "J"],
    ],
    led: [
      ["Red", data?.p_red, "W"],
      ["Yellow", data?.p_yel, "W"],
      ["Green", data?.p_grn, "W"],
    ],
  }[role];

  return (
    <section className="card smps-plot-card">
      <div className="smps-plot-header">
        <div>
          <div className="smps-plot-title" style={{ color }}>
            {ROLE_LABELS[role]}
          </div>
          <div className="smps-plot-sub">
            {data?.timestamp
              ? `Last update: ${new Date(data.timestamp).toLocaleTimeString()}`
              : "No telemetry yet"}
          </div>
        </div>
        <StatusBadge status={status} />
      </div>

      <div className="smps-plot-stats">
        {latestStats.map(([label, value, unit]) => (
          <div className="smps-plot-stat" key={label}>
            <p>{label}</p>
            <h3>
              {fmt(value)}
              <span>{unit}</span>
            </h3>
          </div>
        ))}
      </div>

      <div className="smps-plot-wrapper">
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={history}>
            <XAxis
              dataKey="id"
              hide
            />
            <YAxis
              stroke="#a69ec4"
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={40}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#14052e",
                borderColor: "#27134d",
                borderRadius: "8px",
              }}
              labelStyle={{ color: "#ffffff" }}
            />
            {lines.map((line) => (
              <Line
                key={line.key}
                type="monotone"
                dataKey={line.key}
                name={line.name}
                stroke={line.color}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
                connectNulls={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="smps-plot-legend">
        {lines.map((line) => (
          <span key={line.key}>
            <i style={{ background: line.color }} />
            {line.name}
          </span>
        ))}
      </div>
    </section>
  );
}

export default function SmpsModules({ apiBase }) {
  const [modules, setModules] = useState({});
  const histRef = useRef(Object.fromEntries(ROLES.map((r) => [r, []])));
  const [hist, setHist] = useState(Object.fromEntries(ROLES.map((r) => [r, []])));
  const [overviewData, setOverviewData] = useState([]);
  const [naive, setNaive] = useState(null);
  const [applyBusy, setApplyBusy] = useState(false);
  const [applyMsg, setApplyMsg] = useState("");
  const [showHostConfig, setShowHostConfig] = useState(false);
  const [backendHosts, setBackendHosts] = useState({ cap: "", led: "" });
  const [hostsMsg, setHostsMsg] = useState("");
  const [autoApply, setAutoApply] = useState(false);
  const [cooldownSec, setCooldownSec] = useState(5);
  const lastAutoApplyRef = useRef(0);

  // Algorithm registry / active-selection state.
  const [activeAlgoId, setActiveAlgoId] = useState("naive");
  const [switchingAlgo, setSwitchingAlgo] = useState(false);
  const [switchAlgoMsg, setSwitchAlgoMsg] = useState("");

  async function switchAlgorithm(algoId) {
    if (switchingAlgo || algoId === activeAlgoId) return;
    setSwitchingAlgo(true);
    setSwitchAlgoMsg("");
    try {
      const res = await fetch(`${apiBase}/algo/active`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: algoId }),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || `switch failed: ${res.status}`);
      }
      const data = await res.json();
      setActiveAlgoId(data.active || algoId);
      setSwitchAlgoMsg(`switched to ${data.name || algoId}`);
      window.setTimeout(() => setSwitchAlgoMsg(""), 2500);
    } catch (err) {
      console.error("Failed to switch algorithm", err);
      setSwitchAlgoMsg(`switch failed: ${String(err.message || err)}`);
    } finally {
      setSwitchingAlgo(false);
    }
  }

  async function applyNaiveNow(opts = {}) {
    const { silent = false } = opts;

    if (applyBusy) return false;

    setApplyBusy(true);
    if (!silent) setApplyMsg("");

    try {
      const res = await fetch(`${apiBase}/algo/naive/apply`, { method: "POST" });
      if (!res.ok) {
        throw new Error(`Apply request failed: ${res.status}`);
      }

      const data = await res.json();
      if (data?.recommendation) {
        setNaive(data.recommendation);
      }

      if (!silent) {
        const parts = ["cap", "led", "grid", "export"].map((r) => {
          const ok = data?.applied?.[r]?.ok;
          return `${r} ${ok ? "ok" : "✗"}`;
        });
        const regime = data?.recommendation?.regime;
        setApplyMsg(`${regime ?? "?"}: ${parts.join(", ")}`);
      }
      return true;
    } catch (err) {
      console.error("Failed to apply naive command", err);
      if (!silent) setApplyMsg("apply failed");
      return false;
    } finally {
      setApplyBusy(false);
    }
  }

  async function loadBackendHosts() {
    try {
      const res = await fetch(`${apiBase}/algo/module-hosts`);
      if (!res.ok) return;
      const data = await res.json();
      const hosts = data?.hosts || {};
      setBackendHosts({ cap: hosts.cap || "", led: hosts.led || "" });
    } catch (err) {
      console.error("Failed to load backend hosts", err);
    }
  }

  async function saveBackendHosts() {
    setHostsMsg("");
    try {
      const res = await fetch(`${apiBase}/algo/module-hosts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ hosts: backendHosts }),
      });
      if (!res.ok) {
        throw new Error(`save failed ${res.status}`);
      }
      setHostsMsg("hosts saved");
    } catch (err) {
      console.error("Failed to save backend hosts", err);
      setHostsMsg("save failed");
    }
  }

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const [modulesRes, snapshotsRes, pvRes, gridRes, exportRes, naiveRes] = await Promise.all([
          fetch(`${apiBase}/modules/latest`),
          fetch(`${apiBase}/snapshots?limit=${OVERVIEW_LIMIT}`),
          fetch(`${apiBase}/modules/snapshots/pv?limit=${OVERVIEW_LIMIT}`),
          fetch(`${apiBase}/modules/snapshots/grid?limit=${OVERVIEW_LIMIT}`),
          fetch(`${apiBase}/modules/snapshots/export?limit=${OVERVIEW_LIMIT}`),
          fetch(`${apiBase}/algo/naive`),
        ]);
        if (!modulesRes.ok) return;

        const [data, snapshotsData, pvData, gridData, exportData, naiveData] = await Promise.all([
          modulesRes.json(),
          snapshotsRes.ok ? snapshotsRes.json() : [],
          pvRes.ok ? pvRes.json() : [],
          gridRes.ok ? gridRes.json() : [],
          exportRes.ok ? exportRes.json() : [],
          naiveRes.ok ? naiveRes.json() : null,
        ]);
        if (cancelled) return;

        setModules(data || {});
        setOverviewData(buildOverviewSeries(
          Array.isArray(snapshotsData) ? snapshotsData : [],
          Array.isArray(pvData) ? pvData : [],
          Array.isArray(gridData) ? gridData : [],
          Array.isArray(exportData) ? exportData : [],
        ));
        setNaive(naiveData && !naiveData.error ? naiveData : null);
        if (naiveData && !naiveData.error && naiveData.algo_id) {
          setActiveAlgoId(naiveData.algo_id);
        }

        ROLES.forEach((role) => {
          const row = data?.[role];
          if (!row) return;

          const h = histRef.current[role];
          h.push(row);
          if (h.length > HIST_MAX) h.shift();
        });

        setHist(Object.fromEntries(
          ROLES.map((role) => [role, [...histRef.current[role]]])
        ));
      } catch (err) {
        console.error("Failed to fetch module telemetry", err);
      }
    }

    loadBackendHosts();
    poll();
    const id = setInterval(poll, 2000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [apiBase]);

  useEffect(() => {
    if (!autoApply) return;

    const id = setInterval(() => {
      if (!naive || applyBusy) return;

      const cooldownMs = Math.max(1, Number(cooldownSec) || 1) * 1000;
      const now = Date.now();
      if (now - lastAutoApplyRef.current < cooldownMs) return;

      lastAutoApplyRef.current = now;
      applyNaiveNow({ silent: true });
    }, 1000);

    return () => clearInterval(id);
  }, [autoApply, cooldownSec, naive, applyBusy]);

  return (
    <div className="smps-plots-page">
      <OverviewGraphCard data={overviewData} />
      <NaiveDispatchCard
        apiBase={apiBase}
        naive={naive}
        applyBusy={applyBusy}
        applyMsg={applyMsg}
        onApply={applyNaiveNow}
        showHostConfig={showHostConfig}
        onToggleHostConfig={() => setShowHostConfig((v) => !v)}
        backendHosts={backendHosts}
        onHostsChange={setBackendHosts}
        onSaveHosts={saveBackendHosts}
        hostsMsg={hostsMsg}
        autoApply={autoApply}
        onAutoApplyChange={setAutoApply}
        cooldownSec={cooldownSec}
        onCooldownChange={setCooldownSec}
        activeAlgoId={activeAlgoId}
        onSwitchAlgo={switchAlgorithm}
        switchingAlgo={switchingAlgo}
        switchAlgoMsg={switchAlgoMsg}
      />
      {ROLES.map((role) => (
        <ModulePlotCard
          key={role}
          role={role}
          data={modules?.[role]}
          history={hist[role]}
        />
      ))}
    </div>
  );
}