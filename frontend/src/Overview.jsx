import { useCallback, useEffect, useRef, useState } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import {
  XAxis,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from "recharts";
import SMPS from "./SMPS";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";
const THEME_STORAGE_KEY = "sg-theme";

const MODULE_ROLES = ["pv", "grid", "export", "cap", "led"];

function formatAlgorithmStatus(algorithm) {
  const raw = String(algorithm?.id || algorithm?.name || "naive").toLowerCase();
  return raw.includes("smart") ? "Smart" : "Naive";
}

function getModuleStatus(module, status) {
  if (!status || status.online === false) return "offline";
  if (module?.trip) return "trip";
  if (module?.wd) return "watchdog";
  if (module && module.enable === false) return "disabled";

  return "online";
}

function StatusDot({ status }) {
  return <span className={`module-status-dot module-status-${status}`} />;
}

function DashboardLayout({ theme, onToggleTheme, activeView = "energy" }) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [latest, setLatest] = useState(null);
  const [snapshots, setSnapshots] = useState([]);
  const [modules, setModules] = useState({});
  const [moduleStatuses, setModuleStatuses] = useState({});
  const [activeAlgorithm, setActiveAlgorithm] = useState(null);
  const [autoStatus, setAutoStatus] = useState(null);
  const [runCost, setRunCost] = useState(null);
  const [pollerSource, setPollerSource] = useState({
    mode: "azure",
    status: {},
  });
  const [sourceSwitching, setSourceSwitching] = useState(false);
  const fetchInFlight = useRef(false);
  const handleSmpsLiveData = useCallback((nextModules, nextStatuses) => {
    if (nextModules) setModules(nextModules);
    if (nextStatuses) setModuleStatuses(nextStatuses);
  }, []);

  const fetchData = useCallback(async () => {
    if (fetchInFlight.current) return;
    fetchInFlight.current = true;

    try {
      const commonRequests = [
        fetch(`${API_BASE}/latest`),
        fetch(`${API_BASE}/poller/source`),
        fetch(`${API_BASE}/algo/active`, { cache: "no-store" }),
        fetch(`${API_BASE}/algo/auto/status`, { cache: "no-store" }),
      ];
      const overviewRequests =
        activeView === "energy"
          ? [
              fetch(`${API_BASE}/snapshots?limit=50`),
              fetch(`${API_BASE}/modules/latest`),
              fetch(`${API_BASE}/modules/status`, { cache: "no-store" }),
            ]
          : [];
      const responses = await Promise.all([...commonRequests, ...overviewRequests]);
      const [latestRes, sourceRes, algorithmRes, autoStatusRes] = responses;

      if (!latestRes.ok) {
        throw new Error("Backend API request failed");
      }

      const [latestData, sourceData, algorithmData, autoStatusData] = await Promise.all([
        latestRes.json(),
        sourceRes.ok ? sourceRes.json() : null,
        algorithmRes.ok ? algorithmRes.json() : null,
        autoStatusRes.ok ? autoStatusRes.json() : null,
      ]);

      setLatest(latestData?.error ? null : latestData);
      setActiveAlgorithm(algorithmData);
      setAutoStatus(autoStatusData);
      if (sourceData) setPollerSource(sourceData);

      if (activeView === "energy") {
        const [snapshotsRes, modulesRes, statusesRes] = responses.slice(4);
        const [snapshotsData, modulesData, statusesData] = await Promise.all([
          snapshotsRes?.ok ? snapshotsRes.json() : null,
          modulesRes?.ok ? modulesRes.json() : null,
          statusesRes?.ok ? statusesRes.json() : null,
        ]);
        if (Array.isArray(snapshotsData)) setSnapshots(snapshotsData);
        if (modulesData) setModules(modulesData);
        if (statusesData) setModuleStatuses(statusesData);
      }

      if (autoStatusData?.started_at) {
        const runCostRes = await fetch(`${API_BASE}/algo/run/cost`, {
          cache: "no-store",
        });
        setRunCost(runCostRes.ok ? await runCostRes.json() : null);
      } else {
        setRunCost(null);
      }
    } catch (err) {
      console.error("Failed to fetch dashboard data", err);
    } finally {
      fetchInFlight.current = false;
    }
  }, [activeView]);

  async function togglePollerSource() {
    const mode = pollerSource.mode === "fixed" ? "azure" : "fixed";
    setSourceSwitching(true);
    try {
      const response = await fetch(`${API_BASE}/poller/source`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode }),
      });
      if (!response.ok) throw new Error("Failed to switch poller source");
      setPollerSource(await response.json());
      await fetchData();
    } catch (err) {
      console.error("Failed to switch poller source", err);
    } finally {
      setSourceSwitching(false);
    }
  }

  useEffect(() => {
    let stopped = false;
    let timerId;

    const poll = async () => {
      await fetchData();
      if (!stopped) {
        timerId = window.setTimeout(poll, document.hidden ? 5000 : 2000);
      }
    };
    const handleVisibility = () => {
      if (document.hidden) return;
      window.clearTimeout(timerId);
      poll();
    };

    poll();
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      stopped = true;
      window.clearTimeout(timerId);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [fetchData]);

  const onlineModuleCount = MODULE_ROLES.filter(
    (role) => getModuleStatus(modules?.[role], moduleStatuses?.[role]) === "online"
  ).length;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-inner">
          <Link
            className="topbar-logo"
            to="/"
            aria-label="Home"
          >
            <img src="/oct.png" alt="Octopus" className="topbar-logo-img" />
          </Link>

          <div className="topbar-status" aria-label="Live system status">
            <div className="topbar-status-item">
              <span>Tick</span>
              <strong>{latest?.tick ?? "-"}</strong>
            </div>
            <div className="topbar-status-item">
              <span>Boards</span>
              <strong>{onlineModuleCount}/{MODULE_ROLES.length}</strong>
            </div>
            <div className="topbar-status-item">
              <span>Algorithm</span>
              <strong className={autoStatus?.running ? "is-running" : "is-stopped"}>
                {formatAlgorithmStatus(activeAlgorithm)}
              </strong>
            </div>
          </div>

          <div className="topbar-spacer" />


          <button
            className={`poller-source-toggle poller-source-${pollerSource.mode}`}
            onClick={togglePollerSource}
            disabled={sourceSwitching}
            title={
              pollerSource.mode === "fixed"
                ? "Stop the fixed dataset and resume Azure polling"
                : "Stop Azure polling and play the fixed 60-tick dataset"
            }
          >
            <span className="poller-source-dot" aria-hidden="true" />
            {sourceSwitching
              ? "Switching..."
              : pollerSource.mode === "fixed"
                ? pollerSource.status?.completed
                  ? "Fixed complete"
                  : `Fixed ${pollerSource.status?.tick ?? 0}/59`
                : "Fixed Dataset"}
          </button>

          <button
            className="theme-toggle"
            onClick={onToggleTheme}
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
          >
            {theme === "dark" ? "Light mode" : "Dark mode"}
          </button>

          <div className="topbar-user">
            <span>Watt's Up</span>
            <span className="topbar-avatar">W</span>
          </div>

        </div>
      </header>

      <div className="app-layout">
        <aside className="sidebar">
          <Link
            to="/"
            className={`nav-item ${activeView === "energy" ? "active" : ""}`}
          >
            <span className="nav-icon">⌂</span>
            <span>Overview</span>
          </Link>

          <Link
            className={`nav-item ${activeView === "overview" ? "active" : ""}`}
            to="/smps"
          >
            <span className="nav-icon">↗</span>
            <span>SMPS</span>
          </Link>

          <div className="nav-item nav-item-muted">
            <span className="nav-icon">ϟ</span>
            <span>My Energy</span>
          </div>

          <div className="nav-item nav-item-muted">
            <span className="nav-icon">£</span>
            <span>Payments</span>
          </div>

          <div className="nav-item nav-item-muted">
            <span className="nav-icon">◎</span>
            <span>Octoplus</span>
          </div>
        </aside>

        <main className="main-content">
          {/* {activeView === "energy" && (
            <div className="hero-octopus">
              <DotLottieReact
                src="/porthole.lottie"
                loop
                autoplay
                className="hero-octopus-lottie"
              />
            </div>
          )} */}

          {activeView === "overview" ? (
            <div className="dashboard-container">
              <div className="page-heading-row">
                <div>
                  <h1 className="page-title">SMPS</h1>
                  <p className="date-subtitle">
                    Board health, live electrical readings, and telemetry trends.
                  </p>
                </div>
                <button
                  className={`advanced-toggle ${showAdvanced ? "active" : ""}`}
                  onClick={() => setShowAdvanced((visible) => !visible)}
                  aria-expanded={showAdvanced}
                >
                  {showAdvanced ? "Hide advanced" : "Advanced"}
                </button>
              </div>

              <SMPS
                apiBase={API_BASE}
                theme={theme}
                showAdvanced={showAdvanced}
                activeAlgorithm={activeAlgorithm}
                autoStatus={autoStatus}
                runCost={runCost}
                onLiveData={handleSmpsLiveData}
              />
            </div>
          ) : (
            <HomeContent
              latest={latest}
              snapshots={snapshots}
              modules={modules}
              moduleStatuses={moduleStatuses}
              activeAlgorithm={activeAlgorithm}
              autoStatus={autoStatus}
              runCost={runCost}
              theme={theme}
            />
          )}
        </main>
      </div>
    </div>
  );
}

