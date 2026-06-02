// ============================================================
//  EEE/EIE Y2 Smart Grid Project Report
//  Group: Watt's Up
//  Imperial College London, June 2026
// ============================================================

// ---------- Document metadata ----------
#set document(
  title: "EEE/EIE Y2 Smart Grid Project",
  author: "Watt's Up",
)

// ---------- Page setup ----------
#set page(
  paper: "a4",
  margin: (x: 2.5cm, y: 2.5cm),
)

// ---------- Text & paragraph ----------
#set text(
  font: "New Computer Modern",
  size: 11pt,
  lang: "en",
)
#set par(justify: true, leading: 0.65em)

// Hyperlinks (e.g. bibliography URLs) render in a muted blue, no underline.
// Only affects `link` elements; figure/section cross-references and citation
// numbers are `ref`/`cite` elements and stay black.
#show link: set text(rgb("#1a3e7a"))

// ---------- Tables: consistent, professional style ----------
// Dark-blue header row with white bold text, light zebra striping on the body,
// horizontal hairlines only (no vertical rules) and generous padding. The
// protable() wrapper keeps each table on a single page so it never splits
// across a page boundary.
#let _tbl-blue  = rgb("#23457d")
#let _tbl-zebra = rgb("#eef2f7")
#let _tbl-line  = rgb("#cbd3df")

#set table(
  inset: (x: 7pt, y: 6pt),
  stroke: (x, y) => (
    left: none, right: none,
    top: 0.5pt + _tbl-line,
    bottom: if y == 0 { 0.9pt + _tbl-blue } else { 0.5pt + _tbl-line },
  ),
  fill: (x, y) => if y == 0 { _tbl-blue } else if calc.odd(y) { _tbl-zebra } else { white },
)
#show table.cell: set text(size: 10pt, hyphenate: false)
#show table.cell: set par(justify: false)
#show table.cell.where(y: 0): set text(fill: white, weight: "bold")

// protable wraps a table in a figure(kind: table, ...) so it picks up the
// section-based "Table N.M" numbering scheme set further down. Captions follow
// the same 1-line rule as figures.
#let protable(caption: none, ..args) = figure(
  table(..args),
  caption: caption,
  kind: table,
)

// ---------- Heading numbering & styling ----------
#set heading(numbering: "1.1")

#show heading.where(level: 1): it => [
  #counter(figure.where(kind: image)).update(0)
  #counter(figure.where(kind: table)).update(0)
  #set text(size: 16pt, weight: "bold")
  #v(0.6em)
  #it
  #v(0.3em)
]

// ---------- Figure numbering by section (1.1, 1.2, 2.1, ...) ----------
#set figure(numbering: n => numbering("1.1", counter(heading).get().first(), n))
#show heading.where(level: 2): it => [
  #set text(size: 13pt, weight: "bold")
  #v(0.4em)
  #it
  #v(0.2em)
]
#show heading.where(level: 3): it => [
  #set text(size: 11pt, weight: "bold", style: "italic")
  #it
]

// ============================================================
//  Cover Page (with Abstract)
// ============================================================
#set page(numbering: none)

#align(center)[
  #v(1.2cm)
  #text(size: 24pt, weight: "bold")[EEE/EIE Y2 Smart Grid Project]

  #v(0.7cm)
  #text(size: 18pt, weight: "bold")[Group: Watt's Up]

  #v(1.2cm)
  #text(size: 12pt)[
    Chun Wen Ooi (02586872) \
    Dzuldiniy Hussain Bin Dzulkeflee (02574233) \
    Fangnan Tan (02571173) \
    Hong Zhe Tan (02562503) \
    Wei Zen Ooi (02614796) \
    Yi Da Wu (02567507) \
    Yong Zhi Tong (02581094)
  ]

  #v(0.8cm)
  #text(size: 13pt)[Imperial College London]
  #v(0.15cm)
  #text(size: 13pt)[June 2026]
]

#v(1cm)

// Abstract on cover
#align(center)[
  #text(size: 14pt, weight: "bold")[Abstract]
]
#v(0.3cm)

The Smart Grid was developed as a DC microgrid built from five cooperating SMPS modules. It needed to balance generation, storage, and load on a shared 10V bus while maximising earnings or minimising expenses through grid import, export and supercapacitor charge or discharge. These converters, with independent SMPS topologies, contributed regulated current flows managed by the central coordinator for optimal power dispatch. The electrical limits of a 12V primary supply and a 10V bus with ±0.1V droop band were observed, allowing each module to operate autonomously through bus voltage signals. Architecture included a microcontroller on every module, INA219 and SPI ADC telemetry, and a user interface for operator monitoring. A 3D printed chassis housed the SMPS boards in their optimal positions for airflow and mechanical protection. The microgrid was powered by a 12V bench supply, with each Pico W regulating a local 3.3V rail for logic and sensors.

#v(0.5cm)
#align(center)[
  #text(size: 10pt, style: "italic")[Word count: #text(weight: "bold")[XXXX]]
]

#pagebreak()

// ============================================================
//  Table of Contents (roman numerals)
// ============================================================
#set page(numbering: "i")
#counter(page).update(1)

#outline(
  title: [Contents],
  indent: auto,
  depth: 3,
)

#pagebreak()

// ============================================================
//  Main Body (arabic numerals, restart at 1)
// ============================================================
#set page(numbering: "1")
#counter(page).update(1)


// ----- 1. Project Objectives & Management (~500 words) ------
= Project Objectives & Management

== Project Objectives

The project shall deliver a five-module DC microgrid that cooperatively regulates a shared 10V bus across PV generation, supercapacitor storage, grid import, grid export and a programmable LED load. The control system shall autonomously dispatch power between modules to minimise net cost under a time-varying tariff. The complete prototype shall be evaluated on demo day, 18 June 2026, against a published price-and-load scenario.

== Project Management System & Temporal Organisation

Coordinating a seven-member hardware and software team across a five-weeks delivery window required tooling that off-the-shelf platforms could not provide as a single integrated system. Rather than stitching together Notion, Trello, Microsoft Teams and ChatGPT, each of which solves only a fragment of the problem and none of which share state, a bespoke AI-powered Project Management System (PMS) was self-coded for the project. Every layer of the frontend, backend, AI pipeline and database schema was purpose-built around the rhythm of the team and the constraints of the brief.

#figure(
  image("images/pms_dashboard.png", width: 100%),
  caption: [PMS dashboard: countdown, budget, stats and todo.],
) <fig:pms-dashboard>

The platform is structured around four modules. A live operational dashboard (@fig:pms-dashboard) provides the project's situational awareness layer. An automated meeting transcript module (@fig:pms-transcript) records, transcribes and structures every meeting into attendee lists, discussion summaries and extracted action items, eliminating the historical note-taker tax and providing an unambiguous decision record. An AI-driven article and documentation generator named Aria (@fig:pms-article) produces project-specific technical writing such as component-selection notes and lab write-ups, grounded in the team's own document base. A Retrieval-Augmented Generation (RAG) project chat (@fig:pms-rag) ties everything together by indexing meeting minutes, Aria articles, the GitHub firmware repository, datasheets, test results and curated project memory, so that any team member can self-serve evidenced answers without bottlenecking a senior peer.

#figure(
  image("images/pms_transcript.png", width: 98.5%),
  caption: [Meeting transcript module.],
) <fig:pms-transcript>

#figure(
  image("images/pms_article.png", width: 98.5%),
  caption: [Aria article generator.],
) <fig:pms-article>

#figure(
  image("images/pms_rag_chat.png", width: 98.5%),
  caption: [RAG project chat with cited sources.],
) <fig:pms-rag>

Because every module was written in-house, outputs of one feed directly into the next without manual export. A transcribed meeting immediately enriches the RAG corpus, an Aria article updates the dashboard document count, and a new task synchronises across the calendar and the email reminder service. Temporal organisation is enforced by the countdown and calendar views, which together render the 18 June 2026 demo day as a daily, visceral constraint rather than an abstract deadline. The cumulative effect across the project window has been faster decision turnaround, fewer duplicated discussions, and zero overspend events against the £60 budget.

Beyond the four core modules, several additional features were built specifically to eliminate single points of failure in the team's data and operational continuity (@fig:pms-extras). A shared calendar with a Gantt-style timeline consolidates every milestone, dependency and submission deadline so that schedule knowledge does not live in any one person's head. A project image gallery centralises lab photography that would otherwise be scattered across personal phones and never recovered. A test results module captures raw measurement data with built-in charting, removing the spreadsheet-on-one-laptop antipattern that historically destroys reproducibility. Finally, lightweight personalisation through the team buddy selector keeps the platform somewhere team members actively want to log into, sustaining the upstream coordination benefits on which every other module depends.

#figure(
  grid(
    columns: 2,
    rows: 2,
    gutter: 6pt,
    image("images/pms_calendar.png", width: 100%),
    image("images/pms_images.png", width: 100%),
    image("images/pms_test_results.png", width: 100%),
    image("images/pms_buddies.png", width: 100%),
  ),
  caption: [Calendar, image gallery, test results, and buddy selector.],
) <fig:pms-extras>

#pagebreak()


// ----- 2. System Architecture & Key Design Decisions (~1500) -
= System Architecture & Key Design Decisions

System architecture decisions fix the boundary conditions for every subsequent SMPS, control loop and measurement choice. This section walks through the role of each module, the topology that wires them together, and the rationale behind the bus voltage, supply voltage, coordination scheme and inter-module communication.

== Module Roles

The system comprises five SMPS modules cooperating on a shared 10V DC bus. Each module implements a specific role with a topology and control mode chosen to match it.

#protable(
  caption: [Per-module topology, external component, control mode and bus role.],
  columns: (1fr, 1.3fr, 1.2fr, 1.1fr, 1.6fr),
  align: left + horizon,
  [*Module*], [*External component*], [*Topology*], [*Control*], [*Role on the bus*],
  [Import SMPS], [12V grid PSU], [Buck], [CV, droop at 9.9V], [Sources current when bus < 9.9V],
  [Export SMPS], [Sink resistor], [Buck], [CV, droop at 10.1V], [Sinks current when bus > 10.1V],
  [PV SMPS], [PV panel], [Boost], [MPPT], [Harvests panel power into bus],
  [Supercap SMPS], [10.5 to 17.5V supercap], [Bidirectional buck/boost], [CC, commanded], [Stores or releases on command],
  [LED Load SMPS], [3V LED module], [Buck (internal)], [CC], [Drives the LED load],
)

The two grid-facing modules share a common topology (synchronous buck) and a common control law (droop), differing only in their droop setpoints. This is what creates the dead-band around the nominal bus voltage discussed in Section 2.5. The Supercapacitor SMPS differs from droop entirely and runs as a commanded current source, which allows the economic algorithm in Section 9 to use storage as temporal arbitrage rather than as a passive load-sharing element. The LED Load SMPS is internally managed and exposes only its bus-side power draw to the rest of the system.

All four bidirectional modules are physically the same board, the synchronous half-bridge of @fig:smps-stage, carrying a 100µH inductor and a 100mΩ shunt on the Port B side. The individual roles in the table above are entirely based on how each board's ports are connected and how its buck/boost switch is set, not by different hardware, so the per-module sections that follow refer back to this single power stage rather than redrawing it.

