import { useEffect, useRef, useState } from "react";
import { BusGauge, GlobalChart, ModuleAdvancedPanel } from "./SmpsModules";
import UnifiedLineChart from "./UnifiedLineChart";

const ROLES = ["pv", "grid", "export", "cap", "led"];
const ROLE_COLUMNS = [
  ["pv", "export", "led"],
  ["grid", "cap"],
];
const HIST_MAX = 60;
const OVERVIEW_LIMIT = 60;
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

function getModuleStatus(module, status) {
  if (!status || status.online === false) return "offline";
  if (module?.trip) return "trip";
  if (module?.wd) return "watchdog";
  if (module && module.enable === false) return "disabled";

  return "online";
}

function getBusVoltage(modules) {
  for (const role of ["grid", "export", "pv", "cap"]) {
    const value = modules?.[role]?.vb_bus;
    if (typeof value === "number" && Number.isFinite(value)) return value;
  }
  return null;
}

function buildGlobalTelemetryHistory(hist) {
  const length = Math.max(0, ...ROLES.map((role) => hist?.[role]?.length || 0));

  return Array.from({ length }, (_, index) => {
    const rows = Object.fromEntries(
      ROLES.map((role) => {
        const roleHistory = hist?.[role] || [];
        const offset = length - roleHistory.length;
        return [role, roleHistory[index - offset] || null];
      })
    );
    const led = rows.led || {};
    const timestamp =
      rows.grid?.timestamp ||
      rows.export?.timestamp ||
      rows.pv?.timestamp ||
      rows.cap?.timestamp ||
      rows.led?.timestamp;

    return {
      t: timestamp ? new Date(timestamp).toLocaleTimeString() : String(index + 1),
      vbus: getBusVoltage(rows),
      i_pv: rows.pv?.iL ?? null,
      i_grid: rows.grid?.iL ?? null,
      i_export: rows.export?.iL ?? null,
      i_cap: rows.cap?.iL ?? null,
      i_led:
        [led.i_red, led.i_yel, led.i_grn].some(
          (value) => typeof value === "number" && Number.isFinite(value)
        )
          ? (led.i_red || 0) + (led.i_yel || 0) + (led.i_grn || 0)
          : null,
    };
  });
}

function fmt(v, digits = 3) {
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

function OverviewGraphCard({
  data,
  theme = "dark",
}) {
  const latest = data[data.length - 1];
  const isLightTheme = theme === "light";
  const titleColor = isLightTheme ? "#182235" : "#ffffff";
  const series = {
    pv: isLightTheme ? "#1f7d3b" : "#00e676",
    demand: isLightTheme ? "#167f91" : "#00f0ff",
    def1: isLightTheme ? "#9b6b00" : "#ffc800",
    def2: isLightTheme ? "#b85f00" : "#ff9100",
    def3: isLightTheme ? "#2f7f7a" : "#5ec9c0",
    export: isLightTheme ? "#b63a59" : "#ff4d6d",
    import: isLightTheme ? "#7a4cb8" : "#b67ad9",
  };

  return (
    <section className="card smps-plot-card smps-overview-card smps-overview-graph-card">
      <div className="smps-plot-header">
        <div>
          <div className="smps-plot-title" style={{ color: titleColor }}>
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
          <h3>{latest ? `${fmt(latest.cumulative_import_J)} / ${fmt(latest.cumulative_export_J)} J` : "—"}</h3>
        </div>
      </div>

      <UnifiedLineChart
        data={data}
        xKey="tick"
        height={320}
        theme={theme}
        rightAxis
        lines={[
          { key: "pv_power_W", label: "PV power", color: series.pv },
          { key: "instant_demand_W", label: "Demand", color: series.demand },
          { key: "deferrable_1_J", label: "Deferrable 1", color: series.def1 },
          { key: "deferrable_2_J", label: "Deferrable 2", color: series.def2 },
          { key: "deferrable_3_J", label: "Deferrable 3", color: series.def3 },
          { key: "cumulative_export_J", label: "Cumulative export", color: series.export, axis: "right" },
          { key: "cumulative_import_J", label: "Cumulative import", color: series.import, axis: "right" },
        ]}
      />
    </section>
  );
}

function BusOverviewCard({ vbus, busHistory, theme = "dark", advanced = false }) {
  return (
    <section className="card smps-plot-card smps-overview-card smps-bus-card">
      <div className="smps-plot-header">
        <div>
          <div className="smps-plot-title">Bus Health</div>
          <div className="smps-plot-sub">
            Live DC bus voltage and module-level electrical telemetry.
          </div>
        </div>
      </div>

      <div className="smps-bus-summary">
        <BusGauge vbus={vbus} />
      </div>

      {advanced && (
        <div className="smps-bus-advanced">
          <GlobalChart
            data={busHistory}
            theme={theme}
          />
        </div>
      )}
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
              <span className="algo-tab-label">{a.name}</span>
              {isActive && <span className="algo-tab-state">Active</span>}
            </button>
          );
        })}
      </div>
      {switchMsg && <div className="algo-tabs-msg algo-tabs-error">{switchMsg}</div>}
    </div>
  );
}