function HomeContent({
  latest,
  snapshots,
  modules,
  moduleStatuses,
  activeAlgorithm,
  autoStatus,
  runCost,
  theme = "dark",
}) {
  const isLightTheme = theme === "light";
  const axisColor = isLightTheme ? "#38475f" : "#a69ec4";
  const tooltipBackground = isLightTheme ? "#ffffff" : "#14052e";
  const tooltipBorder = isLightTheme ? "#cfd9e8" : "#27134d";
  const tooltipText = isLightTheme ? "#1a2333" : "#e6e6e6";
  const demandFill = isLightTheme ? "#1f4f83" : "#00f0ff";
  const solarFill = isLightTheme ? "#7d5a00" : "#ffc800";
  const accentText = isLightTheme ? "#12325f" : "#00f0ff";
  const secondaryText = isLightTheme ? "#4f5f7c" : "#a69ec4";
  const cardTitleColor = isLightTheme ? "#1a2333" : "#ffffff";

  return (
    <div className="dashboard-container">
      <div>
        <h1 className="page-title" style={{ color: cardTitleColor }}>Overview</h1>
        <p className="date-subtitle">
          Live system health, energy market data, and algorithm performance.
        </p>
      </div>

      {/* <div className="tabs-container">
        <div className="tab active">Day</div>
        <div className="tab">Week</div>
        <div className="tab">Month</div>
        <div className="tab">Year</div>
        <div className="tab">Custom</div>
      </div> */}

      <OperationalSummary
        activeAlgorithm={activeAlgorithm}
        autoStatus={autoStatus}
        runCost={runCost}
      />

      <section className="card">
        <div className="card-header">
          <span className="icon-green">●</span>
          <span style={{ color: cardTitleColor }}>Module Status</span>
        </div>

        <div className="module-status-grid">
          {MODULE_ROLES.map((role) => {
            const status = getModuleStatus(modules?.[role], moduleStatuses?.[role]);

            return (
              <div key={role} className="module-status-item">
                <div className="module-status-left">
                  <StatusDot status={status} />
                  <span className="module-status-role">{role.toUpperCase()}</span>
                </div>

                <span className={`module-status-label module-status-text-${status}`}>
                  {status}
                </span>
              </div>
            );
          })}
        </div>
      </section>

      <section className="card">
        <div className="card-header">
          <span className="icon-cyan">✦</span>
          <span style={{ color: cardTitleColor }}>Grid State</span>
        </div>

        <div className="chart-wrapper">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={snapshots}>
              <XAxis
                dataKey="tick"
                stroke={axisColor}
                tick={{ fontSize: 12 }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                formatter={(value, name) => [
                  typeof value === "number" ? value.toFixed(3) : value,
                  name,
                ]}
                contentStyle={{
                  backgroundColor: tooltipBackground,
                  borderColor: tooltipBorder,
                  borderRadius: "var(--radius-control)",
                }}
                itemStyle={{ color: tooltipText }}
              />
              <Bar
                dataKey="instant_demand"
                name="Demand (W)"
                fill={demandFill}
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-wrapper">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={snapshots}>
              <XAxis
                dataKey="tick"
                stroke={axisColor}
                tick={{ fontSize: 12 }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                formatter={(value, name) => [
                  typeof value === "number" ? value.toFixed(3) : value,
                  name,
                ]}
                contentStyle={{
                  backgroundColor: tooltipBackground,
                  borderColor: tooltipBorder,
                  borderRadius: "var(--radius-control)",
                }}
                itemStyle={{ color: tooltipText }}
              />
              <Bar
                dataKey="sun"
                name="Solar Input"
                fill={solarFill}
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="stats-row">
          <div className="stat-box">
            <p style={{ color: secondaryText }}>Current Demand</p>
            <h3>
              {typeof latest?.instant_demand === "number"
                ? `${latest.instant_demand.toFixed(3)} W`
                : "-"}
            </h3>
          </div>

          <div className="stat-box">
            <p style={{ color: secondaryText }}>Solar Input</p>
            <h3>
              {typeof latest?.sun === "number" ? `${latest.sun.toFixed(3)}%` : "-"}
            </h3>
          </div>
        </div>
      </section>

      <section className="card">
        <div className="card-header">
          <span className="icon-orange">⚡</span>
          <span style={{ color: cardTitleColor }}>Deferrable Loads</span>
        </div>

        {latest?.deferables?.length ? (
          latest.deferables.map((job, idx) => {
            const now = latest.tick;
            const totalWindow = job.end - job.start;
            const elapsed = Math.min(Math.max(now - job.start, 0), totalWindow);
            const progress = totalWindow > 0 ? (elapsed / totalWindow) * 100 : 0;
            const expired = now > job.end;

            return (
              <div key={idx} className={`deferable-job ${expired ? "expired" : ""}`}>
                <div className="job-header">
                  <span>Job {idx + 1}</span>
                  <span>{Number(job.energy).toFixed(3)} J</span>
                </div>

                <div className="progress-labels">
                  <span>Tick {job.start}</span>
                  <span>Tick {job.end}</span>
                </div>

                <div className="progress-bg">
                  <div className="progress-fill" style={{ width: `${progress}%` }} />
                </div>
              </div>
            );
          })
        ) : (
          <p>No deferrable loads</p>
        )}
      </section>

      <section className="two-col">
        <div className="insight-card">
          <div className="sub" style={{ color: secondaryText }}>Current Market...</div>
          <div className="val" style={{ color: accentText }}>
            {typeof latest?.buy_price === "number"
              ? latest.buy_price.toFixed(3)
              : "-"}
          </div>
          <div>Buy Price (pence/kWh)</div>
          <p style={{ fontSize: 12, color: secondaryText, marginTop: 12 }}>
            Grid import price for this current tick.
          </p>
        </div>

        <div className="insight-card">
          <div className="sub" style={{ color: secondaryText }}>Exporting power...</div>
          <div className="val" style={{ color: isLightTheme ? "#1f7d3b" : "#00e676" }}>
            {typeof latest?.sell_price === "number"
              ? latest.sell_price.toFixed(3)
              : "-"}
          </div>
          <div>Sell Price (pence/kWh)</div>
          <p
            style={{
              fontSize: 12,
              color: secondaryText,
              marginTop: 12,
              position: "relative",
              zIndex: 2,
            }}
          >
            Earnings if feeding back to grid.
          </p>
        </div>
      </section>

    </div>
  );
}

function OperationalSummary({ activeAlgorithm, autoStatus, runCost }) {
  const todayCost = runCost?.today;
  const netCost = todayCost?.net_cost;
  const netCostLabel =
    typeof netCost === "number"
      ? `${netCost < 0 ? "-" : ""}${Math.abs(netCost).toFixed(3)}`
      : "—";

  return (
    <section className="system-summary-grid" aria-label="Algorithm and cost summary">
      <div className="system-summary-card">
        <span className="system-summary-label">Active algorithm</span>
        <strong>{activeAlgorithm?.name || activeAlgorithm?.id || "—"}</strong>
        <span className={`system-run-state ${autoStatus?.running ? "running" : "stopped"}`}>
          {autoStatus?.running ? "Running" : "Stopped"}
        </span>
      </div>

      <div className="system-summary-card">
        <span className="system-summary-label">Import cost today</span>
        <strong>
          {typeof todayCost?.import_cost === "number" ? todayCost.import_cost.toFixed(3) : "—"}
        </strong>
        <span>
          {typeof todayCost?.import_energy_J === "number"
            ? `${todayCost.import_energy_J.toFixed(3)} J imported`
            : "No run data"}
        </span>
      </div>

      <div className="system-summary-card">
        <span className="system-summary-label">Export revenue today</span>
        <strong>
          {typeof todayCost?.export_revenue === "number"
            ? todayCost.export_revenue.toFixed(3)
            : "—"}
        </strong>
        <span>
          {typeof todayCost?.export_energy_J === "number"
            ? `${todayCost.export_energy_J.toFixed(3)} J exported`
            : "No run data"}
        </span>
      </div>

      <div className="system-summary-card">
        <span className="system-summary-label">Net cost today</span>
        <strong
          className={
            typeof netCost === "number" && netCost < 0 ? "cost-positive" : "cost-negative"
          }
        >
          {netCostLabel}
        </strong>
        <span>
          {typeof netCost === "number"
            ? netCost < 0
              ? "Net earned"
              : "Net paid"
            : "Start an algorithm run"}
        </span>
      </div>
    </section>
  );
}

function Overview() {
  const location = useLocation();
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem(THEME_STORAGE_KEY);
    return saved === "light" ? "light" : "dark";
  });

  useEffect(() => {
    document.body.setAttribute("data-theme", theme);
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  if (location.pathname === "/smpsmodule") {
    return <Navigate to="/smps" replace />;
  }
  if (location.pathname !== "/" && location.pathname !== "/smps") {
    return <Navigate to="/" replace />;
  }

  return (
    <DashboardLayout
      theme={theme}
      activeView={location.pathname === "/smps" ? "overview" : "energy"}
      onToggleTheme={() => setTheme((prev) => (prev === "dark" ? "light" : "dark"))}
    />
  );
}

export default Overview;
