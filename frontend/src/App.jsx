import { useEffect, useState } from "react";
import { Routes, Route, Link } from "react-router-dom";
import { DotLottieReact } from "@lottiefiles/dotlottie-react";
import {
  XAxis,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from "recharts";
import SmpsModules from "./SmpsModules";
import SMPS from "./SMPS";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";
const THEME_STORAGE_KEY = "sg-theme";

const MODULE_ROLES = ["pv", "grid", "export", "cap", "led"];
const STALE_AFTER_MS = 5000;

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

function StatusDot({ status }) {
  return <span className={`module-status-dot module-status-${status}`} />;
}

function DashboardLayout({ theme, onToggleTheme }) {
  const [activeView, setActiveView] = useState("energy");
  const [latest, setLatest] = useState(null);
  const [snapshots, setSnapshots] = useState([]);
  const [modules, setModules] = useState({});
  const [pollerTestMode, setPollerTestMode] = useState(false);
  const [pollerTestModeBusy, setPollerTestModeBusy] = useState(false);

  async function fetchPollerTestMode() {
    try {
      const res = await fetch(`${API_BASE}/poller/test-mode`, { cache: "no-store" });
      if (!res.ok) return;
      const data = await res.json();
      setPollerTestMode(Boolean(data?.enabled));
    } catch (err) {
      console.error("Failed to fetch poller test mode", err);
    }
  }

  async function togglePollerTestMode() {
    const next = !pollerTestMode;
    setPollerTestModeBusy(true);
    try {
      const res = await fetch(`${API_BASE}/poller/test-mode`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: next }),
      });
      if (!res.ok) {
        throw new Error(`toggle failed: ${res.status}`);
      }
      const data = await res.json();
      setPollerTestMode(Boolean(data?.enabled));
    } catch (err) {
      console.error("Failed to toggle poller test mode", err);
    } finally {
      setPollerTestModeBusy(false);
    }
  }

  async function fetchData() {
    try {
      const [latestRes, snapshotsRes, modulesRes] = await Promise.all([
        fetch(`${API_BASE}/latest`),
        fetch(`${API_BASE}/snapshots?limit=50`),
        fetch(`${API_BASE}/modules/latest`),
      ]);

      if (!latestRes.ok || !snapshotsRes.ok) {
        throw new Error("Backend API request failed");
      }

      const [latestData, snapshotsData] = await Promise.all([
        latestRes.json(),
        snapshotsRes.json(),
      ]);

      const modulesData = modulesRes.ok ? await modulesRes.json() : {};

      setLatest(latestData?.error ? null : latestData);
      setSnapshots(Array.isArray(snapshotsData) ? snapshotsData : []);
      setModules(modulesData || {});
    } catch (err) {
      console.error("Failed to fetch dashboard data", err);
      setLatest(null);
      setSnapshots([]);
      setModules({});
    }
  }

  useEffect(() => {
    fetchData();
    fetchPollerTestMode();
    const interval = setInterval(fetchData, 1000);
    const testModeInterval = setInterval(fetchPollerTestMode, 3000);
    return () => {
      clearInterval(interval);
      clearInterval(testModeInterval);
    };
  }, []);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-inner">
          <button
            className="topbar-logo"
            onClick={() => setActiveView("energy")}
            aria-label="Home"
          >
            <img src="/oct.png" alt="Octopus" className="topbar-logo-img" />
          </button>

          <nav className="topbar-nav">
            <button className="topbar-link">Energy</button>
            <button className="topbar-link">Heat pumps</button>
            <button className="topbar-link">Solar & battery</button>
            <button className="topbar-link">Electric vehicles</button>
          </nav>

          <div className="topbar-spacer" />

          <button className="topbar-link topbar-support">Support</button>

          <button
            className={`test-mode-toggle ${pollerTestMode ? "on" : ""}`}
            onClick={togglePollerTestMode}
            disabled={pollerTestModeBusy}
            aria-label="Toggle poller test mode"
          >
            {pollerTestModeBusy
              ? "Updating..."
              : pollerTestMode
                ? "Test mode: ON"
                : "Test mode: OFF"}
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
          <div
            className={`nav-item ${activeView === "energy" ? "active" : ""}`}
            onClick={() => setActiveView("energy")}
          >
            <span className="nav-icon">🏠</span>
            <span>Home</span>
          </div>

          <Link className="nav-item" to="/smps">
            <span className="nav-icon">📈</span>
            <span>SMPS Overview</span>
          </Link>

          <div
            className={`nav-item ${activeView === "smps" ? "active" : ""}`}
            onClick={() => setActiveView("smps")}
          >
            <span className="nav-icon">🔌</span>
            <span>SMPS Modules</span>
          </div>

          <div className="nav-item">
            <span className="nav-icon">⚡</span>
            <span>My Energy</span>
          </div>

          <div className="nav-item">
            <span className="nav-icon">💳</span>
            <span>Payments</span>
          </div>

          <div className="nav-item">
            <span className="nav-icon">🐙</span>
            <span>Octoplus</span>
          </div>
        </aside>

        <main className="main-content">
          <div className="hero-octopus">
            <DotLottieReact
              src="/porthole.lottie"
              loop
              autoplay
              className="hero-octopus-lottie"
            />
          </div>

          {activeView === "smps" ? (
            <div className="dashboard-container" style={{ maxWidth: "100%" }}>
              <h1 className="page-title">SMPS Modules</h1>
              <p className="date-subtitle">
                Live telemetry from backend DB. Commands are proxyed through the
                backend API.
              </p>
              <SmpsModules apiBase={API_BASE} theme={theme} />
            </div>
          ) : (
            <HomeContent latest={latest} snapshots={snapshots} modules={modules} theme={theme} />
          )}
        </main>
      </div>
    </div>
  );
}