// ---- Smart V1 (and future algos) extras panel ----
// Renders the algorithm-specific diagnostics dict (cmd.algo_extras) as a
// glanceable grid. Hidden when the active algorithm provides no extras.
function AlgoExtrasPanel({ naive }) {
  const extras = naive?.diagnostics?.algo_extras;
  if (!extras || Object.keys(extras).length === 0) return null;

  // Pretty-print the Smart V1 shape if recognised, otherwise dump generically.
  const isSmartV1 =
    "cap_action_reason" in extras || "forecast_now" in extras;

  if (isSmartV1) {
    const fn = extras.forecast_now || {};
    return (
      <section className="algo-section-card">
        <div className="algo-section-heading">
          <div>
            <h3>Smart V1 forecast</h3>
            <p>Forecast-aware capacitor decision for the current tick.</p>
          </div>
        </div>

        <div className="algo-metric-grid">
          <Metric label="Cap action" value={extras.cap_action_reason || "—"} />
          <Metric label="Bus target" value={extras.cap_action_target_W?.toFixed?.(2) ?? "—"} unit="W" />
          <Metric label="Arbitrage gain" value={extras.cap_arb_gain?.toFixed?.(1) ?? "—"} unit="¢/J" />
          <Metric label="Horizon" value={extras.cap_arb_horizon_t ?? "—"} unit="ticks" />
        </div>

        <div className="algo-forecast-strip">
          <Metric label="Sell price" value={fn.sell_price ?? "—"} />
          <Metric label="Buy price" value={fn.buy_price ?? "—"} />
          <Metric label="Forecast PV" value={fn.pv_bus_W ?? "—"} unit="W" />
          <Metric label="Forecast demand" value={fn.demand_W ?? "—"} unit="W" />
        </div>
      </section>
    );
  }

  // Generic fallback — list keys/values.
  return (
    <section className="algo-section-card">
      <div className="algo-section-heading">
        <h3>Algorithm extras</h3>
      </div>
      <pre style={{ margin: 0, fontSize: 11, overflowX: "auto" }}>
        {JSON.stringify(extras, null, 2)}
      </pre>
    </section>
  );
}

function Metric({ label, value, unit = "" }) {
  return (
    <div className="algo-metric">
      <span>{label}</span>
      <strong>
        {value}
        {unit && <small>{unit}</small>}
      </strong>
    </div>
  );
}