#figure(
  image("images/bidirectional_power_stage.png", width: 100%),
  caption: [Bidirectional SMPS power stage, common to all four modules @clemow_smps.],
) <fig:smps-stage>

== Overall Microgrid Topology

The complete system is shown in @fig:arch-block. External components sit at the top of the diagram, each connected through their respective SMPS module to the shared 10V DC bus. Every SMPS is driven by a dedicated Pico W microcontroller running its local control loop. A FastAPI backend polls an Azure-hosted web service every 5 seconds for the current demand, price and irradiance signals, computes the dispatch decision documented in Section 9, and pushes setpoint commands directly to each module over its HTTP endpoint. The operator-facing dashboard renders telemetry from the same backend.

#figure(
  image("images/arch_block.png", width: 100%),
  caption: [Smart Grid system architecture and power flow.],
) <fig:arch-block>

Three properties of this topology are referenced repeatedly in later sections. First, every SMPS module is fully autonomous in its bus-regulation role: it requires only its local V_bus measurement to act, and the backend provides only setpoint commands and economic context. Second, all demo-day power measurements occur at the bus, never at the individual SMPS terminals. Third, the supercapacitor is the only element capable of storing energy across timescales longer than the bus capacitance, which makes its commanded behaviour central to the economic optimisation in Section 9.

== Bus Voltage Choice: 10 V Nominal, ±0.1 V Droop Band

The 10V nominal bus value is the smallest round-number voltage that simultaneously sits below the supercapacitor charge window, sits above the PV panel open-circuit voltage of approximately 8.5V, and leaves enough headroom for a buck-derived import from a 12V supply (justified in Section 2.4). Setting the bus higher would increase switching stress on every buck module without improving any system property. Setting it lower would force the supercapacitor window to a less convenient range and increase the PV boost ratio. 

Possible bus voltage is then cross-checked against the per-module efficiency sweeps in Sections 3.3.3, 4.3 and 5.3. The table below summarises efficiencies at three candidate bus voltages, with PV averaged across its four characterised irradiances and Import and Supercap measured at the 0.2 A operating point common to both sweeps.

#protable(
  caption: [Measured SMPS efficiencies at three candidate bus voltages.],
  columns: (1fr, 1fr, 1fr, 1fr),
  align: center + horizon,
  [*$V_("bus")$*], [*$eta_("PV")$*], [*$eta_("import")$*], [*$eta_("supercap,RT")$*],
  [8 V],  [97.0%], [88.1%], [87.3%],
  [9 V],  [96.9%], [88.9%], [87.4%],
  [10 V], [97.1%], [89.9%], [88.3%],
)

The differences across 8 V, 9 V and 10 V are small, within roughly a percentage point on every module and on the order of the run-to-run measurement scatter, so the efficiency data alone does not strongly discriminate between the three candidates. 10 V is nonetheless marginally the best on every column. The supercapacitor's hard 10.5 V lower limit (Section 4.1.2) removes the possibility on raising the bus further: a bus above 10.5 V would prevent the cap from boosting into the bus when discharged. 

Each droop-controlled module follows a local linear control law of the form

$ I_("module") = (V_("set") - V_("bus")) / R_("droop") $

with sign and saturation chosen by the module's role. The droop resistance $R_("droop")$ is sized so that the module current saturates at its rated maximum exactly at the edge of the ±0.1V band. This bounds the steady-state bus error to ±0.1V at full load, which is ±1% of nominal and tight enough to be a stiff bus for all downstream loads.

An important consequence of taking demo-day measurements on the bus itself is that conversion losses on different paths are calculated differently. For the LED Load SMPS and the Export SMPS, the losses lie between the bus and the destination, so the bus delivers $P_("destination") + P_("losses")$ and the metric counts the sum as either load or export. SMPS efficiency on those two paths therefore does not affect the score, and the modules can be sized for cost or simplicity rather than peak efficiency. For the Import SMPS the losses lie between the 12V supply and the bus measurement point, so the bus receives only $P_("grid") - P_("losses")$. Every watt lost in the import path is grid energy that does not appear at the bus, directly degrading the economic score. 

== PSU Voltage Rationale: 12 V

The choice of 12V for the primary supply is driven by efficiency. For a synchronous buck converter, the steady-state conduction loss summed across both switches is @erickson_fundamentals_2020

$ P_("cond") = D dot I_("rms")^2 dot R_("ds,on,HS") + (1 - D) dot I_("rms")^2 dot R_("ds,on,LS") $

When the high-side and low-side MOSFETs are matched, $R_("ds,on,HS") = R_("ds,on,LS") = R_("ds,on")$, and the duty cycle terms collapse:

$ P_("cond") = I_("rms")^2 dot R_("ds,on") $

independent of D and therefore independent of $V_("in")$. Switching loss, in contrast, does not collapse:

$ P_("sw") approx 1/2 dot V_("in") dot I_("load") dot (t_r + t_f) dot f_("sw") + 1/2 dot C_("oss") dot V_("in")^2 dot f_("sw") $

Every term scales with $V_("in")$ or $V_("in")^2$. Inductor ripple also shrinks as $V_("in")$ approaches $V_("bus")$:

$ Delta I_L = (V_("in") - V_("bus")) dot D dot T / L $

which reduces inductor RMS current and copper loss as a second-order benefit. The net result is that import SMPS efficiency rises as $V_("in")$ is reduced toward $V_("bus")$, but only weakly: with matched synchronous FETs the dominant conduction term is independent of $V_("in")$, leaving switching term as the only input-voltage-dependent loss.

However the limiting constraint is not efficiency but dropout. A buck produces $V_("bus")$ at a duty $D = V_("bus") / V_("in")$, which tends to unity as $V_("in")$ approaches $V_("bus")$, yet a real converter cannot reach $D = 1$: a minimum switch off-time, gate-driver refresh requirements, and the controller's maximum-duty clamp all hold the duty below unity. With a maximum duty of roughly 0.9, regulation is lost once $V_("in")$ falls below about $V_("bus") / 0.9 approx 11$V, where the output begins to sag below target. Fixing $V_("in") = 12$V leaves comfortable margin above this floor and any marginal efficiency gain from lowering $V_("in")$ further does not justify reducing the risk of tripping. 

@fig:buck-vin-eff plots this loss model at a fixed 10V bus and 1.5A load. Across the usable 11V to 15V range the modelled efficiency is nearly flat: total loss shifts by only a few tens of milliwatts, around 0.2% of the delivered power, because conduction loss is constant and only the small switching term tracks $V_("in")$. The sharp collapse at the left of the plot is not a loss effect but the dropout region described above, where the converter can no longer regulate, so it marks the unusable input range rather than an inefficient one. The chosen 12V point sits on the flat plateau with comfortable margin above that floor.

#figure(
  image("images/buck_vin_efficiency.png", width: 100%),
  caption: [Modelled buck efficiency and loss split versus input voltage.],
) <fig:buck-vin-eff>

A confirmation experiment is flagged in Section 12 (Future Work): sweep $V_("in")$ from 11V to 14V at fixed $V_("bus") = 10$V and measure import SMPS efficiency. The expectation, given the analysis above, is a shallow monotonic rise as $V_("in")$ falls toward 11V, ending in a steep efficiency cliff once dropout kicks in.

== Coordination Scheme: Symmetric Droop vs Mutex Arbitration

Two architectures were considered for coordinating the bus. Mutex arbitration assigns control to exactly one module at a time, with a central coordinator switching modes (PV-controlled, grid-controlled, supercap-controlled) as conditions change. Symmetric droop, the established primary-control approach for DC microgrids @dragicevic_dcmg_2016, instead allows every module to act simultaneously, each modulating its own current from a local V_bus measurement relative to its setpoint.

Mutex arbitration produces tighter bus regulation in steady state because exactly one feedback loop is active at a time. However, it places the inter-module communication channel inside the safety-critical bus-regulation loop: if comms drop or the coordinator stalls, every module loses its reference and the bus collapses. Mode transitions also generate voltage transients as the active controller hands over.

Symmetric droop avoids both failure modes. Each module's control loop is local and continuous, requiring only its own bus measurement, so a comms failure degrades the economic optimisation in Section 9 but does not threaten bus stability. The droop curves blend rather than switch, eliminating handover transients, and modules can join or leave the bus arbitrarily without reconfiguring a coordinator. The cost is a small steady-state V_bus error, bounded to ±0.1V by design as derived in Section 2.3.

Symmetry is enforced by mirroring the import and export setpoints about the 10V nominal:

$ V_("set,import") = 9.9 "V" quad quad V_("set,export") = 10.1 "V" $

This creates a dead-band $V_("bus") in [9.9, 10.1]$ V in which neither grid-facing module acts. Inside the dead-band the bus is held by the PV harvester and the supercapacitor, which is precisely the configuration the algorithm in Section 9 seeks to maximise (no grid interaction means no cost incurred). Outside the dead-band the system gracefully falls back to grid import or export with no explicit mode-change logic. The theoretical droop curves for all five modules are shown in @fig:droop-curves.

#figure(
  image("images/droop_curves.png", width: 85%),
  caption: [Droop curves: module current versus bus voltage.],
) <fig:droop-curves>

@fig:busbar-deadband shows the measured droop coordination over a load cycle. The bus floats inside the dead-band while supply and demand match, is pulled below 9.9V (where the grid module begins to source) when load exceeds local generation, and is pushed above 10.1V (where the export module begins to dissipate) when generation exceeds load.

#figure(
  image("images/busbar_deadband.png", width: 100%),
  caption: [Bus voltage and converter currents across import, dead-band and export.],
) <fig:busbar-deadband>

Choosing droop over mutex maps directly onto the single-point-of-failure mitigation theme introduced in Section 1.2. 

== Communication Protocol

The communication protocol is provisional and described here at the architectural level only. Each Pico W module joins a shared WiFi network (a phone hotspot during bench bring-up, the lab network on demo day) and runs a small HTTP server exposing per-module telemetry and command endpoints in JSON. The FastAPI backend, running on a host on the same network, polls each module's telemetry endpoint at roughly 1 Hz and the Azure-hosted web service every 5 seconds for current demand, price and irradiance signals, computes the dispatch decision (Section 9), and pushes setpoint updates back to each module's command endpoint over the same HTTP link. The 5-second Azure cadence balances rate-limit considerations against the natural timescale of the demand-and-price signal. The dashboard frontend renders telemetry from the backend and additionally carries a direct command path to each module (Section 8.3), so operator control survives a backend or database outage.

Crucially, the protocol layer sits outside the safety-critical bus-regulation loop. Comms loss leaves every module operating against its last commanded setpoint with its local droop or CC law intact, so the bus continues to regulate. Final framing details (transport, framing, retry policy, error handling) are deferred until module integration testing in Section 11.

#pagebreak()


// ----- 3. PV SMPS (~1000 words) ------------------------------
= PV SMPS

== Design & Simulation

=== Topology Selection