function HomeContent({ latest, snapshots, modules, theme = "dark" }) {
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
      <h1 className="page-title" style={{ color: cardTitleColor }}>My energy insights</h1>

      <div className="tabs-container">
        <div className="tab active">Day</div>
        <div className="tab">Week</div>
        <div className="tab">Month</div>
        <div className="tab">Year</div>
        <div className="tab">Custom</div>
      </div>

      <p className="date-subtitle">Latest Tick: {latest?.tick ?? "..."}</p>

      <section className="card">
        <div className="card-header">
          <span className="icon-green">●</span>
          <span style={{ color: cardTitleColor }}>Module Status</span>
        </div>

        <div className="module-status-grid">
          {MODULE_ROLES.map((role) => {
            const status = getModuleStatus(modules?.[role]);

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
                contentStyle={{
                  backgroundColor: tooltipBackground,
                  borderColor: tooltipBorder,
                  borderRadius: "8px",
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
                contentStyle={{
                  backgroundColor: tooltipBackground,
                  borderColor: tooltipBorder,
                  borderRadius: "8px",
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
                ? `${latest.instant_demand.toFixed(2)} W`
                : "-"}
            </h3>
          </div>

          <div className="stat-box">
            <p style={{ color: secondaryText }}>Solar Input</p>
            <h3>
              {typeof latest?.sun === "number" ? `${latest.sun.toFixed(0)}%` : "-"}
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
            const remaining = Math.max(job.end - now, 0);
            const expired = now > job.end;
            const notStarted = now < job.start;

            return (
              <div key={idx} className={`deferable-job ${expired ? "expired" : ""}`}>
                <div className="job-header">
                  <span>Job {idx + 1}</span>
                  <span>{Number(job.energy).toFixed(1)} J</span>
                </div>

                <div className="job-meta">
                  tick {job.start} → {job.end} ·{" "}
                  {expired
                    ? "expired"
                    : notStarted
                      ? `starts in ${job.start - now} ticks`
                      : `${remaining} ticks left`}
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
              ? latest.buy_price.toFixed(0)
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
              ? latest.sell_price.toFixed(0)
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

      <section className="card">
        <h2 style={{ color: cardTitleColor }}>Get your geek on</h2>
        <p style={{ color: secondaryText, marginBottom: 20 }}>
          Backend snapshot dataset from the local DB.
        </p>

        <div
          style={{
            padding: "12px",
            background: isLightTheme ? "rgba(18,50,95,0.06)" : "rgba(255,255,255,0.05)",
            borderRadius: "8px",
            color: accentText,
          }}
        >
          ✦ {snapshots.length} data points loaded
        </div>

        <button className="btn-pink" onClick={() => console.log(snapshots)}>
          Log smart data
        </button>
      </section>
    </div>
  );
}

function SmpsStandalonePage({ theme, onToggleTheme }) {
  return (
    <div className="smps-route-shell">
      <aside className="sidebar smps-route-sidebar">
        <Link className="nav-item" to="/">
          <span className="nav-icon">🏠</span>
          <span>Home</span>
        </Link>

        <div className="nav-item active" aria-current="page">
          <span className="nav-icon">📈</span>
          <span>SMPS Overview</span>
        </div>

        <Link className="nav-item" to="/smpsmodule">
          <span className="nav-icon">🔌</span>
          <span>SMPS Modules</span>
        </Link>

        <button className="nav-item nav-item-button" onClick={onToggleTheme}>
          <span className="nav-icon">◐</span>
          <span>{theme === "dark" ? "Light mode" : "Dark mode"}</span>
        </button>
      </aside>

      <div className="smps-route-content dashboard-container" style={{ maxWidth: "100%" }}>
        <h1 className="page-title">SMPS Overview</h1>
        <p className="date-subtitle">Module telemetry plots from backend DB.</p>
        <SMPS apiBase={API_BASE} theme={theme} />
      </div>
    </div>
  );
}

function SmpsModuleStandalonePage({ theme, onToggleTheme }) {
  return (
    <div className="smps-route-shell">
      <aside className="sidebar smps-route-sidebar">
        <Link className="nav-item" to="/">
          <span className="nav-icon">🏠</span>
          <span>Home</span>
        </Link>

        <Link className="nav-item" to="/smps">
          <span className="nav-icon">📈</span>
          <span>SMPS Overview</span>
        </Link>

        <div className="nav-item active" aria-current="page">
          <span className="nav-icon">🔌</span>
          <span>SMPS Modules</span>
        </div>

        <button className="nav-item nav-item-button" onClick={onToggleTheme}>
          <span className="nav-icon">◐</span>
          <span>{theme === "dark" ? "Light mode" : "Dark mode"}</span>
        </button>
      </aside>

      <div className="smps-route-content smps-standalone-page">
        <SmpsModules apiBase={API_BASE} theme={theme} />
      </div>
    </div>
  );
}

function App() {
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem(THEME_STORAGE_KEY);
    return saved === "light" ? "light" : "dark";
  });

  useEffect(() => {
    document.body.setAttribute("data-theme", theme);
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  return (
    <Routes>
      <Route
        path="/"
        element={<DashboardLayout theme={theme} onToggleTheme={() => setTheme((prev) => (prev === "dark" ? "light" : "dark"))} />}
      />
      <Route
        path="/smps"
        element={<SmpsStandalonePage theme={theme} onToggleTheme={() => setTheme((prev) => (prev === "dark" ? "light" : "dark"))} />}
      />
      <Route
        path="/smpsmodule"
        element={<SmpsModuleStandalonePage theme={theme} onToggleTheme={() => setTheme((prev) => (prev === "dark" ? "light" : "dark"))} />}
      />
    </Routes>
  );
}

export default App;