function NaiveDispatchCard({
  apiBase,
  naive,
  advanced = false,
  screenshotMode = false,
  activeAlgorithm,
  autoStatus,
  runCost,
  applyBusy,
  applyMsg,
  onApply,
  activeAlgoId,
  onSwitchAlgo,
  switchingAlgo,
  switchAlgoMsg,
}) {
  const [runRefreshToken, setRunRefreshToken] = useState(0);
  const algoLabel =
    activeAlgorithm?.name ||
    naive?.algo_name ||
    naive?.diagnostics?.algo_id ||
    activeAlgoId ||
    "—";
  const diagnostics = naive?.diagnostics || {};
  const regime = diagnostics.regime || naive?.regime || "—";
  const todayCost = runCost?.today;
  const netCost = todayCost?.net_cost;
  return (
    <section className="card smps-plot-card smps-overview-card smps-algorithm-card">
      <div className="card-header algorithm-card-header">
        <span className="algorithm-card-title">
          <span>Algorithm Dispatch</span>
        </span>
        <span className="algorithm-card-name">{algoLabel}</span>
        <span
          className={`system-run-state ${autoStatus?.running ? "running" : "stopped"}`}
        >
          {autoStatus?.running ? "Running" : "Stopped"}
        </span>
      </div>

      <div className="algorithm-compact-grid algorithm-compact-grid-wide">
        <div>
          <span>Regime</span>
          <strong>{regime}</strong>
        </div>
        <div>
          <span>Net balance</span>
          <strong>
            {typeof diagnostics.net_W === "number"
              ? `${diagnostics.net_W.toFixed(3)} W`
            : "—"}
          </strong>
        </div>
        <div>
          <span>Import cost</span>
          <strong>
            {typeof todayCost?.import_cost === "number"
              ? todayCost.import_cost.toFixed(3)
              : "—"}
          </strong>
        </div>
        <div>
          <span>Export revenue</span>
          <strong>
            {typeof todayCost?.export_revenue === "number"
              ? todayCost.export_revenue.toFixed(3)
              : "—"}
          </strong>
        </div>
        <div>
          <span>Net cost</span>
          <strong className={typeof netCost === "number" && netCost < 0 ? "cost-positive" : "cost-negative"}>
            {typeof netCost === "number" ? netCost.toFixed(3) : "—"}
          </strong>
        </div>
      </div>

      {advanced && (
        <div className="algorithm-inline-advanced">
          <section className="algorithm-stage algorithm-selection-stage">
            <div className="algorithm-stage-heading">
              <div>
                <h3>Algorithm selection</h3>
                <p>Select the strategy that produces the next dispatch command.</p>
              </div>
            </div>
            <AlgorithmTabs
              apiBase={apiBase}
              activeId={activeAlgoId}
              onSwitch={onSwitchAlgo}
              switching={switchingAlgo}
              switchMsg={switchAlgoMsg}
            />
          </section>

          <NaiveDebugPanel naive={naive} />

          <section className="algorithm-stage">
            <div className="algorithm-stage-heading">
              <div>
                <h3>Forecast and economics</h3>
                <p>Forward-looking decision context and the financial result of the run.</p>
              </div>
            </div>
            <AlgoExtrasPanel naive={naive} />

            <RunCostPanel apiBase={apiBase} refreshToken={runRefreshToken} />
          </section>

          <section className="algorithm-stage">
            <div className="algorithm-stage-heading">
              <div>
                <h3>Run controls</h3>
                <p>Start dispatch, test one tick, refresh status, or export the current run.</p>
              </div>
            </div>
            <AlgorithmRunControls
              apiBase={apiBase}
              screenshotMode={screenshotMode}
              applyBusy={applyBusy}
              applyMsg={applyMsg}
              canTest={!!naive}
              onTest={onApply}
              refreshToken={runRefreshToken}
              onRefresh={() => setRunRefreshToken((token) => token + 1)}
            />
          </section>
        </div>
      )}
    </section>
  );
}