The PV panel is an 8W nominal device with a nominal open-circuit voltage of approximately 8.5V and a short-circuit current of approximately 1.0A, measured at about 7.5V open-circuit under the solar emulator. Its maximum power point shifts only slightly with irradiance, sitting at 5.20V from 65% to 100% irradiance and stepping down by 0.10V to 5.10V at the 25–50% settings, as the measured I-V and P-V sweeps in @fig:pv-iv show. Each curve was taken by stepping the panel voltage from approximately 2V toward the open-circuit knee (with denser sampling around the MPP) and recording the current and resulting power at one of six emulator dimmer settings (25% to 100%). Because the maximum-power voltage (around 5V) is below the 10V bus, energy can only be delivered to the bus by stepping the panel voltage up, so the module runs as a boost converter.

#figure(
  image("images/pv_iv_measured.png", width: 100%),
  caption: [Measured PV panel I-V and P-V curves with the MPP locus.],
) <fig:pv-iv>

The boost direction is consistent with the module's hard constraint that Port A must sit above Port B for any energy transfer (the shared power stage is shown in @fig:smps-stage). The panel is wired to Port B (the lower, variable voltage) and the bus to Port A (the fixed 10V), so current flows from Port B to Port A and the panel always satisfies $V_("A") > V_("B")$. The BU/BO switch is set to BOOST, which also routes the on-board support rail (Pico, current sensor, gate drivers) from Port B; during bench work the Pico is additionally USB-powered, so panel collapse does not reset the controller. Unlike the grid and export buck modules, the boost PWM is not inverted: the firmware writes the duty directly rather than the `65536 - pwm_out` form the buck modules require.

Current is sensed by the INA219 across the 0.10 ohm shunt at Port B. The shunt is physically wired in the Port A to Port B sense direction, so the firmware negates the reading: a positive inductor current then corresponds to panel-to-bus boost flow. The control structure is a cascaded pair, an outer voltage PI that servoes the panel voltage to the commanded $V_("mpp")$ and an inner current PI that drives the duty, with the operating point set by whichever MPPT strategy is active.

=== MPPT Strategy: Lookup Table vs P&O

Three approaches for maximum power point tracking were considered: a static constant-voltage operating point, an irradiance-indexed lookup table, and online Perturb and Observe (P&O) gradient ascent. All three were prototyped. The constant-voltage approach is more competitive than initially assumed: the characterisation in @fig:pv-vmpp shows $V_("mpp")$ varying by only 0.10V across the full irradiance range, so a fixed 5.15V setpoint would lose under 1% of available harvest at every characterised point. It is nevertheless not relied on alone because the bench sweep is taken under thermal equilibrium and does not capture the temperature drift the panel sees under sustained illumination, where $V_("mpp")$ slides with the cell-temperature coefficient. Lookup-table and P&O are therefore shipped alongside fixed mode, and all three are user-selectable from the host dashboard so that Section 3.3 can present a quantitative comparison rather than commit to a single shipped strategy.

The lookup table method exploits the externally available irradiance signal. The PV module fetches the current sun value from the Azure-hosted `/sun` endpoint every five seconds, normalises to a fraction in $[0, 1]$, and interpolates against a piecewise-linear $V_("mpp")$ versus irradiance table built from the characterisation sweeps of @fig:pv-iv. The extracted maximum-power points are plotted against irradiance in @fig:pv-vmpp, and these values, stepping from 5.10V at low irradiance (25–50%) up to 5.20V at higher irradiance (65–100%), are exactly the entries loaded into the firmware table. The 0.10V step direction matches the textbook silicon-cell ascent of $V_("mpp")$ with irradiance, though the magnitude is small enough that linear interpolation between the two plateaus produces a near-flat lookup. Settling is immediate because the new $V_("mpp")$ is commanded as a step input to the existing outer voltage PI. The costs are the prior characterisation effort and the dependency on the web link remaining alive; if the link drops, the firmware degrades gracefully by holding the last good irradiance value rather than commanding an arbitrary fallback.

#figure(
  image("images/pv_vmpp_irradiance.png", width: 78%),
  caption: [Measured Vmpp and Pmax versus irradiance: the MPPT lookup table.],
) <fig:pv-vmpp>

P&O makes no assumption about $V_("mpp")$. The algorithm perturbs the commanded $V_("mpp")$ by a small fixed step, measures the resulting power averaged over a settling window, compares to the previous window, and either keeps or reverses the perturbation direction. With no external irradiance signal required, P&O is inherently more robust against web link outages or unmodelled panel behaviour, at the cost of continuous oscillation around the peak and slower convergence after rapid irradiance steps. The literature on P&O @femia_po_2005 cautions that naive implementations using a single instantaneous power sample per perturbation collapse into noise-driven random walks when the per-sample noise exceeds the curvature of the $P(V_("mpp"))$ surface near the peak; the bench-noise floor (Section 3.2) made this an active concern that shaped the implementation.

Implementing all three, rather than committing to one, is driven by the marking rubric's emphasis on quantitative evaluation. Shipping multiple modes also leaves the system robust to single-method failure: a web link outage degrades from web-lookup to fixed-mode with no firmware change, and P&O remains available as a fully autonomous fallback that does not depend on the external irradiance signal.

== Testing & Implementation

Three implementation concerns dominated bringing the PV SMPS up on the bench: noise on the measured panel power that masked operating-point differences, robust P&O behaviour against that noise, and a clean framework for comparing the two MPPT modes during evaluation. Each is described in turn.

=== Bench Noise Treatment

Raw $P_("panel") = V_("panel") dot I_("L")$ telemetry showed several-hundred-milliwatt peak-to-peak jitter at the 1 kHz control tick, dominating the mode-to-mode harvest differences the comparison in Section 3.3 needed to resolve. The three-layer attenuation derived in Section 7 (INA219 hardware averaging, four-fold Pico ADC oversample, and a software EMA at $alpha = 0.05$) was applied. The filtered values feed only the dashboard display and the P&O comparison; the inner current PI and the safety guards continue to consume the raw single-sample readings so the original loop tuning is unchanged and trip response remains instantaneous.

=== P&O Implementation

P&O was implemented with a two-timescale structure. The outer voltage PI continues to track the commanded $V_("mpp")$ at 100 Hz; perturbations to that command occur on a 300 ms cadence ($T_("dwell")$). The cadence is roughly five times the outer-loop settling time so that the power measured at the end of a dwell reflects the new steady-state operating point rather than the PI transient. Power for the comparison is the filtered $V_("panel,lp") dot I_("L,lp")$ accumulated only over the second half of each dwell window and then averaged. The two-stage filtering (EMA followed by dwell average) brings the per-comparison noise floor below 10 mW, well under the curvature of the $P(V_("mpp"))$ surface near the peak.

A direction-flip rule with a dead-band prevents the three-point oscillation around the peak from degenerating into a noise-driven random walk. If the dwell-averaged power decreased by more than $epsilon = 20$ mW since the previous dwell, the perturbation direction is reversed; otherwise the previous direction is held. The commanded $V_("mpp")$ is hard-clamped to the 5.0 V to 7.0 V window so that an algorithm fault cannot walk the operating point off into open-circuit or short-circuit territory. On entry to P&O mode the state is reseeded from the last commanded fixed-mode $V_("mpp")$, avoiding a stale or possibly faulty prior value.

=== Mode Comparison Support

To make MPPT mode comparison tractable on bench equipment, a true three-second block average of $P_("panel")$ was added to the firmware telemetry, restarting whenever the MPPT mode is changed from the dashboard. The operator procedure becomes "fix the panel under stable light, select mode A, wait three seconds, read the number, select mode B, wait three seconds, read the number". This separates the question of which algorithm finds a higher operating point (resolved by the averaged numbers) from the question of how noisily the operating point is tracked (resolved by inspecting the live trace). The same block-average pattern is reused in Section 4 and Section 5 for the supercap and grid efficiency tests.

== Evaluation & Optimisation

Two evaluation axes are reported for the PV SMPS: MPPT mode comparison, and SMPS conversion efficiency.

=== MPPT Mode Comparison

Each MPPT mode is tested across the lookup table's irradiance range using the lab dimmer to set fractional sun at 25%, 50%, 75% and 100%. At each setting the three-second block-averaged $P_("panel")$ is recorded in fixed mode (commanded at the table's $V_("mpp")$), web mode (tracking the live sun signal), and P&O mode (started from the same $V_("mpp")$ seed). The primary metric is steady-state delivered power; the secondary metric is convergence time, defined as the time from a mode switch until $P_("panel")$ enters and stays within a ±5% band of the final value.

The expected outcome is that web-lookup and P&O converge to the same delivered power within bench noise at the four characterised irradiances, because P&O hunts to the same peak the table is built from. The interesting comparison is therefore off the table's characterised points: at irradiance values between the table entries (where the interpolation is approximate) and at panel temperatures away from characterisation conditions (where the table is open-loop and P&O is closed-loop). P&O is expected to win on convergence speed only if the perturbation cadence is reduced from its conservative 300 ms; future work covers the cadence sweep.

=== SMPS Efficiency Characterisation

PV conversion efficiency is defined as $eta_("PV") = P_("bus,out") / P_("panel,in")$. The pre-loss quantity $P_("panel,in") = V_("panel") dot I_("L")$ is directly available from the firmware because both factors are Port B side measurements on the boost topology, where the inductor current equals the input current. The post-loss quantity $P_("bus,out") = V_("bus") dot I_("bus,out")$ is not directly available: the shunt sits between the inductor and Port B per the lab schematic, so Port A (the bus side) is uninstrumented on every bidirectional module.

Three approaches were considered for measuring $P_("bus,out")$. The first was an automated test using the supercapacitor module as a calibrated load: with the cycle-test round-trip efficiency $eta_("cap")$ known (Section 4.3), the cap-side stored energy rate $C dot V_("cap") dot (d V_("cap")) / (d t)$ divided by $eta_("cap,charge")$ gives the bus-side power into the cap, which equals $P_("bus,out")$ when no other module is sourcing or sinking. The second was using the LED Load SMPS bus draw, after a one-time bench characterisation of the LED module's own efficiency $eta_("LED")$. Both automated approaches cascade two independently measured efficiencies, compounding their ±1 to 2% characterisation errors and introducing a dependency on the calibration operating point matching the test operating point. The third was a manual bench measurement using a digital multimeter (DMM) placed in series with the PV-to-bus wire, giving $I_("bus,out")$ directly.

For the demo-day characterisation the third approach was chosen. The decision is justified by the marking rubric's evaluation criterion that rewards quantitative evidence and informative visual presentation: a smaller number of high-confidence ground-truth measurements yields a more defensible $eta_("PV")$ curve than a larger number of cascaded automated measurements. The realised sweep covers two axes. The bus-voltage axis is swept across twelve points from 7.1 to 12.55 V, deliberately wider than the import/export dead-band of Section 2.5 so the duty-cycle dependency is captured across the full physically reachable range. The irradiance axis covers the four lab-dimmer settings 25%, 50%, 75% and 100%. At each of the 48 grid points the operator reads $P_("panel")$ off the dashboard, reads $I_("bus,out")$ off the DMM, computes $P_("bus,out") = V_("bus") dot I_("bus,out")$ and reports $eta_("PV") = P_("bus,out") / P_("panel")$. Both axes are now complete and reported in Section 3.3.3 below.

A subsequent automation step would replace the manual DMM measurement with the cap-as-calibrated-load approach: the first DMM sweep then serves as a single calibration step, after which characterisation runs can be triggered from the dashboard without bench instrumentation.

=== Measured SMPS Efficiency

@fig:pv-eta-measured and the table below present the full 48-point sweep: four irradiance settings (25%, 50%, 75%, 100%) at twelve bus-voltage points each, with the panel pinned at its MPP under the prior characterisation ($V_("panel") approx 6.23$ V). The boost duty cycle $D = 1 - V_("panel") / V_("bus")$ walks from 0.13 to 0.50 across the bus-voltage sweep. A re-sweep against the updated $V_("mpp")$ table of @fig:pv-vmpp is queued for the next firmware revision: the new operating point sits roughly 1V lower (approximately 5.15V), which shifts the same bus sweep into the wider duty range 0.28–0.59. That range stays within the flat boost plateau, but at the supercap ceiling $V_("bus") = 17.5$V the reachable $D_("max") = 1 - 5.15 / 17.5 approx 0.71$ now sits at the CCM cliff threshold that the 6.23V case (0.64) safely cleared, so cliff-edge behaviour at the cap-full operating point becomes a verification target for the re-sweep.

#protable(
  caption: [Measured PV SMPS efficiency across bus voltage and irradiance.],
  columns: (1fr, 1fr, 1.1fr, 1.1fr, 1.1fr, 1.1fr),
  align: center + horizon,
  [*$V_("bus")$ (V)*], [*Duty $D$*], [*$eta_("PV")$ at 25%*], [*$eta_("PV")$ at 50%*], [*$eta_("PV")$ at 75%*], [*$eta_("PV")$ at 100%*],
  [7.11], [0.12], [96.56%], [96.69%], [97.17%], [97.68%],
  [7.61], [0.18], [96.36%], [96.79%], [96.82%], [97.89%],
  [8.11], [0.23], [96.62%], [96.57%], [96.98%], [97.74%],
  [8.61], [0.28], [96.52%], [96.44%], [96.73%], [98.00%],
  [9.12], [0.32], [96.16%], [96.63%], [96.79%], [97.86%],
  [9.61], [0.35], [96.69%], [96.34%], [97.11%], [98.10%],
  [10.21], [0.39], [96.56%], [96.80%], [97.15%], [98.02%],
  [10.63], [0.41], [96.57%], [96.68%], [97.28%], [97.79%],
  [11.07], [0.44], [96.18%], [96.75%], [96.90%], [98.10%],
  [11.63], [0.46], [96.37%], [96.51%], [96.92%], [98.08%],
  [12.06], [0.48], [96.32%], [96.88%], [96.98%], [97.83%],
  [12.55], [0.50], [96.66%], [96.84%], [96.81%], [97.77%],
)

#figure(
  image("images/pv_efficiency_measured.png", width: 100%),
  caption: [Measured PV SMPS efficiency versus bus voltage at four irradiances.],
) <fig:pv-eta-measured>

Two features stand out. First, each $eta_("PV")$ trace is flat with bus voltage. The four curves vary by no more than ±0.3% across their twelve points, with no monotonic trend against $V_("bus")$, consistent with the flat plateau of the boost converter's $eta$-versus-$D$ characteristic across the $D = 0.12$ to $0.50$ range covered here. Fig. 5 of @navamani_iccpct2015, reproduced in @fig:pv-eta-ref, shows this plateau across moderate duty cycles and a sharp CCM cliff beyond $D approx 0.7$. The hardware cannot reach that cliff regime: with the panel pinned at 6.23 V the bus would need to exceed 20.8 V to hit $D = 0.7$, well above both the 17.5 V supercapacitor ceiling and the board's rated operating range. The maximum reachable $D_("max") = 1 - 6.23 / 17.5 = 0.64$ is still well clear of the cliff, so the measured plateau represents the converter's behaviour across its entire physically reachable operating space.

Second, the per-irradiance means rise monotonically with irradiance: 96.5% at 25%, 96.7% at 50%, 97.0% at 75% and 97.9% at 100%. The total spread is approximately 1.4 percentage points from lowest to highest dimmer setting and is consistent with the boost-converter loss model. Fixed gate-drive and switching overhead are independent of throughput, so they consume a larger fraction at low panel power: at 100% irradiance the panel delivers approximately 2.3 W, at 25% approximately 0.8 W, and the same fixed overhead therefore dominates a larger share of the lower throughput. The irradiance-to-irradiance gap sits well above the per-point scatter, so the monotonic ordering is statistically clean and not a noise artefact.

#figure(
  image("images/pv_efficiency.png", width: 78%),
  caption: [Boost efficiency versus duty cycle in DCM and CCM, from Fig. 5 of @navamani_iccpct2015.],
) <fig:pv-eta-ref>

The combined finding is that PV conversion efficiency sits in a narrow 96 to 98% band across all four irradiance levels, with a clean 1.4 percentage-point rise from 25% to 100% irradiance and no meaningful dependence on bus voltage. PV's contribution to the system optimum is therefore largely insensitive to bus-voltage choice, so the system-level optimal $V_("bus")$ for maximum overall efficiency is driven by the more bus-voltage-sensitive Import SMPS characterised in Section 5.3.

#pagebreak()


// ----- 4. Supercapacitor SMPS (~1000 words) ------------------
= Supercapacitor SMPS

== Design & Simulation

=== Boost Topology and Boot-with-Empty-Cap Rationale

The supercapacitor bank is the only variable-voltage element on the storage side, swinging between 10.5V when depleted and 17.5V when full. The same Port A above Port B transfer rule that fixed the PV topology dictates the port assignment here (the shared power stage is @fig:smps-stage): the cap is the higher and variable rail and must sit on Port A, with the fixed 10V bus on Port B. Energy then flows from bus to cap (Port B to Port A) when charging and from cap to bus (Port A to Port B) when discharging, so the module is genuinely bidirectional rather than a one-way source or sink.

The BU/BO switch is set to BOOST, which is the load-bearing decision for robustness. With BOOST selected, the on-board support circuitry draws from Port B, the bus, which is always energised by the grid and PV modules. The board therefore boots and stays alive even when the cap is fully empty at 0V. The alternative BUCK setting would power the support rail from Port A, the cap, and would brick the controller whenever the cap fell below the 6V to 7V minimum support voltage, which is precisely the depleted state from which the system most needs to recover.The current sign convention follows the PV module: a positive inductor current means charging (bus to cap), a negative current means discharging (cap to bus), and the dashboard command $i_("cmd")$ is signed accordingly.

=== Operating Window 10.5 to 17.5 V

The usable voltage window falls out of three hard limits, illustrated against the stored-energy curve in @fig:supercap-energy. The ceiling $V_("cap,max") = 17.5$V is the SMPS port limit and sits comfortably under the 18V cap rating. The floor $V_("cap,min") = 10.5$V is the point below which the cap can no longer satisfy $V_("A") > V_("B")$ against the 10V bus, so the SMPS can transfer energy in neither direction. Within that window the bank stores energy as $E = 1/2 C V^2$ with $C = 0.5$F (two 0.25F caps in parallel).

#figure(
  image("images/supercap_energy_window.png", width: 88%),
  caption: [Supercapacitor stored energy and usable operating window.],
) <fig:supercap-energy>

In firmware the practical charge ceiling is lowered to 15.7V. The choice of 15.7V was chosen after a series of test with different voltages, and we found 15.7 to provide the best compromise of safe upper headroom for demo as well as sufficient usable energy. The usable energy cycled between 10.5V and 15.7V is approximately 34J of the roughly 49J the full window would hold. A significant practical challenge is the bank's approximately 4 ohm equivalent series resistance, this value of ESR is significant and has been accounted in our cycle testing in modelling the cap's efficiency. Lastly the peak current is clamped to 0.60A, leaving approximately 21% headroom under the 0.76A SMPS hardware limit @cd_dsm_datasheet.

=== Command-Driven CC: Rationale for the Departure

Unlike the grid and export modules, the supercap does not participate in droop. The bus voltage is already regulated by the grid and export droop pair (Section 2.5), so adding the cap as a third droop participant would complicate coordination for no benefit. Instead the cap is a commanded current source and sink: it tracks a signed current command decided by the economic algorithm. This performs temporal arbitrage, charging when energy is cheap and discharging when it is expensive, rather than reacting naively to instantaneous bus voltage.

The control law is therefore an inner current PI only, with no outer voltage loop. The role normally played by an outer loop is filled by a set of soft clamps on the current command: a hard limit at plus or minus 0.60A, a linear taper to zero near each voltage limit, and a bus-health taper that reduces charging demand when the bus sags so the cap does not fight the grid for current. 

== Testing & Implementation

Two implementation matters specific to the supercap module are reported here: the same layered noise treatment described for the PV module in Section 3.2 and the inner-loop feedforward that keeps the synchronous boost stable.


=== Inner-Loop Feedforward and Bus-Droop Backoff

The inner current PI carries a boost feedforward term equal to the equilibrium duty cycle, $D_("ff") = 1 - V_("bus") / V_("cap")$. At this duty the inductor sees zero net volt-seconds per switching cycle, so its current holds constant and the integrator only has to correct the residual. Without the feedforward the integrator must synthesise the entire steady-state duty, and when the command steps to zero the PI can transiently drive the duty all the way to its floor. In this synchronous boost topology a zero duty clamps the high-side MOSFET on, dumping cap energy back into the bus and crashing the bus rail.

A subtle but critical detail is that the feedforward uses the nominal 10V bus value, not the measured $V_("bus")$. Feeding the measured bus voltage into the feedforward creates a positive-feedback loop with a loop gain near 1.7: a bus sag raises the feedforward duty, which draws more current from the bus, which sags it further. Substituting the constant nominal value breaks the loop, and the integrator absorbs any genuine offset between nominal and actual bus voltage as a small steady-state correction. A complementary bus-health taper scales the charge command down as the bus falls from 9.5V toward 8.5V, so the cap stops competing with the grid module for current during a shared sag; discharging is left untapered because pushing current into a sagging bus helps rather than harms. A hard charge cutoff at 15.7V provides a final backstop above the soft taper.

== Evaluation & Optimisation

The supercap evaluation answers two questions: what is the round-trip energy efficiency $eta_("RT")$, and how does it split into $eta_("charge")$ and $eta_("discharge")$? Both are answered from a single charge-and-discharge cycle, exploiting the cap's known capacitance as an internal calibration reference. The same dataset supports the efficiency-versus-current curve required for Section 11.

=== Energy Balance Method

For a complete cycle from $V_("low")$ up to $V_("high")$ and back to $V_("low")$, three energies are measured. Bus-side input energy is integrated over the charge phase as $E_("in") = integral V_("bus") dot I_("bus") d t$. Bus-side output energy is integrated over the discharge phase as $E_("out") = integral V_("bus") dot |I_("bus")| d t$. Cap-side stored energy at three reference points is computed from the open-circuit cap voltage as $E_("cap") = 1/2 C V_("cap")^2$, captured before charging ($E_("cap,start")$), between the charge and discharge phases ($E_("cap,peak")$) and after discharging ($E_("cap,end")$). The three efficiencies follow:

$ eta_("charge") = (E_("cap,peak") - E_("cap,start")) / E_("in") $
$ eta_("discharge") = E_("out") / (E_("cap,peak") - E_("cap,end")) $
$ eta_("RT") = E_("out") / E_("in") = eta_("charge") dot eta_("discharge") $