// ---- "What is the algorithm doing right now?" debug panel ----
// Reads `naive.diagnostics` (populated by buysellalgorithm/naive.py's
// commands_to_diagnostics) and renders a compact, glanceable view.
function NaiveDebugPanel({ naive }) {
  const d   = naive?.diagnostics || {};
  const inp = naive?.inputs || {};
  const fmt = (v, n = 3, suf = "") =>
    typeof v === "number" ? `${v.toFixed(n)}${suf}` : "—";

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
    borderRadius: "var(--radius-control)",
    padding: "8px 10px",
    fontSize: 13,
    color: "inherit",
  };
  const mutedStyle  = { color: "rgba(127,127,127,0.85)" };

  return (
    <section className="algorithm-stage naive-debug">
      <div className="algorithm-stage-heading">
        <div>
          <h3>Current dispatch decision</h3>
          <p>How the active algorithm reads the power balance and assigns module outputs.</p>
        </div>
      </div>

      {/* Bus-side energy balance */}
      <section className="algo-section-card">
        <div className="algo-section-heading">
          <div>
            <h3>Bus-side energy balance</h3>
            <p>Current power flow after conversion losses and active loads.</p>
          </div>
        </div>

        <div className="algo-flow-grid">
          <div className="algo-flow-card generation">
            <span>PV to bus</span>
            <strong>{fmt(d.pv_bus_W, 3, " W")}</strong>
            <small>
              panel {fmt(d.pv_panel_W, 3, " W")} · efficiency {fmt(d.pv_eta_used, 3)}
            </small>
          </div>

          <div className="algo-flow-card demand">
            <span>Effective load</span>
            <strong>{fmt(d.effective_load_W, 3, " W")}</strong>
            <small>
              demand {fmt(d.demand_W, 3, " W")} · deferrable {fmt(d.def_rate_total_W, 3, " W")}
            </small>
          </div>

          <div className="algo-flow-card storage">
            <span>Capacitor command</span>
            <strong>{fmt(d.cap_p_W, 3, " W")}</strong>
            <small>i_cmd {fmt(naive?.suggested?.cap?.i_cmd, 3, " A")}</small>
          </div>
        </div>

        <div className="algo-setpoint-grid">
          {[
            ["cap.i_cmd", fmt(naive?.suggested?.cap?.i_cmd, 3, " A")],
            ["LED each",  fmt(naive?.suggested?.led?.p_red, 3, " W")],
            ["v_cap",     fmt(inp.v_cap_V, 3, " V")],
            ["vbus",      fmt(inp.vbus_V, 3, " V")],
          ].map(([label, value]) => (
            <div key={label} className="algo-setpoint-card">
              <p style={{ margin: 0, ...mutedStyle }}>{label}</p>
              <h3 style={{ margin: 0, color: "inherit" }}>{value}</h3>
            </div>
          ))}
        </div>

        {clampLabel && <div className="algo-warning">{clampLabel}</div>}
      </section>

      {/* Active deferrables — the "what's filling up" view */}
      <div className="algo-detail-panel" style={panelStyle}>
        <div className="algo-detail-title">
          Load execution ({active.length} active)
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
                <th style={{ padding: "2px 4px" }}>Ticks left</th>
                <th style={{ padding: "2px 4px" }}>Rate now</th>
                <th style={{ padding: "2px 4px", width: 120 }}>Filling</th>
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
                    <td style={{ padding: "4px" }}>{fmt(ad.remaining_energy, 3)}</td>
                    <td style={{ padding: "4px" }}>{ad.ticks_remaining}</td>
                    <td style={{ padding: "4px" }}>
                      <strong>{fmt(ad.rate_W, 3, " W")}</strong>
                    </td>
                    <td style={{ padding: "4px" }}>
                      <div className="progress-labels">
                        <span>~{pct.toFixed(3)}% Served</span>
                      </div>
                      <div className="progress-bg">
                        <div
                          className="progress-fill"
                          style={{ width: `${Math.min(100, pct).toFixed(3)}%` }}
                        />
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {d.led_clamped_W > 0.01 && (
        <p className="algo-warning">
          LED setpoint clamped: {fmt(d.led_clamped_W, 3, " W")} could not be dissipated
          (each channel hit 3 W cap)
        </p>
      )}
    </section>
  );
}