The key property of this construction is that no current sensor is required on the cap side: $E_("cap")$ is computed entirely from a voltage measurement and the bank capacitance $C = 0.5$ F (two 0.25 F caps in parallel). This avoids the cascading-efficiency problem flagged in Section 3.3 for the PV characterisation and makes the test fully self-contained inside the supercap firmware.

=== Cycle Test State Machine

The test is implemented as a state machine inside the supercap firmware, triggered from a single dashboard button (@fig:cap-state-machine). Phases run in sequence: precharge (drive $V_("cap")$ down to $V_("low")$ if currently above), settle 1 (zero current for 500 ms, capture $E_("cap,start")$), charge (constant current at the user-specified $I_("charge")$ up to $V_("high")$), settle 2 (capture $E_("cap,peak")$), discharge (constant current at the user-specified $I_("discharge")$ back to $V_("low")$), settle 3 (capture $E_("cap,end")$), done (compute and expose the three efficiencies). Each settle phase averages $V_("cap")$ over only its last 200 ms, skipping the early-settle ESR voltage relaxation transient. Integration of $E_("in")$ and $E_("out")$ runs at the full 1 kHz control tick rate so the displayed efficiencies are not limited by any external sample rate.

#figure(
  image("images/supercap_cycle_state_machine.png", width: 100%),
  caption: [Supercapacitor cycle-test state machine.],
) <fig:cap-state-machine>

Three design decisions in the state machine deserve note. First, the endpoint $V_("low") = 10.5$ V was chosen over a tapered-out $V_("low") = 11.0$ V even though the cap's soft-discharge taper between 11.0 V and 10.5 V (introduced for hard-floor safety) means the discharge current is not held constant at the user-specified value across the final 0.5 V. The energy integral correctly captures the tapered region, and $eta_("discharge")$ legitimately reflects performance averaged across the operational window; the alternative would understate the discharge contribution to round-trip loss. Second, the test bypasses the user-i_cmd path and writes 0 into the command dictionary at start, so when the test ends the cap idles cleanly rather than resuming whatever current command was active before. Third, auto-rearm is implemented: after the done phase the firmware returns to normal command mode, allowing the next test to be triggered with a single button click without intermediate reset.


=== Measured Results

The cycle test was run as two sweeps, each repeated three times: a charge and discharge current sweep at 0.1, 0.2, 0.3, 0.4, 0.5 and 0.6 A with the bus held at 10V, and a bus voltage sweep at 8.0, 8.5, 9.0, 9.5 and 10.0V with the current fixed at 0.2A. @fig:cap-cycle shows a representative cycle at the 10V, 0.2A operating point. The capacitor voltage ramps from 10.5V to the 15.7V cutoff over a 19-second charge and back over a 17-second discharge, while the bus-side energy integrals accumulate to $E_("in") = 38.2$ J on charge and $E_("out") = 33.7$ J on discharge. The cap-side energy swing $1/2 C (V_("high")^2 - V_("low")^2) approx 34$ J matches the design estimate.

#figure(
  image("images/supercap_cycle_trace.png", width: 100%),
  caption: [Measured supercapacitor charge and discharge cycle at 10V, 0.2A.],
) <fig:cap-cycle>

Round-trip efficiency is reported as $eta_("RT") = E_("out") / E_("in")$, with both energies measured at the bus, so the figure is independent of any cap-side assumption. @fig:cap-eff plots it against current and against bus voltage, showing all three runs per point. The headline result is a round-trip efficiency of approximately 88%, slightly above the conservative 70 to 85% pre-test estimate and stable across the operating range. The current dependence is weak and slightly negative across the full 0.1 to 0.6 A range (89.7% at 0.1 A falling to 86.9% at 0.5 A, with an 87.4% recovery at 0.6 A inside the run-to-run scatter), consistent with conduction loss growing with current. The bus-voltage dependence is weaker still and largely within run-to-run scatter, with a mild rise toward higher bus voltage (87.3% at 8 V to 88.3% at 10 V), consistent with the smaller boost ratio, and therefore lower switch stress, when the cap sits closer to the bus.

#figure(
  image("images/supercap_efficiency.png", width: 100%),
  caption: [Measured round-trip efficiency versus current and versus bus voltage.],
) <fig:cap-eff>

#protable(
  caption: [Supercap round-trip efficiency by charge current at 10 V bus.],
  columns: (1fr, 1fr),
  align: (center + horizon, center + horizon),
  [*Charge current*], [*Mean $eta_("RT")$, 3 runs*],
  [0.1 A], [89.7%],
  [0.2 A], [88.3%],
  [0.3 A], [88.2%],
  [0.4 A], [87.0%],
  [0.5 A], [86.9%],
  [0.6 A], [87.4%],
)

#protable(
  caption: [Supercap round-trip efficiency by bus voltage at 0.2 A.],
  columns: (1fr, 1fr),
  align: (center + horizon, center + horizon),
  [*Bus voltage*], [*Mean $eta_("RT")$, 3 runs*],
  [8.0 V], [87.3%],
  [8.5 V], [87.7%],
  [9.0 V], [87.4%],
  [9.5 V], [88.8%],
  [10.0 V], [88.3%],
)

The per-phase split into $eta_("charge")$ and $eta_("discharge")$ is deliberately not reported as a headline figure, because the data shows it is unreliable on this bank. The split needs the open-circuit cap energy $1/2 C V^2$ captured at each settle phase, but the supercapacitor's distributed series resistance means the terminal voltage keeps redistributing after the current stops, exactly the effect the brief warns about. The discharge-side split routinely came out above 100%, which is unphysical, because more energy is drawn from the cap on discharge than the post-settle open-circuit voltage implies. Since $eta_("RT") = E_("out") / E_("in")$ is computed entirely from bus-side measurements it is immune to this, and is the figure carried into Section 11. The finding is itself informative: the cap-side voltage is adequate for the state-of-charge display but not for a clean charge versus discharge efficiency split.

The cap cycle test also feeds the future-work automated PV efficiency measurement (Section 3.3): because the bus-side energy delivered into the cap is directly measured, a PV run that charges the cap can be cross-checked against $E_("in")$ without relying on the cap-side split.

=== Self-Discharge and Hold-Duration Dependence

The cycle-test state machine was extended with a user-controlled zero-current hold phase inserted between charge and discharge, and a hold-duration sweep at 60, 120, 180, 240 and 300 seconds (three runs each, 0.2 A charge and discharge at 10 V bus) was run to characterise self-discharge. @fig:cap-hold-duration shows the resulting drop in round-trip efficiency, and @fig:cap-hold shows the underlying open-circuit relaxation.

#figure(
  image("images/supercap_hold_duration.png", width: 90%),
  caption: [Round-trip efficiency versus zero-current hold duration.],
) <fig:cap-hold-duration>

$eta_("RT")$ falls from 88.3% with no hold to 64.1% after 300 seconds of hold at peak charge. The largest single step is the first minute (88.3% to 77.5%); subsequent minutes contribute a roughly linear 3 percentage-points-per-minute slope. Because $eta_("RT") = E_("out") / E_("in")$ is measured entirely at the bus, this is real energy lost, not a measurement artefact.

#figure(
  image("images/supercap_hold_self_discharge.png", width: 100%),
  caption: [Open-circuit $V_("cap")$ drift after charge: master curve across 13 hold runs.],
) <fig:cap-hold>

@fig:cap-hold underpins the efficiency drop. The median $V_("cap")$ traced across all 0.2 A hold runs (irrespective of their commanded hold length) collapses onto a single relaxation curve, confirming that one underlying mechanism dominates: a fast component of approximately 0.5 V over the first 50 seconds, attributable to dielectric absorption (charge redistribution into deeper dielectric layers @jamieson_charge_redistribution_2021, already flagged in Section 4.1 as the reason the cycle test inserts a settle window before each OCV capture), and a slow component of order 2 to 3 mV per second thereafter, attributable to ohmic leakage through the dielectric. That all hold lengths produce the same curve means the relaxation can be fit once and reused for any hold the algorithm chooses.

The implication for the economic dispatch algorithm in Section 11 is direct: the supercap should be charged just-in-time. Even a few minutes of unscheduled hold at peak state of charge materially erodes the round-trip benefit, and slight scheduling slack is cheaper to absorb on the input side (delay charging by a few minutes) than on the output side (charge ahead and let leakage bleed it down).

#pagebreak()


// ----- 5. Import & Export SMPS (~1000 words) -----------------
= Import & Export SMPS

== Design & Simulation

=== Topology Choice

Both grid-facing modules are configured as synchronous buck converters with the BU/BO switch set to BUCK (the shared power stage is @fig:smps-stage), but their port assignments mirror their opposite roles. The import module places the 12V bench PSU on Port A and the bus on Port B, stepping 12V down to the 10V bus and sourcing current into it; it cannot push current back into the PSU, so its current reference is clamped to non-negative values. The export module places the bus on Port A and a dummy resistor bank on Port B, stepping the bus down into the resistor to dissipate surplus energy; its current reference is likewise clamped non-negative. Both satisfy the Port A above Port B rule by construction.

A natural alternative is one bidirectional module with the 12V PSU and the sink resistor wired in parallel on a single port, eliminating one SMPS. There was a critical issue that ruled this method out. Taking the worst-case 20 W surplus (derived below) without exceeding the 17.5V SMPS port limit requires $R <= 17.5^2 / 20 approx 15$ ohm. At that 15 ohm value, the PSU clamps the shared node at 12V and drives a continuous parasitic dissipation of $12^2 / 15 = 9.6$ W even when the system is idle, roughly half the maximum surplus the converter is being built to handle in the first place. Raising R to cut this loss is no escape either: at 1 kohm the parasitic falls to about 0.14 W but the maximum absorbable export collapses to $17.5^2 / 1000 approx 0.3$ W, three orders of magnitude below the 20 W surplus, and no single fixed R closes the gap. 

The resistance follows from the worst-case exportable surplus. The most the bus could ever need to shed is full irradiance on PV plus peak supercapacitor discharge: two panels in parallel supply under 8W, and the supercapacitor at its 17.5V ceiling and 0.6A average discharge adds about 10.5W, so the surplus stays under 20W. Because the export converter bucks from the 10V bus, the dissipating voltage cannot exceed the bus, so shedding 20W needs a current of $P / V = 20 / 10 = 2$A and a load of $V / I = 10 / 2 = 5$ ohm. The dummy load is therefore a 5 ohm bank and the inductor-current reference is capped at 2A, the point at which the 10V and 2A limits coincide at the 20W corner, and which sits under the module's 2.8A firmware overcurrent trip.

=== Droop Setpoints: 9.9 V Import and 10.1 V Export

Each module runs a cascaded controller: an outer bus-voltage PI produces a current reference, and an inner current PI servoes the inductor current to it (@fig:cascaded-control). The two modules differ only in the sign of the voltage error. The import module computes $v_("err") = V_("target") - V_("bus")$, so it sources more current the further the bus falls below its 9.9V setpoint. The export module computes $v_("err") = V_("bus") - V_("target")$, the sign flipped, so it dissipates more the further the bus rises above its 10.1V setpoint. Each reference is clamped to a non-negative cap of 2.0A on both modules (approximately 20W at the bus), the export value set by the worst-case surplus analysis in Section 5.1.1 and the import value by the grid interface rating.

#figure(
  image("images/cascaded_control_block.png", width: 100%),
  caption: [Cascaded control structure shared by Import and Export SMPS modules.],
) <fig:cascaded-control>

The dead-band that the asymmetric setpoints create is analysed at system level in Section 2.5; what matters here is the implementation. A setpoint of 0.1V or below, or a disable command, is treated as fully off, which is how a higher-level scheduler hands the bus entirely to one side. During bring-up a deliberately wider band was used, with the import target lowered and the export target raised, to stay tolerant of untuned loops and residual noise before narrowing to the final 9.9V and 10.1V once the loops were stable.

== Testing & Implementation

Both bus-facing modules received the same three-layer noise reduction as PV and supercap, applied through a single edit to the shared INA219 driver. Because Import and Export use the common `INA219` class in `common.py` rather than an inline driver, raising the CONFIG word from 0x199F (12-bit, single-sample, 532 us conversion) to 0x1E67 (12-bit, 16-sample averaging, 8.51 ms conversion) inside the class constructor benefited both modules with one change. The four-fold ADC oversample on $V_("PSU")$, $V_("bus")$, $V_("dummy")$ and the software EMA on the V and I traces were duplicated into each module's main loop. Three-second block averages of $P_("import")$ and $P_("dissipated")$ were added with reset triggers on $V_("target")$, $I_("max")$ and enable state, matching the per-module pattern used elsewhere.

 

=== Anti-Windup and Soft-Start Grace

The outer voltage PI on each module uses clamping anti-windup with a tightly bounded integrator. Left at the default integrator bound the term could wind up tens of thousands of times past the value that already saturates the current reference, taking several seconds to unwind once the bus returned to target and producing a slow limit cycle on the bus, observed as the rail swinging between roughly 8V and 12V at about 1Hz when PV and export ran together without the grid module present. Bounding the integrator to the range that just saturates the output lets it wind up only as far as useful and unwind in time proportional to the error.

A soft-start grace window guards the undervolt trip. When the grid module is the only source during bring-up, the bus begins near 0V, which would latch an undervolt trip on the very first tick before the converter has had any chance to lift the rail. The undervolt trip is therefore masked for 500ms on every transition from inactive to active, that is on enable, on watchdog clear, and on trip reset, while the overvolt and overcurrent trips stay armed throughout. The export module carries the same grace logic for symmetry, although its sink-only reference naturally clamps to zero while the bus is below target.

== Evaluation & Optimisation

The import SMPS efficiency is defined as $eta_("import") = P_("bus,delivered") / P_("PSU,drawn")$. The numerator $P_("bus,delivered")$ is the firmware's $P_("import")$ field. The denominator $P_("PSU,drawn") = V_("PSU") dot I_("PSU")$ requires $I_("PSU")$, which is not measured on the import module because the shunt sits on the Port B (bus) side. Unlike the PV case in Section 3.3, however, $I_("PSU")$ is available with no extra instrumentation and no calibration step: the bench PSU's built-in current readout exposes it directly with manufacturer-stated accuracy. The test procedure reduces to "read the three-second-averaged $P_("import")$ off the dashboard, multiply $V_("PSU")$ by the PSU's current reading, take the ratio".

Section 2.3 established that any watt lost in the import path is a watt of grid energy that does not appear on the bus, directly degrading the economic score. Import efficiency therefore deserves disproportionate evaluation attention, and the sweep is correspondingly fine-grained. The bus-voltage axis is swept across nine points from 7 V to 11 V in roughly 0.5 V steps, deliberately wider than the 9.9 V to 10.1 V dead-band so the duty-cycle dependency is captured across the full operating range rather than just the cluster around 10 V. The current axis covers 0.1, 0.2 and 0.3 A, set by the outer voltage PI. At each of the 27 grid points the three-second-averaged $P_("import")$ is recorded against the steady-state PSU current reading.

=== Measured Import Efficiency

@fig:import-eta and the table below present the 27-point sweep at $V_("PSU") = 12$ V. Efficiency rises monotonically with both bus voltage and load current. At the nominal $V_("bus") = 10$ V the converter delivers 83.8%, 89.9% and 92.5% at 0.1, 0.2 and 0.3 A respectively; at the high end of the sweep ($V_("bus") approx 11$ V) the same three numbers rise to 84.7%, 91.3% and 93.6%.

#protable(
  caption: [Measured Import SMPS efficiency by bus voltage and load current.],
  columns: (1fr, 1fr, 1.2fr, 1.2fr, 1.2fr),
  align: center + horizon,
  [*$V_("bus")$ (V)*], [*Duty $D$*], [*$eta$ at 0.1 A*], [*$eta$ at 0.2 A*], [*$eta$ at 0.3 A*],
  [7.0],  [0.58], [77.8%], [86.9%], [89.3%],
  [7.5],  [0.62], [79.0%], [87.3%], [90.0%],
  [8.1],  [0.67], [81.1%], [88.1%], [90.4%],
  [8.5],  [0.71], [81.7%], [88.4%], [90.8%],
  [9.0],  [0.75], [82.1%], [88.9%], [91.2%],
  [9.5],  [0.79], [82.9%], [89.6%], [91.7%],
  [10.0], [0.83], [83.8%], [89.9%], [92.5%],
  [10.5], [0.87], [84.2%], [90.6%], [92.7%],
  [11.0], [0.92], [84.7%], [91.3%], [93.6%],
)

#figure(
  image("images/import_efficiency.png", width: 100%),
  caption: [Measured Import SMPS efficiency versus bus voltage at three load currents.],
) <fig:import-eta>

Both trends are expected from the buck loss model. The bus-voltage dependence reflects the duty cycle: as $V_("bus")$ rises toward $V_("PSU") = 12$ V the duty $D = V_("bus") / V_("PSU")$ approaches unity, inductor ripple shrinks, and the high-side switch spends more of each cycle conducting against a less-than-quadratic increase in $I^2 R$ loss. The current dependence reflects fixed-overhead amortisation: gate-drive consumption and switching loss are largely independent of load, so they consume a larger fraction of throughput at low current. At 0.1 A the converter delivers only about 1 W to the bus and the fixed overheads dominate; at 0.3 A the delivered power is roughly three times larger and the efficiency rises by 6 to 10 percentage points.

For the system-level optimum this is the strongest argument for a bus voltage above 10 V if other constraints allow. Pushing $V_("bus")$ from 10 V to 11 V at $I_("L") = 0.3$ A buys roughly 1.1 percentage points of import efficiency; combined with the Section 3.3.3 result that PV efficiency is approximately flat with bus voltage, the system efficiency is dominated by import behaviour and tilts toward a higher bus voltage. The decision is left to the dispatch algorithm of Section 9, which weighs this against the supercapacitor's reduced energy-storage headroom at a higher bus (the cap window must stay above the bus).

The current axis here is a preliminary low-current characterisation; the originally planned 0.5 to 2.0 A range, covering the operational current band that the import module will see when serving combined LED demand and cap charging, is scheduled as a follow-up to extend the surface upward.

The Export module is excluded from the efficiency sweep. Per the architectural rationale in Section 2.3, the project supervisor confirmed that demo-day power measurements are taken at the DC bus bar itself, so all losses on the export path between the bus and the dummy resistor are counted as if they were part of the dissipated load; export's role is to remove excess bus energy when bus voltage exceeds the export droop setpoint, and the module is sized for cost and simplicity, not for peak conversion efficiency. The dummy-resistor dissipation $P_("dissipated")$ is still reported in the telemetry for the system-level energy balance check in Section 11, but the conversion loss between bus and dummy is not separately characterised.

The exclusion of both Export and LED Load efficiency from the demo-day score is an experimental simplification specific to the assessed metric and is acknowledged as a divergence from real-world deployment economics. In a domestic smart-grid context both paths matter: Export carries electricity sold back to the utility (conversion losses reduce revenue per surplus watt), and the LED Load sits between the bus and the end-use load (conversion losses force a larger bus draw to deliver the same demand, increasing import cost or decreasing export revenue).

#pagebreak()


// ----- 6. LED Load SMPS (~900 words) -------------------------
= LED Load SMPS

== Design & Simulation

=== Topology

The LED load is a triple driver assembly: three independent buck channels (red, yellow, green), each a cut-down SMPS driving a roughly 3W, 1A LED, all controlled by a single Pico W. Buck is the natural choice because an LED forward voltage of around 3V is well below the 10V bus, so the bus is stepped down into each string. The hardware differs from the bidirectional modules in two ways that the firmware must respect. Current is sensed not by an INA219 but by an external SPI ADC of the MCP3208 family, reading three current channels and three voltage channels through one chip select, and the shunt is 0.33 ohm rather than 0.10 ohm, so the inductor current is recovered as $i_("L") = 3 dot V_("shunt")$. Each channel also has a dedicated enable pin that must be driven high on every tick, since the gate driver gates the PWM off whenever its enable is low. The LED forward voltage is reconstructed from the two ADC reads as $v_("LED") = 2 dot v_("v,pin") - v_("i,pin")$, correcting for the sense divider and the shunt drop. One of the three identical driver channels is shown in @fig:led-driver.

#figure(
  image("images/LED_driver.png", width: 92%),
  caption: [LED buck driver power stage, one of three identical channels @clemow_led.],
) <fig:led-driver>

=== Control Mode: CC vs Commanded Power

An LED behaves approximately as a fixed-voltage device, so its power is set by controlling current, which makes a current-controlled inner loop the only sensible drive. The demand from the web server, however, arrives as a power figure, so each channel runs in a commanded-power mode realised through constant current: the demanded power is divided by the measured forward voltage to give a current reference, $i_("ref") = P_("demand") / v_("LED")$, which a per-channel current PI then tracks. The reference is clamped to the channel ratings, 3.0W and 1.05A, and a forward-voltage floor guards the division when a string is dark. When the demanded power for a channel is zero the enable pin is dropped and that channel's PI is reset, preventing the integrator from winding up while the channel is meant to be off.

== Testing & Implementation

The example driver firmware was reworked to drop its external PID dependency in favour of the same inline PI used across the bidirectional modules, giving one consistent controller idiom throughout the project. The per-channel gains and the duty saturation range differ from the bidirectional modules to suit the 0.33 ohm shunt and the driver's own PWM limits. Safety is per channel: if any channel's current exceeds 1.4 times its rated maximum the firmware latches a trip and records which colour tripped, so a single faulty string is diagnosable from the telemetry rather than presenting as a generic fault.

Two bring-up aids proved useful. A boot-time diagnostic samples every SPI ADC channel several times before the control loop starts, with no PWM commanded, so that a phantom overcurrent caused by a floating ADC input, a wrong port, or a brown-out can be told apart from a genuine LED overcurrent simply by reading the printed values. On shutdown the enables are dropped first, which gates the PWM off at the driver regardless of the commanded duty, before the duties themselves are zeroed, guaranteeing the strings go dark cleanly. The shared 10-second watchdog forces all channels off if commands stop arriving.

== Evaluation & Optimisation

Two evaluation axes are reported for the LED Load SMPS: per-channel power-following accuracy, which verifies Requirement 1 quantitatively, and the rationale for not separately characterising conversion efficiency.

=== Power-Following Accuracy