// ---- Per-Azure-day P&L for the current run ----
// Polls /algo/run/cost every 3 s. Renders two cards: previous Azure day
// and today. "Today" = current Azure day; "previous day" = the most
// recent earlier day we've recorded (may be partial if we started
// mid-day). Price pairing: import × sell_price (we pay), export ×
// buy_price (we earn). Net = import_cost − export_revenue.
function RunCostPanel({ apiBase, refreshToken = 0 }) {
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
  }, [apiBase, refreshToken]);

  return (
    <section className="algo-section-card algo-pnl-panel">
      <div className="algo-section-heading">
        <div>
          <h3>Daily P&amp;L</h3>
          <p>Import cost, export revenue, and net result for the current algorithm run.</p>
        </div>
        <span className="algo-panel-meta">
          {cost?.run_started_at ? `since ${new Date(cost.run_started_at).toLocaleTimeString()}` : "-"}
          {cost?.run_started_at && ` · ${cost?.run_running ? "running" : "stopped"} · ${cost?.price_ticks ?? 0} ticks`}
        </span>
      </div>

      {err && (
        <p className="algo-warning">{err}</p>
      )}

      <div className="algo-pnl-grid">
        <DayCostCard label="Previous day" block={cost?.previous_day} />
        <DayCostCard label="Today" block={cost?.today} />
      </div>

      <p className="algo-panel-note">
        Positive net cost means money paid; negative means net revenue. One tick is 5 seconds.
      </p>
    </section>
  );
}