A 60-second scripted tracking test exercises each channel individually and then together, with the commanded and measured per-channel powers logged off the dashboard at 20 Hz. @fig:led-tracking overlays the two: the faint trace is the commanded power and the dark trace the measured power delivered to the LED string. The sequence is red at 2 W for 6 s, off, yellow at 2 W for 6 s, off, blue at 2 W for 6 s, off, all three together at 1, 2 and 3 W for 10 s, off, and a 15-second simultaneous ramp from 0 to 3 W on all three channels.

#figure(
  image("images/led_power_tracking.png", width: 100%),
  caption: [Per-channel commanded and measured LED power across the 60-second tracking sequence.],
) <fig:led-tracking>

Each channel tracks its command within approximately ±3% across all operating points, with the residual driven by per-string forward-voltage variation that the $i_("ref") = P_("demand") / v_("LED")$ division (Section 6.1.2) leaves uncompensated when $v_("LED")$ is itself estimated through the SPI ADC chain. Step settling on each on or off transition resolves inside a single 50 ms dashboard sample. The all-on and ramp phases confirm that channels do not interact through the shared bus or shared SPI ADC, so a multi-colour LED demand is served additively without cross-channel disturbance.

=== Efficiency Exclusion

The LED Load SMPS conversion efficiency is not separately characterised. Per the architectural rationale in Section 2.3 and confirmed directly by the project supervisor, the demo-day power measurements occur at the DC bus bar itself, so any loss occurring between the bus and the LED string is counted on the bus side as load consumption rather than as a deduction from the score. The metric therefore treats LED Load SMPS losses as if they were additional LED dissipation, and there is no scoring benefit to driving LED Load SMPS efficiency above whatever the simplest competent design delivers. The module is sized for cost, current capability and PI robustness rather than peak efficiency, on the same logic that excludes the Export SMPS in Section 5.3.

The real-world deployment implications of leaving the LED Load (and Export) path uncharacterised, and the corresponding future-work efficiency sweep, are discussed alongside the Export equivalent in Section 5.3.

#pagebreak()


// ----- 7. Telemetry Filtering (~700 words) -------------------
= Telemetry Filtering

Noise on the per-module power telemetry was severe enough at first bring-up to obscure the operating-point comparisons that Section 3.3, Section 4.3 and Section 5.3 depend on. Typical jitter on $P_("panel")$ was several hundred milliwatts peak-to-peak against a steady-state mean of a few watts, with similar relative magnitudes on the other modules. The fix is a three-layer attenuation applied identically across the PV, supercap, import and export modules; it is documented once here and referenced by each per-module section.

== Hardware Averaging

The bidirectional template inherits an INA219 CONFIG register of 0x199F (12-bit, single-sample, 532 us conversion @ti_ina219), which lets a substantial fraction of switching ripple through unaveraged, particularly on the shunt channel where ripple amplitude is largest. Reprogramming to 0x1E67 (16-sample averaging, 8.51 ms conversion) across all four bidirectional modules removes the dominant current-channel noise; conversion time rises but stays an order of magnitude below the slowest downstream consumer (the supercap cycle test's 200 ms OCV averaging window, Section 4.3), so the latency is invisible. The change benefited PV and supercap through identical edits to their inline `ina_init` functions and import and export through a single edit to the shared `INA219` class.

Voltage channels are read by the Pico's onboard 12-bit ADC through a resistive divider and walk several LSBs sample-to-sample regardless of the INA219 setting. Each `read_va` and `read_vb` call therefore performs four single reads and right-shifts the accumulated sum by two to take the mean:

$ V_("oversampled") = (V[0] + V[1] + V[2] + V[3]) / 4 $

Cost per call is approximately 10 us, well inside the 1 ms control tick budget. Observed peak-to-peak jitter falls by roughly a factor of 1.6, with diminishing returns past four samples.

== Exponential Moving Average

A first-order EMA is applied in software on top of the hardware-averaged readings:

$ V_("filt")[n] = (1 - alpha) dot V_("filt")[n-1] + alpha dot V[n] $

with $alpha = 0.05$ at the 1 kHz sample rate, equivalent to a time constant $tau approx 20$ ms and a corner frequency around 8 Hz. The filtered signals drive the dashboard display, the three-second block averages, the P&O power comparison (Section 3.2) and the cycle-test energy integrators (Section 4.3). The choice of $alpha = 0.05$ is bounded by two constraints. Too small (longer $tau$) and the filter introduces phase lag that would slow the displayed transient on dashboard reads; too large (shorter $tau$) and the filter passes switching-ripple aliasing through. 20 ms is approximately 60 ms to settle to 95% of a step input, which fits inside the 150 ms second-half averaging window of the P&O dwell and inside the 200 ms tail of the cycle-test settle phases. @fig:ema-response shows the resulting response: a corner near 8Hz that rejects the aliased switching ripple, with a step settling inside 60ms so the displayed transient is barely delayed.

#figure(
  image("images/ema_filter_response.png", width: 100%),
  caption: [Telemetry EMA magnitude and step response at alpha = 0.05.],
) <fig:ema-response>

A critical design decision is that the inner PI loops and the safety guards continue to consume the raw single-sample readings, not the filtered values. Two reasons. First, introducing a 20 ms phase lag into a current PI tuned against unfiltered inputs would shift its stability margin and require retuning. Second, the trip thresholds in each module (panel undervolt, bus overvolt, overcurrent) were designed for instantaneous response; a filtered safety guard would react with a 20 ms delay, slow enough to allow more energy to flow into a fault before tripping. Keeping the filter strictly on the display and characterisation paths preserves both control-loop behaviour and trip response while still giving the operator clean numbers to read.

== Three-Second Block Average

Each module computes a true block average of its bus-side power over a three-second window in firmware:

$ P_("avg3s") = (1 / N) sum_(i=1)^(N) P[i] $

with $N = 3000$ at 1 kHz. The window restarts on changes to the module's commanded operating point (MPPT mode for PV, $I_("cmd")$ for supercap, $V_("target")$ and $I_("max")$ for import), so each completed average reflects a single operating point. Float-rounding the operating-point tuple before comparison avoids spurious resets from JSON-parser dust. The completed average is what the operator reads from the dashboard during the side-by-side comparisons in Section 3.3 and Section 5.3, and it sits on top of the cycle phase changes inside the supercap cycle test as a real-time sanity check that the commanded current has settled.

== Evaluation

The combined three-layer treatment is evaluated by the noise reduction it delivers on the per-module bus-side power telemetry. @fig:noise-raw-filt overlays a representative raw single-sample trace against the same operating point after the three-layer filter, with the absolute level shifted to a 2 W PV operating point for visual context.

#figure(
  image("images/noise_raw_vs_filtered.png", width: 100%),
  caption: [Bus-side power telemetry: raw single-sample versus three-layer filtered.],
) <fig:noise-raw-filt>

Raw $P_("panel")$ jitter falls from approximately 300 mW peak-to-peak at the 1 kHz tick to under 10 mW per P&O dwell-averaged comparison (Section 3.2), roughly a 30 to 1 reduction. Equivalent attenuation on the supercap, import and export modules brings the three-second-averaged power readings inside a few milliwatts of run-to-run reproducibility, fine enough to resolve the 1.4 percentage-point irradiance-to-irradiance spread in the PV efficiency sweep (Section 3.3) and the 1 to 2 percentage-point steps between adjacent supercap charge currents in the round-trip sweep (Section 4.3).

#pagebreak()


// ----- 8. User Interface (~1000 words) -----------------------
= User Interface

The user interface satisfies the brief's requirement for a display of current and historic information about energy flows and stores, and extends it with full operator control of every module. The whole stack was written in-house as three cooperating tiers.

== Architecture

The lowest tier is a hand-rolled HTTP server embedded in every module's firmware. It exposes a telemetry endpoint and a command endpoint and runs on the Pico's second core, deliberately isolated from the 1kHz control loop on the first core, so that no network activity can ever stall or jitter the safety-critical control timing. Telemetry is published as a JSON snapshot and commands are accepted as a JSON object merged into the module's command dictionary.

The middle tier is a Python backend built on FastAPI with a SQLite store. A poller fetches the telemetry endpoint of each module on a roughly one-second cadence and the external grid signals (demand, irradiance, buy and sell price, and the deferrable-load list) once per tick, writing both into time-stamped tables. Grid snapshots are de-duplicated by day and tick so the history is clean. The backend then serves this data to the frontend through a small set of read endpoints for the latest grid state, recent snapshots, and per-module telemetry.

The top tier is a React single-page application built with Vite. It polls the backend on a short interval, keeps a client-side rolling history of recent samples per module, and renders three operator views.

#figure(
  image("images/ui_stack_architecture.png", width: 100%),
  caption: [User interface stack with independent telemetry and command paths.],
) <fig:ui-stack>

@fig:ui-stack summarises the stack and the two independent data paths discussed in Section 8.3: telemetry flows bottom-up through the backend, while commands go straight from the browser to each module, bypassing the backend so a backend or database outage never blocks operator control.

== Operator Views

The default My Energy view is a consumer-facing dashboard styled after a domestic energy provider. It presents the live grid state as demand and irradiance bar charts, a module status grid that flags each module as online, stale, tripped, on watchdog, or disabled, the current buy and sell prices, and the deferrable-load list rendered as progress bars showing each job's window and time remaining. The SMPS Overview view plots per-module telemetry histories (panel, bus, capacitor and load voltages, currents and powers) as line charts drawn from the stored snapshots. The SMPS Modules view is the engineering control surface: one card per module showing its live statistics, a mini history chart, a status pill, and a control panel tailored to that module's role.

The control panels expose exactly the commands each module understands. The PV card switches between fixed, web-lookup and Perturb-and-Observe MPPT and sets a manual maximum-power voltage. The grid and export cards set the bus target and current cap and toggle the module off by setting a zero target. The supercap card offers a signed current slider with charge, discharge and stop shortcuts, and triggers the self-contained efficiency cycle test. The LED card sets per-channel power demands. Every card carries enable, disable and reset-trip controls.

== Control and Telemetry Paths

A deliberate design choice is that the control path and the telemetry path are independent. Telemetry flows up through the backend and database, but commands are sent straight from the browser to each module's own command endpoint, using the permissive cross-origin policy the firmware sets for this purpose. The two paths therefore share no single point of failure: if the backend or database is down the operator can still command modules directly, and if a module's command endpoint is unreachable the rest of the system keeps reporting. Combined with the firmware watchdog, which forces a module to safe defaults if commands stop arriving, this keeps the interface advisory rather than safety-critical, consistent with the coordination philosophy of Section 2.5.

== On-Module Fallback Dashboard

As a final redundancy a complete single-file dashboard is bundled into the firmware filesystem and served by the module's own HTTP server at its root path. This gives a usable monitoring and control surface with no backend, no database and no Node toolchain running at all, which is valuable during bench bring-up and as a fallback if the main stack is unavailable on demo day.

#pagebreak()


// ----- 9. Algorithm Software (~1000 words) -------------------
= Algorithm Software

This section covers the system-level coordinator that turns the acquired price, demand and irradiance signals into dispatch decisions across the modules. The per-module control loops of Sections 3 to 6 and the data-acquisition pipeline of Section 8 are complete; the economic decision policy that sits on top of them is the project's principal remaining work ahead of demo day, so the subsections below state the problem the coordinator must solve and the fault model it inherits, and leave the decision policy and its evaluation to be reported once implemented.