function DayCostCard({ label, block }) {
  const fmt  = (v, n = 3) => (typeof v === "number" ? v.toFixed(n) : "—");
  const fmtJ = (v) => (typeof v === "number" ? `${v.toFixed(3)} J` : "—");

  if (!block) {
    return (
      <div className="algo-pnl-card is-empty">
        <div className="algo-pnl-label">{label}</div>
        <div className="algo-pnl-coverage">Azure day -</div>
        <div className="algo-pnl-value">-</div>
        <div className="algo-pnl-caption">No recorded data</div>
        <div className="algo-pnl-row import">
          <span>Import</span><span>-</span><strong>-</strong>
        </div>
        <div className="algo-pnl-row export">
          <span>Export</span><span>-</span><strong>-</strong>
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
    <div className="algo-pnl-card">
      <div className="algo-pnl-label">{label} · Azure day {block.day}</div>
      <div className="algo-pnl-coverage">{coverage}</div>
      <div className="algo-pnl-value" style={{ color: netColor }}>
        {netSign}{fmt(netAbs, 3)}
      </div>
      <div className="algo-pnl-caption">
        {net > 0 ? "paid out (net)" : net < 0 ? "net earned" : "break-even"}
      </div>
      <div className="algo-pnl-row import">
        <span>Import</span>
        <span>{fmtJ(block.import_energy_J)}</span>
        <strong>+{fmt(block.import_cost, 3)}</strong>
      </div>
      <div className="algo-pnl-row export">
        <span>Export</span>
        <span>{fmtJ(block.export_energy_J)}</span>
        <strong>-{fmt(block.export_revenue, 3)}</strong>
      </div>
    </div>
  );
}


// ---- Run controls and current-run export ----
function AlgorithmRunControls({
  apiBase,
  screenshotMode = false,
  applyBusy,
  applyMsg,
  canTest,
  onTest,
  refreshToken,
  onRefresh,
}) {
  const [status, setStatus] = useState(null);
  const [summary, setSummary] = useState(null);
  const [toggleBusy, setToggleBusy] = useState(false);
  const [downloadBusy, setDownloadBusy] = useState(false);
  const [error, setError] = useState("");

  async function refreshData() {
    try {
      const [statusRes, summaryRes] = await Promise.all([
        fetch(`${apiBase}/algo/auto/status`),
        fetch(`${apiBase}/export/run/summary`),
      ]);
      if (statusRes.ok) {
        setStatus(await statusRes.json());
      }
      if (summaryRes.ok) {
        setSummary(await summaryRes.json());
      } else if (summaryRes.status === 404) {
        setSummary(null);
      }
      setError("");
    } catch {
      setError("Unable to refresh algorithm status.");
    }
  }

  useEffect(() => {
    let cancelled = false;
    async function poll() {
      try {
        const [statusRes, summaryRes] = await Promise.all([
          fetch(`${apiBase}/algo/auto/status`),
          fetch(`${apiBase}/export/run/summary`),
        ]);
        if (cancelled) return;
        if (statusRes.ok) setStatus(await statusRes.json());
        if (summaryRes.ok) {
          setSummary(await summaryRes.json());
        } else if (summaryRes.status === 404) {
          setSummary(null);
        }
      } catch {
        if (!cancelled) setError("Unable to refresh algorithm status.");
      }
    }
    poll();
    const id = setInterval(poll, 3000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [apiBase, refreshToken]);

  async function toggleAlgorithm() {
    if (toggleBusy) return;
    setToggleBusy(true);
    setError("");
    try {
      const action = status?.running ? "stop" : "start";
      const res = await fetch(`${apiBase}/algo/auto/${action}`, { method: "POST" });
      if (!res.ok) throw new Error(`algorithm ${action} failed: ${res.status}`);
      await refreshData();
      onRefresh();
    } catch (e) {
      setError(String(e?.message || e));
    } finally {
      setToggleBusy(false);
    }
  }

  async function downloadZip() {
    if (downloadBusy) return;
    setDownloadBusy(true);
    setError("");
    try {
      const res = await fetch(`${apiBase}/export/run?format=csv`);
      if (res.status === 404) {
        setError("Start the algorithm before downloading run data.");
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
      setDownloadBusy(false);
    }
  }

  const startedAt = summary?.run_started_at;
  const runActive = !!startedAt;
  const running = screenshotMode || !!status?.running;
  const fmt = (s) => (s?.count ?? 0) + " rows";

  return (
    <section className="algo-run-controls">
      <div className="algo-control-status-row">
        <span>Continuous dispatch status</span>
        <span className={`system-run-state ${running ? "running" : "stopped"}`}>
          {running ? "Running" : "Stopped"}
        </span>
      </div>

      <div className="algo-action-row">
        <button className="algo-action-primary" onClick={toggleAlgorithm} disabled={toggleBusy}>
          {toggleBusy ? "Updating..." : running ? "Stop Algorithm" : "Start Algorithm"}
        </button>
        <button
          className="algo-action-button"
          onClick={async () => {
            await onTest();
            onRefresh();
          }}
          disabled={applyBusy || !canTest}
          title="Compute and dispatch one cycle using the latest available tick."
        >
          {applyBusy ? "Testing..." : "Test One Tick"}
        </button>
        <button
          className="algo-action-button"
          onClick={downloadZip}
          disabled={downloadBusy || !runActive}
          title={runActive ? "" : "Start the algorithm before exporting data."}
        >
          {downloadBusy ? "Preparing..." : "Download Run CSV"}
        </button>
        <button
          className="algo-action-button"
          onClick={async () => {
            setError("");
            await refreshData();
            onRefresh();
          }}
        >
          Refresh Data
        </button>
      </div>

      <div className="algo-run-summary">
        <div>
          <strong>Run started</strong>
          <span>{startedAt ? new Date(startedAt).toLocaleString() : "-"}</span>
        </div>
        <div>
          <strong>Grid</strong>
          <span>{runActive ? fmt(summary?.grid_snapshots) : "-"}</span>
        </div>
        <div>
          <strong>Modules</strong>
          <span>{runActive ? fmt(summary?.module_snapshots) : "-"}</span>
        </div>
        <div>
          <strong>Decisions</strong>
          <span>{runActive ? fmt(summary?.naive_decisions) : "-"}</span>
        </div>
        <div>
          <strong>Last regime</strong>
          <span>{status?.last_regime || "-"}</span>
        </div>
        <div>
          <strong>Applied</strong>
          <span>{status?.applied_count ?? "-"}</span>
        </div>
        <div>
          <strong>Skipped</strong>
          <span>{status?.skipped_count ?? "-"}</span>
        </div>
      </div>

      {applyMsg && <p className="naive-apply-msg">{applyMsg}</p>}
      {status?.last_error && <p className="algo-warning">Algorithm error: {status.last_error}</p>}
      {error && (
        <p className="algo-warning">{error}</p>
      )}
    </section>
  );
}

function ModulePlotCard({
  role,
  data,
  status: moduleStatus,
  history,
  theme = "dark",
  advanced = false,
  host = "",
  onCmd,
  lastBusVoltage,
}) {
  const status = getModuleStatus(data, moduleStatus);
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
  const lines = (ROLE_LINES[role] || []).map((line) => {
    const darker = {
      "#00e676": "#1f7d3b",
      "#00f0ff": "#2e5f93",
      "#ffc800": "#7d5a00",
      "#ff9100": "#a65a00",
      "#b67ad9": "#7a4cb8",
      "#ff4d6d": "#b63a59",
      "#5ec9c0": "#2f7f7a",
    };

    return isLightTheme ? { ...line, color: darker[line.color] || line.color } : line;
  });
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

      <UnifiedLineChart
        data={history}
        xKey="timestamp"
        height={220}
        theme={theme}
        compact
        lines={lines.map((line) => ({ ...line, label: line.name }))}
      />

      {advanced && (
        <ModuleAdvancedPanel
          role={role}
          data={data}
          status={moduleStatus}
          host={host}
          onCmd={onCmd}
          lastBusVoltage={lastBusVoltage}
        />
      )}
    </section>
  );
}

export default function SMPS({
  apiBase,
  theme = "dark",
  showAdvanced = false,
  screenshotMode = false,
  activeAlgorithm,
  autoStatus,
  runCost,
  onLiveData,
}) {
  const [modules, setModules] = useState({});
  const [statuses, setStatuses] = useState({});
  const histRef = useRef(Object.fromEntries(ROLES.map((r) => [r, []])));
  const [hist, setHist] = useState(Object.fromEntries(ROLES.map((r) => [r, []])));
  const [overviewData, setOverviewData] = useState([]);
  const [naive, setNaive] = useState(null);
  const [applyBusy, setApplyBusy] = useState(false);
  const [applyMsg, setApplyMsg] = useState("");
  const [moduleHosts, setModuleHosts] = useState({});

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
      setSwitchAlgoMsg("");
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

  async function sendModuleCommand(role, payload) {
    try {
      const response = await fetch(`${apiBase}/modules/cmd/${role}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return response.ok;
    } catch (err) {
      console.error(`Failed to send ${role} command`, err);
      return false;
    }
  }

  useEffect(() => {
    let cancelled = false;
    let timerId;

    async function poll() {
      try {
        const [modulesRes, statusesRes, naiveRes] = await Promise.all([
          fetch(`${apiBase}/modules/latest`, { cache: "no-store" }),
          fetch(`${apiBase}/modules/status`, { cache: "no-store" }),
          fetch(`${apiBase}/algo/naive`, { cache: "no-store" }),
        ]);
        if (!modulesRes.ok) return;

        const [data, statusesData, naiveData] = await Promise.all([
          modulesRes.json(),
          statusesRes.ok ? statusesRes.json() : null,
          naiveRes.ok ? naiveRes.json() : null,
        ]);
        if (cancelled) return;

        const displayedModules = screenshotMode
          ? Object.fromEntries(
              ROLES.map((role) => [
                role,
                {
                  ...(data?.[role] || {}),
                  role,
                  trip: 0,
                  trip_reason: "",
                  wd: 0,
                  enable: 1,
                  wifi_connected: true,
                  backend_post_ok: true,
                },
              ])
            )
          : data || {};
        const displayedStatuses = screenshotMode
          ? Object.fromEntries(
              ROLES.map((role) => [
                role,
                {
                  ...(statusesData?.[role] || {}),
                  online: true,
                  age_s: 0.42,
                  last_seen: statusesData?.[role]?.last_seen || new Date().toISOString(),
                },
              ])
            )
          : statusesData;

        setModules(displayedModules);
        if (displayedStatuses) setStatuses(displayedStatuses);
        onLiveData?.(displayedModules, displayedStatuses);
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
      } finally {
        if (!cancelled) {
          timerId = window.setTimeout(poll, document.hidden ? 5000 : 1500);
        }
      }
    }

    poll();
    return () => {
      cancelled = true;
      window.clearTimeout(timerId);
    };
  }, [apiBase, onLiveData, screenshotMode]);

  useEffect(() => {
    let cancelled = false;
    let timerId;

    async function loadHistory() {
      try {
        const [snapshotsRes, pvRes, gridRes, exportRes, hostsRes] = await Promise.all([
          fetch(`${apiBase}/snapshots?limit=${OVERVIEW_LIMIT}`),
          fetch(`${apiBase}/modules/snapshots/pv?limit=${OVERVIEW_LIMIT}`),
          fetch(`${apiBase}/modules/snapshots/grid?limit=${OVERVIEW_LIMIT}`),
          fetch(`${apiBase}/modules/snapshots/export?limit=${OVERVIEW_LIMIT}`),
          fetch(`${apiBase}/algo/module-hosts`),
        ]);
        const [snapshotsData, pvData, gridData, exportData, hostsData] = await Promise.all([
          snapshotsRes.ok ? snapshotsRes.json() : null,
          pvRes.ok ? pvRes.json() : null,
          gridRes.ok ? gridRes.json() : null,
          exportRes.ok ? exportRes.json() : null,
          hostsRes.ok ? hostsRes.json() : null,
        ]);
        if (cancelled) return;

        if (
          Array.isArray(snapshotsData) &&
          Array.isArray(pvData) &&
          Array.isArray(gridData) &&
          Array.isArray(exportData)
        ) {
          setOverviewData(buildOverviewSeries(
            snapshotsData,
            pvData,
            gridData,
            exportData,
          ));
        }
        if (hostsData?.hosts) setModuleHosts(hostsData.hosts);
      } catch (err) {
        console.error("Failed to fetch telemetry history", err);
      } finally {
        if (!cancelled) timerId = window.setTimeout(loadHistory, 10000);
      }
    }

    loadHistory();
    return () => {
      cancelled = true;
      window.clearTimeout(timerId);
    };
  }, [apiBase]);

  return (
    <div className="smps-plots-page">
      <OverviewGraphCard
        data={overviewData}
        theme={theme}
      />
      <BusOverviewCard
        vbus={getBusVoltage(modules)}
        busHistory={buildGlobalTelemetryHistory(hist)}
        theme={theme}
        advanced={showAdvanced}
      />
      <NaiveDispatchCard
        apiBase={apiBase}
        naive={naive}
        advanced={showAdvanced}
        screenshotMode={screenshotMode}
        activeAlgorithm={activeAlgorithm}
        autoStatus={autoStatus}
        runCost={runCost}
        applyBusy={applyBusy}
        applyMsg={applyMsg}
        onApply={applyNaiveNow}
        activeAlgoId={activeAlgoId}
        onSwitchAlgo={switchAlgorithm}
        switchingAlgo={switchingAlgo}
        switchAlgoMsg={switchAlgoMsg}
      />
      <div className="smps-plot-columns">
        {ROLE_COLUMNS.map((roles, columnIndex) => (
          <div className="smps-plot-column" key={columnIndex}>
            {roles.map((role) => (
              <ModulePlotCard
                key={role}
                role={role}
                data={modules?.[role]}
                status={statuses?.[role]}
                history={hist[role]}
                theme={theme}
                advanced={showAdvanced}
                host={moduleHosts?.[role]}
                onCmd={(payload) => sendModuleCommand(role, payload)}
                lastBusVoltage={getBusVoltage(modules)}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