== Master Loop & Timing Budget

The coordinator runs as a 1 Hz outer loop on the host, two orders of magnitude slower than the 1 kHz inner control tick on each module. Each tick the coordinator polls every module's telemetry endpoint and the live price, demand and irradiance feeds, evaluates the decision policy of Section 9.3, and posts updated current and power setpoints back to each module's command endpoint. The 1 Hz cadence is matched to the timescale of the economically relevant variables (prices update at most minutely; irradiance drifts on tens of seconds; demand on seconds to minutes) and intentionally decoupled from the per-module loops, so a coordinator stall cannot destabilise the bus: local droop, watchdogs and PI controllers continue to run autonomously. The same decoupling lets coordinator development proceed in parallel with bench work on the modules.

== Economic Model

The objective is set directly by the brief: minimise the net cost of grid energy over a daily cycle while always meeting demand. With import and export power metered at the bus, the cost accumulated over the cycle is

$ C = sum_t (P_("import")(t) dot p_("buy")(t) - P_("export")(t) dot p_("sell")(t)) dot Delta t $

where $p_("buy")$ and $p_("sell")$ are the per-tick prices read from the web service. The coordinator minimises $C$ subject to a power balance at the bus on every tick,

$ P_("PV") + P_("import") + P_("cap,dis") = P_("demand") + P_("export") + P_("cap,chg") + P_("loss") $

and to several constraints: the instantaneous demand must be met at all times; each deferrable job must receive its specified energy somewhere inside its allowed time window; the supercapacitor must stay within its energy window and current limit (Section 4); and import and export must stay within their current caps (Section 5).

The levers available to the coordinator are therefore which deferrable loads to run when, when to charge or discharge the supercapacitor, and when to import or export. The economically interesting behaviour is temporal arbitrage: deferring flexible loads into ticks with cheap energy or surplus PV, charging the cap when price is low or PV would otherwise be curtailed, and discharging it (or exporting) when price is high. The brief sets the bar explicitly: the policy must beat a naive baseline that always minimises instantaneous import or export and serves every demand immediately. That baseline is the natural comparison point for the evaluation once the policy is implemented.

== Decision Policy / State Machine

== System-Level Fault Handling

Because the coordinator is advisory rather than safety-critical (Section 2.6), system-level robustness currently rests on distributed mechanisms already present in firmware rather than on a central fault handler. Each module carries a watchdog that forces it to safe defaults if commands stop arriving, so a stalled coordinator or dropped link degrades the economic optimisation without threatening the bus, which continues to regulate on local droop. Latching trips with dashboard reset, the soft-start grace window, and the per-module current and voltage clamps described in Sections 3 to 6 contain faults locally. A centralised fault response that reacts to module dropout or trips at the dispatch level is left as future work alongside the decision policy.

== Evaluation

#pagebreak()


// ----- 10. Mechanical Design & Project Polish (~400 words) ---
= Mechanical Design & Project Polish

== 3D-Modelled SMPS Enclosure

The four bidirectional SMPS boards were housed in a 3D-printed chassis rather than left as loose boards on the bench. The enclosure fixes each board in a defined position with spacing for airflow between the converters, also giving the assembly a single rigid form that can be moved and demonstrated without disturbing the wiring. 

The chassis went through one revision driven by thermal observations on the bench. The v1 print packed the SMPS slots tightly to minimise footprint, but extended usage showed the inter-slot gap was too narrow to support adequate passive convection, with risk of board overheating. The v2 revision in @fig:smps-stand widened the gap between adjacent SMPS slots and added through-holes on the side walls to restore a clear convective path through and around each board. 

#figure(
  grid(
    columns: (1fr, 1fr),
    column-gutter: 10pt,
    image("images/smps_stand_before.png", width: 100%),
    image("images/smps_stand_after.png", width: 100%),
  ),
  caption: [SMPS stand iteration: v1 (left) and v2 (right)],
) <fig:smps-stand>

== Cable Management and Connector Choice

Power interconnects use 4mm banana leads into the shared DC busbar, the connector standard of the lab kit, so any module can be attached to or removed from the bus without tools and without disturbing the others, mirroring at the physical layer the modular join-and-leave property that the droop coordination provides electrically. Routing the bus connections through a single busbar keeps the high-current paths short and identifiable and gives an unambiguous single point at which demo-day bus power is measured.

#pagebreak()


// ----- 11. System-Level Testing & Evaluation (~1000 words) ---
= System-Level Testing & Evaluation

== Test Scenarios

System-level evaluation comprises two categories of test: per-module SMPS efficiency characterisations (the headline numbers reported here), and full demo-day economic-dispatch dry runs against scripted price-and-irradiance profiles. The first is described in this section; the second is introduced in Section 9.

=== Per-Module Efficiency Sweeps

Each SMPS module is characterised across a small grid of operating points, with the test method tailored to the instrumentation available on that module's port assignment. The three methods are summarised below; full details for each are in the relevant per-module evaluation subsection.

PV SMPS (Section 3.3): manual measurement using a DMM placed in series with the PV-to-bus wire. The pre-loss panel power $P_("panel,in")$ is available directly from the firmware (both factors are Port B); the post-loss bus power $P_("bus,out")$ requires the external DMM because Port A is uninstrumented. Both axes are complete: twelve bus-voltage points from 7.1 to 12.55 V at each of four irradiance settings (25%, 50%, 75%, 100%), 48 measurements total. The four irradiance curves give means of 96.5%, 96.7%, 97.0% and 97.9% rising monotonically with irradiance, and are flat with bus voltage to within ±0.3%.

Supercap SMPS (Section 4.3): fully automated cycle test triggered from the host dashboard. The test integrates bus-side $E_("in")$ and $E_("out")$ at the 1 kHz tick and reports the round-trip efficiency $eta_("RT") = E_("out") / E_("in")$ from a single charge and discharge cycle. The sweep covers charge and discharge current at six levels (0.1 to 0.6 A in 0.1 A steps) at a 10V bus, bus voltage at five levels (8.0 to 10.0 V) at 0.2 A, and hold duration at six levels (0 to 300 s) at 0.2 A. The measured round-trip efficiency is approximately 88% with no hold, falling to 64% after a 300 s hold at peak charge.

Import SMPS (Section 5.3): manual measurement using the bench PSU's built-in current readout for the pre-loss $P_("PSU,drawn")$ side; the post-loss $P_("bus,delivered")$ is available from the firmware. Bus voltage is swept across nine points from 7 V to 11 V in 0.5 V steps; current is set at 0.1, 0.2 and 0.3 A by the outer voltage PI. The 27-point grid is complete and gives $eta_("import")$ rising monotonically from 77.8% (low current, low bus) to 93.6% (high current, high bus), with 83.8%, 89.9% and 92.5% at the nominal $V_("bus") = 10$ V at 0.1, 0.2 and 0.3 A respectively. A 0.5 to 2.0 A current extension is scheduled to characterise the operational current band.

Export SMPS is not characterised for efficiency because its losses occur between the bus and the dummy resistor and are not counted by the demo-day metric (Section 2.3).

== Performance Metrics

The headline metrics extracted from the efficiency sweeps are tabulated below. Each entry is a ratio of post-loss output power to pre-loss input power, averaged over the relevant operating window. For the supercap, the round-trip efficiency is reported per operating point, the per-phase charge and discharge split being confounded by the cap's charge redistribution (Section 4.3). For PV and import, a single number is reported per operating point. All numbers are accompanied by their operating point (bus voltage, current, irradiance) and by the underlying $P_("in")$ and $P_("out")$ raw readings so the ratios can be audited.

In addition to the SMPS efficiency table, two derived system-level checks are reported. First, the steady-state bus voltage. Observed at idle, the bus holds within approximately ±0.05 V of the 10 V nominal, comfortably inside the ±0.1 V droop deadband defined in Section 2.3, which is sized as a safety margin against transient sag and disturbance rejection rather than for steady-state regulation. Second, the energy balance closure across the bus for full-cycle scenarios:

$ E_("PV,bus") + E_("import,bus") = E_("export,bus") + E_("LED,bus") + E_("supercap,bus") + E_("losses,bus") $

The unmodelled $E_("losses,bus")$ residual captures bus-wire $I^2 R$ and any uncharacterised dissipation, and is expected to be small (a few percent at most) if the per-module post-loss measurements are consistent. An anomalously large residual on a closure check is treated as a regression signal for the per-module efficiency numbers.

== Requirements Verification Matrix

Each of the brief's six requirements is mapped below to the subsystem that realises it, the test that verifies it, and its current status. Requirement 5, the economic dispatch algorithm, is the principal item still in progress (Section 9); the remainder are implemented and verified by the tests described in the cited sections.

#protable(
  caption: [Brief requirements: verification method and current status.],
  columns: (0.5fr, 2fr, 1.4fr, 1.5fr, 1.4fr),
  align: (center + horizon, left + horizon, left + horizon, left + horizon, left + horizon),
  [*Req*], [*Requirement*], [*Realised by*], [*Verification*], [*Status*],
  [1], [Supply domestic LEDs per web demand], [LED Load SMPS (Section 6)], [Power-tracking test (Section 6.3)], [Implemented; tracking within ±3% across channels],
  [2], [Extract PV energy with MPPT], [PV SMPS (Section 3)], [MPPT mode comparison; efficiency sweep], [Efficiency sweep complete; MPPT comparison scheduled],
  [3], [Store excess in supercap, no batteries], [Supercap SMPS (Section 4)], [Cycle test; round-trip efficiency], [Implemented],
  [4], [Import and export to grid, metered], [Import/Export SMPS (Section 5)], [Import efficiency sweep; bus dead-band], [Implemented; 0.5 to 2.0A current extension scheduled],
  [5], [Minimise cost; schedule storage and deferrables; beat naive], [Algorithm (Section 9)], [Dry run versus naive baseline], [In progress],
  [6], [UI for current and historic energy data], [User Interface (Section 8)], [Live dashboard; telemetry plots], [Implemented],
)

#pagebreak()


// ----- 12. Conclusion (~150 words) ---------------------------
= Conclusion

The project delivered a five-module DC microgrid that regulates a shared 10V bus across PV generation, supercapacitor storage, a bidirectional grid interface and a programmable LED load. The two grid-facing converters coordinate the bus through symmetric droop with a 0.2V dead-band, holding the bus inside ±0.05V of nominal without a central coordinator and degrading gracefully under communication loss. The PV module reaches 96 to 98% conversion across irradiance and bus voltage under selectable lookup-table and P&O MPPT; the import converter spans 78 to 94% across its operating sweep; the supercapacitor is a command-driven store with a self-contained cycle test that returns approximately 88% round-trip efficiency from bus-side energy alone; the LED load follows commanded power through constant current with per-channel tracking inside ±3%. A three-layer telemetry filter chain attenuated raw bus-side power jitter by roughly 30 to 1, and a self-coded React and FastAPI interface provides monitoring and control on independent paths so a backend outage does not block operator action. The principal remaining work before demo day on 18 June 2026 is the economic dispatch algorithm that turns the acquired price and demand signals into cost-minimising decisions.

// ============================================================
//  References
// ============================================================
#pagebreak()
#bibliography("references.bib", title: "References", style: "ieee")
