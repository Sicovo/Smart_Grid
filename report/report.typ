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

The Smart Grid is a DC microgrid built from five cooperating SMPS modules. It balances generation, storage and load on a shared 10V bus while minimising net grid cost through import, export and supercapacitor charge or discharge. Each converter regulates its own current flow against a local bus measurement, with a central coordinator setting dispatch commands. The system operates from a 12V primary supply onto a 10V bus with a ±0.1V droop band, allowing each module to act autonomously on the bus voltage signal. A Pico W on every module runs the control loop and provides INA219 or SPI ADC telemetry to a user-facing dashboard. A 3D-printed chassis houses the SMPS boards for airflow and mechanical protection.

#v(0.5cm)
#align(center)[
  #text(size: 10pt, style: "italic")[Word count: #text(weight: "bold")[11861]]
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

The project delivers a five-module DC microgrid that regulates a shared 10V bus across PV generation, supercapacitor storage, grid import, grid export and a programmable LED load. The control system dispatches power between modules to minimise net cost under a time-varying tariff. The prototype is evaluated on demo day, 18 June 2026, against a published price-and-load scenario.

== Project Management System & Time Planning

Coordinating a seven-member hardware and software team across a five-week delivery window required tooling that off-the-shelf platforms could not provide as a single integrated system. Rather than stitching together Notion, Trello, Microsoft Teams and ChatGPT, each of which solves only a fragment of the problem individually, an AI-powered Project Management System (PMS) was coded by our team for the project. Every layer of the frontend, backend, AI pipeline and database schema was purpose built around our needs.

#figure(
  image("images/pms_dashboard.png", width: 100%),
  caption: [PMS dashboard: countdown, budget, stats and todo.],
) <fig:pms-dashboard>

The platform is structured around four modules. A live operational dashboard (@fig:pms-dashboard) displays the project's current situation and deadlines. An automated meeting transcript module (@fig:pms-transcript) records, transcribes and structures every meeting into attendee lists, discussion summaries and extracted action items. An AI-driven article and documentation generator named Aria (@fig:pms-article) produces project-specific technical writing such as component-selection notes and lab write-ups. A Retrieval-Augmented Generation (RAG) project chat (@fig:pms-rag) compiles Aria articles, meeting minutes, the GitHub firmware repository, datasheets and test results into context for the AI to analyse and discuss with team members.

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

Several additional features were built other than the four core modules (@fig:pms-extras). A shared calendar with a Gantt-style timeline consolidates every milestone and submission deadline so that everyone is aware of the project timeline. A project gallery centralises lab photographs that would otherwise be unorganised and scattered across personal phones. A test results module captures raw measurement data with built-in charting, removing the need for data transfer between spreadsheet software. Finally, lightweight personalisation through the team buddy selector motivates team members to actively log on to the platform and increases productivity.

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

== Role Allocation

Work was split into one Task Master and one Task Assistant per hardware module and software stack, summarised in @tbl:role-allocation. The Task Master owned the design, build and report writing for their module, while the Task Assistant supported bring-up, ran cross-checks and reviewed the writing. Report-structure authoring was led by Hong Zhe, with Chun Wen and Yong Zhi acting as report checkers.

#protable(
  caption: [Per-module role allocation across hardware and software.],
  columns: (1.1fr, 1fr, 1fr, 1fr, 1.1fr, 1.2fr, 1fr, 1fr),
  align: center + horizon,
  [], [*PV Panel*], [*LED Load*], [*Import (PSU)*], [*Export (Load Bank)*], [*Supercapacitor*], [*Backend*], [*Frontend*],
  [*Task Master*], [Chun Wen], [Yong Zhi], [Wei Zen], [Yi Da], [Hong Zhe], [Dzuldiniy], [Fangnan],
  [*Task Assistant*], [Hong Zhe], [Yi Da], [Chun Wen], [Wei Zen], [Yong Zhi], [Fangnan], [Dzuldiniy],
) <tbl:role-allocation>

#pagebreak()


// ----- 2. System Architecture & Key Design Decisions (~1500) -
= System Architecture & Key Design Decisions

This section covers the hardware architecture: module roles, microgrid topology, bus and supply voltages, the droop coordination scheme and the inter-module communication protocol. The software architecture, dispatch algorithm and operator dashboard that sit on top are covered separately in Sections 8 and 9.

== Module Roles

#protable(
  caption: [Per-module topology, external component, control mode and bus role.],
  columns: (1fr, 1.3fr, 1.2fr, 1.1fr, 1.6fr),
  align: left + horizon,
  [*Module*], [*External component*], [*Topology*], [*Control*], [*Role on the bus*],
  [Grid Import SMPS], [12V grid PSU], [Buck], [CV, droop at 9.9V], [Sources current when bus < 9.9V],
  [Grid Export SMPS], [Sink resistor], [Buck], [CV, droop at 10.1V], [Sinks current when bus > 10.1V],
  [PV SMPS], [PV panel], [Boost], [MPPT], [Harvests panel power into bus],
  [Supercapacitor SMPS], [10.5 to 17.5V supercapacitor], [Bidirectional buck/boost], [CC, commanded], [Stores or releases on command],
  [LED Load SMPS], [3V LED module], [Buck (internal)], [CC], [Drives the LED load],
)

The system comprises five SMPS modules connected to a shared 10V DC bus. The import and export modules share a synchronous-buck topology and a common droop, differing only in setpoints; this creates the dead-band discussed in Section 2.4. The Supercapacitor SMPS does not droop and runs as a commanded current source, so the economic algorithm in Section 9 can use it to buy energy cheap and sell it expensive. The LED Load SMPS is internally managed; only its bus-side draw is exposed. All four bidirectional modules use the same power stage in @fig:smps-stage, with a 100 µH inductor and a 100 mΩ shunt on Port B. The roles in the table depend on the port connections, not on the hardware, so per-module sections refer back to this single stage.

#figure(
  image("images/bidirectional_power_stage.png", width: 100%),
  caption: [Bidirectional SMPS power stage, common to all four modules @clemow_smps.],
) <fig:smps-stage>

== Overall Microgrid Topology

@fig:arch-block shows the complete system. External components sit at the top, each connected through its SMPS module to the shared 10V DC bus. A dedicated Pico W on every module runs the local control loop. A FastAPI backend checks the Azure-hosted web service once per second for a new simulation tick, fetching the demand, price, irradiance and deferrable data when one appears; each new tick triggers the dispatch decision (Section 9), whose setpoints are pushed to each module over HTTP. The operator dashboard renders telemetry from the same backend.

#figure(
  image("images/arch_block.png", width: 100%),
  caption: [Smart Grid system architecture and power flow.],
) <fig:arch-block>

Three properties of this topology recur in later sections. First, every module is autonomous in its bus-regulation role: it acts on its local $V_("bus")$ measurement alone, with the backend supplying only setpoints and economic context. Second, all demo-day power measurements occur at the bus, never at SMPS terminals. Third, the supercapacitor is the only element that stores energy across timescales longer than the bus capacitance, which puts its commanded behaviour at the centre of the economic optimisation.

== Voltage Architecture: 10V Bus, ±0.1V Droop Band and 12V PSU

The voltage architecture is fixed by the operating windows of the PV panel, supercapacitor and grid-interface converters. A 10V nominal bus is the smallest round-number voltage that sits below the supercapacitor charge window, above the PV panel open-circuit voltage of about 8.5V, and reachable from a 12V buck input (justified below). Raising the bus would add switching stress with little benefit; lowering it would reduce the supercapacitor margin and increase the PV boost ratio.

Each droop-controlled module follows a local linear control law of the form

$ I_("module") = (V_("set") - V_("bus")) / R_("droop") $

with sign and saturation set by module role. $R_("droop")$ is sized so each module reaches its rated current at the edge of the ±0.1V band, bounding the full-load steady-state bus error to ±1% of nominal. This keeps the bus stiff enough for downstream modules while regulation stays local.

The bus voltage choice also affects the scoring of converter losses. Demo-day measurements are taken at the bus, so LED Load and Export losses occur after the measured point and are counted as load or dissipated export power; their efficiency does not affect the score directly. Import losses occur before energy reaches the bus, so every watt lost between the 12V supply and the bus is grid energy missing from the measured balance.

The 12V PSU is the lowest practical input that preserves buck regulation with sufficient headroom, while avoiding the switching loss a higher input would add. For a synchronous buck converter @erickson_fundamentals_2020,

$ P_("cond") = D dot I_("rms")^2 dot R_("ds,on,HS") + (1 - D) dot I_("rms")^2 dot R_("ds,on,LS") $

which reduces to

$ P_("cond") = I_("rms")^2 dot R_("ds,on") $

for matched MOSFETs. The dominant conduction term is therefore independent of both $D$ and $V_("in")$. Switching loss scales with $V_("in")$ or $V_("in")^2$:

$ P_("sw") approx 1/2 dot V_("in") dot I_("load") dot (t_r + t_f) dot f_("sw") + 1/2 dot C_("oss") dot V_("in")^2 dot f_("sw") $

and inductor ripple shrinks as $V_("in")$ approaches $V_("bus")$:

$ Delta I_L = (V_("in") - V_("bus")) dot D dot T / L $

The binding constraint is therefore dropout, not efficiency: with $D = V_("bus") / V_("in")$, duty tends to unity as the input approaches $V_("bus")$, but a real converter cannot reach $D = 1$ due to minimum off-time, gate-driver refresh and maximum-duty limits. With a maximum duty of about 0.9, regulation is lost below $V_("bus") / 0.9 approx 11$V. A 12V bench supply leaves margin above this floor while staying close enough to the bus to limit switching loss.

@fig:buck-vin-eff shows a flat usable region rather than a strong efficiency optimum: across 11 to 15V at a 10V bus and 1.5A load, modelled loss changes by only tens of milliwatts, about 0.2% of delivered power. The sharp collapse below this region is dropout. The 12V point sits on the flat plateau with margin to spare; a future confirmation sweep from 11 to 14V at $V_("bus") = 10$V would verify the predicted shallow efficiency rise and the dropout cliff.

#figure(
  image("images/buck_vin_efficiency.png", width: 100%),
  caption: [Modelled buck efficiency and loss split versus input voltage.],
) <fig:buck-vin-eff>

== Coordination Scheme: Symmetric Droop vs Mutex Arbitration

Two architectures were considered. Mutex arbitration assigns bus control to one module at a time, with a coordinator switching modes as conditions change; symmetric droop, the established primary-control approach for DC microgrids @dragicevic_dcmg_2016, lets every module act at once on its local $V_("bus")$ measurement. Mutex gives tighter steady-state regulation, but it places the communication channel inside the safety-critical bus-regulation loop — a dropped link or stalled coordinator collapses the bus — and every handover adds a voltage transient. Droop keeps each loop local and continuous: a communications failure degrades the economic optimisation but not bus stability, the curves blend without handover transients, and the cost is a small steady-state error bounded to ±0.1V by design (Section 2.3).

Symmetry is enforced by mirroring the import and export setpoints about the 10V nominal:

$ V_("set,import") = 9.9 "V" quad quad V_("set,export") = 10.1 "V" $

This creates a dead-band $V_("bus") in [9.9, 10.1]$V in which neither grid-facing module acts and the bus is held by the PV module and supercapacitor alone — the no-cost configuration the algorithm in Section 9 maximises. Outside it, the system falls back to grid import or export with no explicit mode-change logic. @fig:droop-curves and @fig:busbar-deadband show the droop curves and a load cycle moving between import, dead-band and export regimes without central arbitration.

#figure(
  image("images/droop_curves.png", width: 85%),
  caption: [Droop curves: module current versus bus voltage.],
) <fig:droop-curves>

#figure(
  image("images/busbar_deadband.png", width: 100%),
  caption: [Bus voltage and converter currents across import, dead-band and export.],
) <fig:busbar-deadband>

#pagebreak()


// ----- 3. PV SMPS (~1000 words) ------------------------------
= PV SMPS

== Design & Simulation

=== Topology Selection

The bench setup uses one PV panel rated at approximately 4W under full bench-emulator illumination at room temperature, with a datasheet open-circuit voltage of 8.5V and short-circuit current of 1.0A. Demo day adds a second identical panel in parallel for roughly double the available harvest, sharing the same MPP voltage but doubling the current. The single-panel characterisation in Section 3.3 transfers directly to the demo-day configuration: the per-panel MPP voltage is unchanged, so the MPPT lookup table, the P&O dwell behaviour and the boost converter's operating duty all stay valid; only the per-panel current at the bus doubles, which sits well under the 1.5A inductor current cap. Under the solar emulator the measured open-circuit voltage was about 7.5V, with the MPP near 5.20V at full irradiance and 5.10V at low irradiance (@fig:pv-iv). Each curve was taken by stepping the panel voltage from 2V toward the open-circuit knee (with denser sampling around the MPP) at one of six emulator dimmer settings (25% to 100%). Since the MPP voltage (around 5V) is below the 10V bus, energy reaches the bus by stepping up, so the module runs as a boost converter.

#figure(
  image("images/pv_iv_measured.png", width: 100%),
  caption: [Measured PV panel I-V and P-V curves with the MPP locus.],
) <fig:pv-iv>

The panel is wired to Port B (lower, variable voltage) and the bus to Port A (fixed 10V), satisfying the hard constraint $V_("A") > V_("B")$. The BU/BO switch is set to BOOST, and unlike the buck modules the PWM is not inverted: the firmware writes duty directly rather than the `65536 - pwm_out` form.

Current is sensed by the INA219 across the 0.10 Ω Port B shunt. The shunt is wired in the Port A to Port B sense direction, so the firmware negates the reading; a positive inductor current then corresponds to panel-to-bus boost flow. The controller is cascaded: an outer voltage PI servoes the panel voltage to the commanded $V_("mpp")$, and an inner current PI drives the duty. The operating point is set by whichever MPPT strategy is active.

=== MPPT Strategy: Fixed Voltage vs Lookup Table vs P&O

Three MPPT approaches were considered and prototyped: a static constant-voltage operating point (Fixed), an irradiance-indexed lookup table (LUT) driven by the Azure `/sun` feed, and online Perturb and Observe (P&O). @fig:pv-vmpp shows $V_("mpp")$ varying by only 0.10V across the full irradiance range, so a fixed 5.15V setpoint would lose under 1% of available harvest at every characterised point at thermal equilibrium. The headline trade-offs are summarised in @tbl:mppt-modes.

#protable(
  caption: [MPPT mode comparison: Fixed, LUT and P&O.],
  columns: (0.6fr, 1.4fr, 1.2fr, 1.2fr),
  align: left + horizon,
  [*Mode*], [*Description*], [*Benefits*], [*Disadvantages*],
  [Fixed], [Constant $V_("mpp")$ at 5.15V.], [Simple; no external feed; no oscillation.], [Open-loop on temperature.],
  [LUT], [$V_("mpp")$ interpolated from the Azure `/sun` value.], [Tracks irradiance; immediate settling.], [Needs characterisation and the web link; open-loop on temperature.],
  [P&O], [Perturbs $V_("mpp")$, keeps or reverses by power comparison @femia_po_2005.], [No external feed; corrects temperature drift.], [Oscillates around the peak; noise-sensitive; slower convergence.],
) <tbl:mppt-modes>

#figure(
  image("images/pv_vmpp_irradiance.png", width: 78%),
  caption: [Measured Vmpp and Pmax versus irradiance: the MPPT lookup table.],
) <fig:pv-vmpp>

Shipping all three gives a clean comparison under identical conditions and a fallback path if the web link fails: LUT drops to Fixed mode, and P&O stays available as an autonomous fallback.

== Testing & Implementation

=== Bench Noise Treatment

The three-layer noise treatment (Section 7) was applied to the PV telemetry before bring-up; the filtered values feed the dashboard and the P&O power comparison while raw readings are retained for the control loop and trip guards.

=== P&O Implementation

P&O uses a two-timescale structure. The outer voltage PI tracks the commanded $V_("mpp")$ at 100 Hz; perturbations occur on a 300 ms cadence ($T_("dwell")$), roughly five times the outer-loop settling time, so the power measured at the end of a dwell reflects steady state, not the PI transient. The comparison power is the filtered $V_("panel,lp") dot I_("L,lp")$ accumulated over the second half of each dwell and averaged. Two-stage filtering (EMA then dwell average) brings the per-comparison noise floor under 10 mW, well below the $P(V_("mpp"))$ curvature near the peak.

A direction-flip rule with a dead-band stops the three-point oscillation degenerating into noise. If dwell-averaged power dropped by more than $epsilon = 20$ mW versus the previous dwell, direction reverses; otherwise it continues. The commanded $V_("mpp")$ is hard-clamped to 4.75V to 5.5V, a narrow window centred on the measured 5.10 to 5.20V MPP locus (@fig:pv-vmpp), so an algorithm fault cannot walk the operating point into open-circuit or short-circuit territory. On entry to P&O mode the state is reseeded from the last commanded fixed-mode $V_("mpp")$, avoiding a stale value. A three-second block average of $P_("panel")$, restarting on each mode switch, was added to the firmware telemetry so the operator can read steady-state delivered power for each MPPT mode straight from the dashboard; the live trace captures tracking noise separately.

== Evaluation & Optimisation

Two evaluation axes are reported: MPPT mode comparison, and SMPS conversion efficiency.

=== MPPT Mode Comparison

Each MPPT mode is tested at 25%, 50%, 75% and 100% irradiance. At each setting the three-second block-averaged $P_("panel")$ is recorded in fixed mode, LUT mode, and P&O mode. $V_("mpp,target")$ and $v_("panel")$ are logged throughout so the mode-switch transient can be inspected. The primary metric is steady-state delivered power; the secondary metric is the mode-change transient.

Mean recorded powers per mode and irradiance are summarised in @fig:mppt-means and tabulated below.

#protable(
  caption: [Recording-phase mean panel power per MPPT mode and irradiance.],
  columns: (1fr, 1fr, 1fr, 1fr, 1fr),
  align: center + horizon,
  [*Irradiance*], [*Fixed (W)*], [*LUT (W)*], [*P&O (W)*], [*Spread (mW)*],
  [25%],  [0.767], [0.770], [0.770], [3],
  [50%],  [1.933], [1.932], [1.933], [1],
  [75%],  [2.845], [2.841], [2.841], [4],
  [100%], [3.577], [3.562], [3.550], [27],
)

#figure(
  image("images/mppt_test_means.png", width: 100%),
  caption: [Mean delivered panel power by MPPT mode at four irradiance settings.],
) <fig:mppt-means>

The three modes converge to within a few mW at every irradiance; the worst-case spread of 27 mW at 100% is under 1% of the 3.55 W operating point. This is what the construction predicts: P&O hunts to the same peak the LUT is built from, and Fixed sits within 0.10V of $V_("mpp")$ across the full range (@fig:pv-vmpp), so all three settle close to the same operating point. At thermal equilibrium under the bench emulator there is no steady-state harvest advantage of P&O over LUT or Fixed.

#figure(
  image("images/mppt_test_transient_50pct.png", width: 100%),
  caption: [Mode-switch transient at 50% irradiance: commanded $V_("mpp")$ (solid), measured $v_("panel")$ (dotted), and resulting $P_("panel")$.],
) <fig:mppt-transient>

@fig:mppt-transient shows the mode-switch transient at 50% irradiance. Fixed and LUT hold their commanded $V_("mpp")$ flat at 5.15V and 5.10V, with $v_("panel")$ tracking inside the noise envelope. P&O shows the expected three-point hunting oscillation around the peak, walking $V_("mpp")$ up and down in a bounded cycle; the resulting panel power stays inside the same envelope as the other two modes, confirming the algorithm locks onto the peak rather than drifting.

At bench thermal equilibrium all three modes converge to the same peak, so P&O shows no steady-state advantage, but it does confirm the algorithm tracks correctly with its oscillation contained within the noise envelope. The real differentiator is temperature: as the panel warms under sustained illumination, $V_("mpp")$ drifts downward by several mV/°C. Fixed and LUT cannot follow this since both are open-loop, whereas P&O corrects automatically by optimising power directly. P&O is therefore the shipped default, with Fixed and LUT kept as fallbacks in case of a fault.


=== Measured SMPS Efficiency

PV conversion efficiency is defined as $eta_("PV") = P_("bus,out") / P_("panel,in")$, with $P_("panel,in") = V_("panel") dot I_("L")$ from firmware (both factors are Port B) and $P_("bus,out") = V_("bus") dot I_("bus,out")$ from a DMM in series with the PV-to-bus wire (Port A is uninstrumented). @fig:pv-eta-measured and the table below show the 48-point sweep: four irradiance settings (25%, 50%, 75%, 100%) at twelve bus-voltage points each, with the panel pinned at its MPP ($V_("panel") approx 5.15$ V, from @fig:pv-vmpp). The boost duty $D = 1 - V_("panel") / V_("bus")$ spans 0.28 to 0.59 across the sweep, staying inside the flat boost plateau.

#protable(
  caption: [Measured PV SMPS efficiency across bus voltage and irradiance.],
  columns: (1fr, 1fr, 1.1fr, 1.1fr, 1.1fr, 1.1fr),
  align: center + horizon,
  [*$V_("bus")$ (V)*], [*Duty $D$*], [*$eta_("PV")$ at 25%*], [*$eta_("PV")$ at 50%*], [*$eta_("PV")$ at 75%*], [*$eta_("PV")$ at 100%*],
  [7.11], [0.28], [96.56%], [96.69%], [97.17%], [97.68%],
  [7.61], [0.32], [96.36%], [96.79%], [96.82%], [97.89%],
  [8.11], [0.37], [96.62%], [96.57%], [96.98%], [97.74%],
  [8.61], [0.40], [96.52%], [96.44%], [96.73%], [98.00%],
  [9.12], [0.44], [96.16%], [96.63%], [96.79%], [97.86%],
  [9.61], [0.46], [96.69%], [96.34%], [97.11%], [98.10%],
  [10.21], [0.50], [96.56%], [96.80%], [97.15%], [98.02%],
  [10.63], [0.52], [96.57%], [96.68%], [97.28%], [97.79%],
  [11.07], [0.54], [96.18%], [96.75%], [96.90%], [98.10%],
  [11.63], [0.56], [96.37%], [96.51%], [96.92%], [98.08%],
  [12.06], [0.57], [96.32%], [96.88%], [96.98%], [97.83%],
  [12.55], [0.59], [96.66%], [96.84%], [96.81%], [97.77%],
)

#figure(
  image("images/pv_efficiency_measured.png", width: 100%),
  caption: [Measured PV SMPS efficiency versus bus voltage at four irradiances.],
) <fig:pv-eta-measured>

Two features stand out. First, each $eta_("PV")$ trace is flat with bus voltage. The four curves vary by no more than ±0.3% across their twelve points, with no monotonic trend against $V_("bus")$, matching the flat plateau of the boost $eta$-versus-$D$ characteristic over the $D = 0.28$ to $0.59$ range. Fig. 5 of @navamani_iccpct2015, reproduced in @fig:pv-eta-ref, shows this plateau across moderate duty cycles and a sharp CCM cliff beyond $D approx 0.7$. At the supercapacitor ceiling $V_("bus") = 17.5$V the reachable $D_("max") = 1 - 5.15 / 17.5 approx 0.71$ sits at the cliff threshold, so the supercapacitor-full corner is the one regime where degraded efficiency would be expected; elsewhere the plateau represents converter behaviour across its operating window.

Second, the per-irradiance means rise monotonically: 96.5% at 25%, 96.7% at 50%, 97.0% at 75% and 97.9% at 100%. The 1.4 percentage-point spread matches the boost loss model. Fixed gate-drive and switching overhead are independent of throughput, so they consume a larger fraction at low panel power: 100% irradiance gives about 2.3W out, 25% gives about 0.8W, and the same fixed overhead is a bigger share of the lower throughput. The irradiance-to-irradiance gap sits well above the per-point scatter, so the monotonic ordering is statistically clean rather than a noise artefact.

#figure(
  image("images/pv_efficiency.png", width: 78%),
  caption: [Boost efficiency versus duty cycle in DCM and CCM, from Fig. 5 of @navamani_iccpct2015.],
) <fig:pv-eta-ref>

PV conversion efficiency stays within 96 to 98% across all four irradiance levels, rising 1.4 percentage points from 25% to 100% irradiance with no meaningful dependence on bus voltage. Import efficiency does enter the score under the dual-meter framework of Section 2.3 and rises monotonically with $V_("bus")$ (Section 5.3.2), so the import lens marginally favours a higher bus voltage; the PV lens is neutral. The $V_("bus") = 10$V choice rests on hardware constraints (supercapacitor lower bound, PV panel open-circuit voltage, buck dropout), with both bus-relevant efficiency curves consistent with that pick.

#pagebreak()


// ----- 4. Supercapacitor SMPS (~1000 words) ------------------
= Supercapacitor SMPS

== Design & Simulation

=== Boost Topology and Boot-with-Empty-Capacitor Rationale

The supercapacitor is the only variable-voltage element on the storage side, ranging from 10.5V when depleted to 17.5V when full. The same Port A above Port B transfer rule that fixed the PV topology dictates the port assignment here (the shared power stage in @fig:smps-stage): the capacitor is the higher and variable rail and must sit on Port A, with the fixed 10V bus on Port B. Energy flows from bus to capacitor (B to A) when charging and from capacitor to bus (A to B) when discharging, so the module is a bidirectional SMPS.

The SMPS is set to BOOST mode, which is the load-bearing decision for robustness. In BOOST mode, the on-board circuitry draws from Port B, the bus, which is always energised by the grid and PV modules. The SMPS therefore boots and stays alive even when the capacitor is fully empty at 0V. The alternative BUCK setting would power the bus from Port A, the capacitor, and would trip the SMPS whenever the capacitor fell below the 6V to 7V minimum support voltage. The current sign convention follows the PV module: a positive inductor current means charging, a negative current means discharging, and the dashboard command $i_("cmd")$ is signed accordingly.

=== Operating Window 10.5 to 17.5 V

The usable voltage window is determined by two hard limits, illustrated in the stored-energy curve in @fig:supercap-energy. The ceiling $V_("cap,max") = 17.5$V is the SMPS port limit and sits under the 18V capacitor rating. The floor $V_("cap,min") = 10.5$V provides a 0.5V margin above the 10V bus to maintain $V_("A") > V_("B")$ under ESR-induced voltage drop and measurement noise. Within this window the capacitor stores energy as $E = 1/2 C V^2$ with $C = 0.5$F (two 0.25F capacitors in parallel).

#figure(
  image("images/supercap_energy_window.png", width: 88%),
  caption: [Supercapacitor stored energy and usable operating window.],
) <fig:supercap-energy>

In firmware the practical voltage ceiling is lowered to 15.7V, to reduce the impact of noise overshooting the voltage limit if 17.5V was used instead. The current is reset to 0 whenever the capacitor approaches within 0.5V of the upper and lower limits. The energy genuinely transferred between 10.5V and 15.7V is approximately 34J of the 49J the full window could hold. A significant complication is the capacitor's approximately 4 Ω equivalent series resistance (ESR): immediately after a current step the voltage ripple is dominated by the resistive drop and charge redistribution, so an accurate voltage can only be determined after some settling time. This directly shapes the cycle-test settle phases described in Section 4.2, which read the open-circuit voltage only after a deliberate pause. Peak current is clamped to 0.60A, leaving approximately 21% headroom under the 0.76A SMPS hardware limit @cd_dsm_datasheet.

=== Command-Driven CC: Rationale for the Departure

Unlike the grid and export modules, the supercapacitor is not involved in droop. The bus voltage is already regulated by the grid and export droop pair (Section 2.4). Instead the capacitor is a commanded current source and sink: it tracks a signed current given by input from the economic algorithm. This is the correct implementation for storage where it allows arbitrage: charging when energy is cheap and discharging when it is expensive, rather than reacting passively to instantaneous bus voltage.

The control law is an inner current PI only. The current limits implemented are a maximum or minimum at $plus.minus 0.60$ A, a linear taper to 0 near the voltage limits, and a bus-health taper that reduces charging demand when the bus voltage sags so the capacitor does not pull too much grid current.

== Testing & Optimisation

The supercapacitor evaluation answers two questions: what is the round-trip energy efficiency $eta_("RT")$, and how does it split into $eta_("charge")$ and $eta_("discharge")$? Both are answered from a single charge-and-discharge cycle, using the capacitor's known capacitance as an internal calibration reference. The same dataset supplies the efficiency figures the dispatch algorithm in Section 9 relies on.

=== Automated Cycle-Test Method

For a complete cycle from $V_("low")$ to $V_("high")$ and back, the firmware integrates bus-side input energy during charge,

$ E_("in") = integral V_("bus") dot I_("bus") d t $

and bus-side output energy during discharge,

$ E_("out") = integral V_("bus") dot |I_("bus")| d t $

The headline round-trip efficiency is therefore

$ eta_("RT") = E_("out") / E_("in") $

This metric is preferred because both $E_("in")$ and $E_("out")$ are measured at the bus, so the result does not depend on estimating capacitor-side current. The capacitor-side stored energy $E_("cap") = 1/2 C V_("cap")^2$ (with $C = 0.5$F, two 0.25F capacitors in parallel) is still recorded before charge, after charge, after any hold phase, and after discharge. It is useful for checking the expected energy swing, but it is not used as the main efficiency metric because the terminal voltage relaxes after current steps due to ESR and charge redistribution.

#figure(
  image("images/supercap_cycle_state_machine.png", width: 100%),
  caption: [Supercapacitor cycle-test state machine.],
) <fig:cap-state-machine>

As shown in @fig:cap-state-machine, the test is implemented as a firmware state machine triggered from the dashboard. It runs through precharge, settle 1, charge, settle 2, optional hold, discharge, settle 3 and done. Each settle phase records the open-circuit capacitor voltage only after a short delay, reducing the effect of the immediate ESR transient. Bus-side energy integration runs at the 1 kHz control tick, so the reported $eta_("RT")$ is not limited by the dashboard logging rate. The discharge endpoint is kept at $V_("low") = 10.5$V, matching the usable operating window. Any taper near the lower limit is therefore included in the measured round-trip result.

Although $eta_("charge")$ and $eta_("discharge")$ can be estimated from the capacitor-side energy readings, they are not reported as headline values. In practice, charge redistribution caused the discharge-side estimate to exceed 100% in some runs, which is physically impossible. The conclusion is that capacitor voltage is adequate for state-of-charge indication, but not for cleanly separating charge and discharge efficiency on this capacitor bank. The reliable metric carried forward is therefore the bus-side round-trip efficiency $eta_("RT")$.

=== Round-Trip Efficiency Results

Two no-hold sweeps were run, with each operating point repeated three times. The first varied charge and discharge current from 0.1A to 0.6A at a 10V bus. The second varied bus voltage from 8.0V to 10.0V at 0.2A. @fig:cap-cycle shows a representative 10V, 0.2A cycle: the capacitor charges from 10.5V to the 15.7V cutoff, then discharges back to 10.5V. The measured bus-side energies are $E_("in") = 38.2$ J and $E_("out") = 33.7$ J, giving $eta_("RT") approx 88%$. The capacitor-side energy swing is approximately 34J, matching the design estimate from the usable voltage window.

#figure(
  image("images/supercap_cycle_trace.png", width: 100%),
  caption: [Measured supercapacitor charge and discharge cycle at 10V, 0.2A.],
) <fig:cap-cycle>

The measured round-trip efficiency is stable across the tested range. In the current sweep, $eta_("RT")$ falls only slightly from 89.7% at 0.1A to 86.9% at 0.5A, with the 0.6A result recovering to 87.4% within run-to-run scatter. This weak downward trend is consistent with conduction loss increasing with current. In the bus-voltage sweep, efficiency varies even less, rising mildly from 87.3% at 8.0V to 88.3% at 10.0V. This is consistent with the smaller boost ratio when the bus voltage is closer to the capacitor voltage.

#figure(
  image("images/supercap_efficiency.png", width: 100%),
  caption: [Measured round-trip efficiency versus current and versus bus voltage.],
) <fig:cap-eff>

#protable(
  caption: [Supercapacitor round-trip efficiency by charge current at 10 V bus.],
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
  caption: [Supercapacitor round-trip efficiency by bus voltage at 0.2 A.],
  columns: (1fr, 1fr),
  align: (center + horizon, center + horizon),
  [*Bus voltage*], [*Mean $eta_("RT")$, 3 runs*],
  [8.0 V], [87.3%],
  [8.5 V], [87.7%],
  [9.0 V], [87.4%],
  [9.5 V], [88.8%],
  [10.0 V], [88.3%],
)

The headline result is therefore that the supercapacitor path achieves approximately 88% immediate round-trip efficiency across the intended operating range. This figure is higher than the conservative 70 to 85% pre-test estimate and is sufficiently stable to use in the system-level dispatch model.

=== Self-Discharge and Hold-Duration Dependence

The same cycle test was extended with a zero-current hold phase between charge and discharge. Hold durations of 60, 120, 180, 240 and 300 seconds were tested at 0.2A and a 10V bus, with three repeats per point. This isolates the effect of storing energy in the capacitor before using it.

#figure(
  image("images/supercap_hold_duration.png", width: 90%),
  caption: [Round-trip efficiency versus zero-current hold duration.],
) <fig:cap-hold-duration>

Round-trip efficiency falls sharply with hold time: from 88.3% with no hold to 77.5% after 60 seconds, and to 64.1% after 300 seconds. Because $eta_("RT") = E_("out") / E_("in")$ is measured entirely from bus-side energy, this drop is a real loss of recoverable energy rather than a capacitor-voltage measurement artefact.

#figure(
  image("images/supercap_hold_self_discharge.png", width: 100%),
  caption: [Open-circuit $V_("cap")$ drift after charge: master curve across 13 hold runs.],
) <fig:cap-hold>

Also as seen in @fig:cap-hold, after charging to the 15.7V cutoff, $V_("cap")$ falls quickly by about 0.5V over the first 50 seconds, then continues to decay more slowly at roughly 2 to 3 mV/s. The fast component is attributed to charge redistribution within the supercapacitor @jamieson_charge_redistribution_2021, while the slower component is consistent with leakage. Since all hold-duration runs collapse onto the same relaxation curve, the loss can be treated as a repeatable function of hold time.

The dispatch implication is direct: the supercapacitor should be charged just-in-time rather than charged early and held near peak voltage. Immediate cycling gives about 88% round-trip efficiency, but a few minutes of hold time can erase much of the storage benefit. The economic algorithm should therefore delay charging until the stored energy is actually needed, unless the alternative is curtailing otherwise unusable PV energy.

#pagebreak()


// ----- 5. Import & Export SMPS (~1000 words) -----------------
= Import & Export SMPS

== Design & Simulation

=== Topology Choice

Both grid-facing modules are configured as synchronous buck converters with the BU/BO switch set to BUCK (the shared power stage is @fig:smps-stage). The import module places the 12V bench PSU on Port A and the 10V bus on Port B, sourcing current into the bus. The export module places the 10V bus on Port A and a resistor bank on Port B, stepping the voltage down across the resistor to dissipate energy. Current cannot be pushed into the PSU or bank, so the minimum reference current for both SMPS is 0. This satisfies the Port A above Port B rule.

The duty cycle is inverted for these SMPS compared to the PV and supercapacitor boost SMPS due to the inversion of the gate driver. Current sensing is performed by the INA219 driver across the 0.1 Ω Port B shunt. The choice of a dummy resistor is in accordance with the project brief: using a resistor sized to sink the maximum export current instead of driving current into a bench PSU, which would collapse the terminal voltage.

The maximum export power is the sum of maximum PV power and capacitor power. The demo-day configuration of two parallel PV panels supplies a maximum of roughly 8W at the panel side, and the capacitor supplies a maximum of about 13W at peak 0.6A discharging current near the top of its window, making the maximum export power under 20W. Given that the buck SMPS has 10V at the input and the output voltage must be below that, the load bank needs a current of $P / V = 20 / 10 = 2$ A and a resistance of $V / I = 10 / 2 = 5$ Ω. The dummy load is therefore a 5 Ω bank and the inductor-current reference is capped at 2 A, the point at which the 10V and 2A limits coincide at the 20W corner, and which sits under the module's 2.8A firmware overcurrent trip.

=== Droop Setpoints: 9.9 V Import and 10.1 V Export

Each module runs a cascaded controller: an outer bus-voltage PI produces a reference current and an inner current PI produces a PWM which changes the voltage (@fig:cascaded-control). The two modules differ only in the sign of the voltage error. The import module computes $v_("err") = V_("target") - V_("bus")$, so it sources more current the further the bus falls below its 9.9V setpoint. The export module computes $v_("err") = V_("bus") - V_("target")$, the sign flipped, so it dissipates more the further the bus rises above its 10.1V setpoint. Each reference current is limited to 2A on both modules (approximately 20W at the bus), the export value set by the worst-case surplus analysis in Section 5.1.1 and the import value by the grid interface rating.

#figure(
  image("images/cascaded_control_block.png", width: 100%),
  caption: [Cascaded control structure shared by Import and Export SMPS modules.],
) <fig:cascaded-control>

The dead-band that the symmetric setpoints create is analysed in Section 2.4. For implementation, a setpoint of 0.1V or below, or a disable command, is treated as fully off, which is how the bus changes from entirely import to entirely export.

== Testing & Implementation

Both bus-facing modules received the same three-layer noise reduction as the PV module (Section 3.2), applied through the shared `INA219` class so import and export pick it up in one edit. Three-second block averages of $P_("import")$ and $P_("dissipated")$ are computed inside firmware with reset triggers on $V_("target")$, $I_("max")$ and enable state; the block-averaged values are exposed in each module's telemetry dictionary but their persistence to the backend SQLite store and surfacing on the dashboard are pending wiring work, so the bench characterisation in Sections 5.3.1 and 5.3.2 reads the steady-state powers from the live filtered telemetry rather than the unwired block-average field.

 

=== Anti-Windup and Soft-Start Grace

The outer voltage PI on each module uses clamping anti-windup with a tightly bounded integrator. Left at the default integrator bound the term could wind up much larger than the value that saturates the current reference, taking several seconds to unwind once the bus returns to target. This was observed as the rail voltage fluctuating between 8V and 12V at about 1Hz when the PV and export SMPS ran together without the grid SMPS. We therefore bound the integrator to the range that just saturates the output.

A soft-start grace prevents the undervolt trip. When the system starts up with just the grid module, the bus voltage begins near 0V, which would cause an undervolt trip immediately. The undervolt trip is disabled for a 500ms grace period on every transition from inactive to active (on enable, watchdog clear and trip reset) while overvolt and overcurrent trips stay enabled. The export module carries the same grace logic, but its output current is clamped to 0 when the bus voltage is below target.

== Evaluation & Optimisation

The Export and Import SMPS share a buck topology and a bench characterisation methodology but play opposite roles in the dual-meter scoring framework of Section 2.3. Export sits between the bus and the dummy resistor: the lecturer's bus meter credits the pre-loss bus value while the dashboard reports the post-loss dissipation, so the dispatch algorithm under-reports export revenue by the conversion loss and operates on slightly off-optimum numbers (Section 6.3.2 covers the same effect on the LED path; the proper fix in both cases is a current sensor between the bus and the SMPS). Maximising $eta_("export")$ is the available mitigation. Import is the inverse: the PSU reading is the billed quantity, so every 1% of conversion loss inflates the effective import price per delivered bus Wh directly. The two sweeps are presented in that order.

=== Measured Export Efficiency

The export SMPS efficiency is $eta_("export") = P_("dissipated") / P_("bus,drawn")$. The numerator $P_("dissipated")$ is the firmware's post-loss field, measured at the dummy resistor by the Port B INA219. The denominator $P_("bus,drawn")$ is not natively instrumented, so a bench DMM is placed in series with the bus-to-export wire and $V_("bus")$ is read off the dashboard. At each operating point the three-second-averaged $P_("dissipated")$ is recorded against $V_("bus") dot I_("DMM")$ and the ratio taken.

// TODO(export-sweep): fill in once measurements complete.
// Suggested grid: V_bus at 9.0, 9.5, 10.0, 10.5, 11.0 V; I_L at 0.1, 0.2, 0.3 A.
// Mirror the import table format below.

#protable(
  caption: [Measured Export SMPS efficiency by bus voltage and load current.],
  columns: (1fr, 1fr, 1.2fr, 1.2fr, 1.2fr),
  align: center + horizon,
  [*$V_("bus")$ (V)*], [*Duty $D$*], [*$eta$ at 0.1 A*], [*$eta$ at 0.2 A*], [*$eta$ at 0.3 A*],
  [9.0],  [ ], [ ], [ ], [ ],
  [9.5],  [ ], [ ], [ ], [ ],
  [10.0], [ ], [ ], [ ], [ ],
  [10.5], [ ], [ ], [ ], [ ],
  [11.0], [ ], [ ], [ ], [ ],
)

// TODO(export-sweep): replace placeholder image once images/export_efficiency.png exists.
// #figure(
//   image("images/export_efficiency.png", width: 100%),
//   caption: [Measured Export SMPS efficiency versus bus voltage at three load currents.],
// ) <fig:export-eta>

// TODO(export-sweep): one short paragraph summarising the result.
// Expected shape: nominal-bus efficiency at 10 V around [TBD]%; trend with V_bus
// and I_L follows the same buck loss model as the import sweep below. Headline
// number to extract is η at the bus dead-band and at the expected operating
// current, since that determines the dashboard-vs-bus-meter gap during demo.

=== Measured Import Efficiency

The import SMPS efficiency is $eta_("import") = P_("bus,delivered") / P_("PSU,drawn")$. The pre-loss draw $P_("PSU,drawn") = V_("PSU") dot I_("PSU")$ is not measured on the import module because the shunt sits on Port B. Unlike the PV case in Section 3.3, $I_("PSU")$ can be read from the bench PSU's built-in current display with manufacturer-stated accuracy (the same display the lecturer reads on demo day).

Section 2.3 established that any watt lost in the import path is a watt of grid energy missing from the bus, hurting the economic score. Import efficiency therefore gets more attention. The bus-voltage axis is swept across nine points from 7V to 11V in roughly 0.5V steps, wider than the 9.9V to 10.1V dead-band so duty-cycle dependence is captured across the full operating range. Currents of 0.1, 0.2 and 0.3A are used. At each of the 27 operating points the three-second-averaged $P_("bus,delivered")$ is recorded against $V_("PSU") dot I_("PSU")$ and the ratio taken.

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

At the nominal $V_("bus") = 10$V the converter delivers 83.8%, 89.9% and 92.5% at 0.1, 0.2 and 0.3A. Both trends (monotonic rise with $V_("bus")$ as duty approaches unity, and monotonic rise with $I_L$ as fixed switching overheads amortise over more delivered power) match the buck loss model of Section 2.3 and confirm the converter is operating away from dropout. In cost terms, the 89.9% at the nominal 10V and 0.2A operating point inflates the effective import price by $1 / 0.899 approx 1.11$, an 11% premium absorbed by conversion loss that the dispatch algorithm of Section 9 sees directly through its PSU-referenced cost formula.

#pagebreak()


// ----- 6. LED Load SMPS (~900 words) -------------------------
= LED Load SMPS

== Design & Simulation

=== Topology

The LED load is a triple driver assembly: three independent buck channels (red, yellow, blue), each a cut-down SMPS driving a 3W, 1A LED, all under one Pico W. Buck is the natural choice because the 3V LED forward voltage is well below the 10V bus. The hardware differs from the bidirectional modules in two ways the firmware must respect. Current is sensed by an external SPI ADC (MCP3208 family) reading three current channels and three voltage channels through one chip select, with a 0.33 Ω shunt rather than 0.10 Ω, so the inductor current is $i_("L") = 3 dot V_("shunt")$. Each channel has a dedicated enable pin that must be driven high on every tick; the gate driver gates the PWM off whenever its enable is low. The LED forward voltage is reconstructed from the two ADC reads as $v_("LED") = 2 dot v_("v,pin") - v_("i,pin")$, correcting for the sense divider and shunt drop. One of the three identical channels is shown in @fig:led-driver.

#figure(
  image("images/LED_driver.png", width: 92%),
  caption: [LED buck driver power stage, one of three identical channels @clemow_led.],
) <fig:led-driver>

=== Control Mode: CC vs Commanded Power

An LED behaves as a fixed-voltage device, so its power is set by controlling current. The web server hands the system a power figure, so each channel runs commanded-power mode through constant current: power is divided by measured forward voltage to give a current reference $i_("ref") = P_("demand") / v_("LED")$, which a per-channel current PI tracks. The reference is clamped to channel ratings of 3.0W and 1.05A, and a forward-voltage floor guards the division when a string is dark. When demanded power is zero the enable pin is dropped and the PI is reset to stop the integrator winding up while the channel is off.

== Testing & Implementation

The example driver firmware was reworked to drop its external PID dependency in favour of the same inline PI used across the bidirectional modules, giving one consistent controller idiom throughout the project. The per-channel gains and duty saturation range differ from the bidirectional modules to suit the 0.33 Ω shunt and the driver's own PWM limits. Safety is per-LED: if any channel's current exceeds 1.4 times its rated maximum the firmware latches a trip and records which colour tripped, so a faulty LED is diagnosable from telemetry instead of showing up as a generic fault.

Two bring-up aids proved useful. A boot-time diagnostic samples every SPI ADC channel several times before any PWM is commanded, so spurious overcurrent readings caused by floating ADC inputs, a wrong port assignment or insufficient bus voltage can be told apart from a real LED overcurrent by inspecting the printed channel values. On shutdown the per-channel enable lines drop first, gating the PWM off at the driver before the commanded duty is zeroed, so the LEDs extinguish without residual current. A shared 10-second watchdog hook exists for forcing all channels off if commands stop arriving but is currently held inactive (Section 8.3); the operator-driven recovery path is the dashboard Stop action, which broadcasts zero per-LED power through the command proxy.

== Evaluation & Optimisation

Two axes are reported: per-channel power-following accuracy (which verifies Requirement 1) and the reason conversion efficiency is not separately characterised.

=== Power-Following Accuracy

A 60-second scripted test exercises each channel individually and then together, with commanded and measured per-channel powers logged from the dashboard at 20 Hz. @fig:led-tracking overlays the two: the faint trace is commanded power, the dark trace is measured power delivered to the LED string. The sequence is red at 2W for 6s, off, yellow at 2W for 6s, off, blue at 2W for 6s, off, all three together at 1, 2 and 3W for 10s, off, and a 15-second simultaneous ramp from 0 to 3W.

#figure(
  image("images/led_power_tracking.png", width: 100%),
  caption: [Per-channel commanded and measured LED power across the 60-second tracking sequence.],
) <fig:led-tracking>

Each channel tracks within about ±3% across all operating points, with the residual driven by per-string forward-voltage variation that the $i_("ref") = P_("demand") / v_("LED")$ division (Section 6.1.2) cannot compensate when $v_("LED")$ is itself estimated through the SPI ADC chain. Step settling on each on/off transition resolves inside one 50 ms dashboard sample. The all-on and ramp phases confirm channels do not interact through the shared bus or SPI ADC, so a multi-colour demand is served additively.

=== Bus-Side Measurement Gap

The LED Load conversion path sits between the bus meter and the LED string, in the same topological position as Export. The lecturer's bus meter registers $P_("LED,bus") = P_("LED,channel") + P_("losses")$ as load, while firmware reports only the per-channel post-loss values $p_("red")$, $p_("yel")$, $p_("blu")$ measured at the LED string. The dispatch algorithm therefore reads an LED demand under-reported by exactly the LED Load buck conversion loss, and the same effect applies on Export where the post-loss dissipation under-reports the bus-credited revenue (Section 5.3). The buck loss could in principle be attributed to either side of the converter, but with no instrumentation between the bus and the SMPS we cannot measure where it actually lands. Maximising $eta_("LED")$ is the available lever: at $eta_("LED") = 1$ the post-loss value would equal the bus value and dispatch decisions would align exactly with the lecturer's reading; at realistic efficiencies the algorithm runs on slightly optimistic numbers and PnL is marginally worse than a perfectly-informed policy would achieve. The clean fix is a dedicated INA219 between the bus and the SMPS, feeding the true bus-side current to the dashboard so dispatch operates on the lecturer's view of the load; this was identified but not implemented within the project window.

#pagebreak()


// ----- 7. Telemetry Filtering (~700 words) -------------------
= Telemetry Filtering

Noise on the power telemetry was bad, obscuring the operating-point comparisons Sections 3.3, 4.3 and 5.3 depend on. Typical oscillation on $P_("panel")$ was several hundred milliwatts peak-to-peak against a steady-state mean of a few watts, with similar relative magnitudes on the other modules. The fix is a three-layer attenuation applied identically across the PV, supercapacitor, import and export modules.

== Hardware Averaging

The bidirectional template inherits an INA219 CONFIG register of 0x199F (12-bit, single-sample, 532 μs conversion @ti_ina219), which lets most of the switching ripple through unaveraged on the current-sense shunt. Reprogramming to 0x1E67 (16-sample averaging, 8.51 ms conversion) across all four modules clears this, in which the longer conversion time is still over twenty times faster than the slowest downstream consumer — the supercapacitor's 200 ms OCV window (Section 4.2), so no process is kept waiting. PV and supercapacitor pick this up through identical edits to their inline `ina_init` functions, and import and export through a single edit to the shared `INA219` class.

Voltage channels are read by the Pico's onboard 12-bit ADC through a resistive divider and walk several LSBs sample-to-sample regardless of INA219 settings. Each `read_va` and `read_vb` call performs four single reads and right-shifts the sum by two to take the mean:

$ V_("oversampled") = (V[0] + V[1] + V[2] + V[3]) / 4 $

Cost per call is about 10 μs, well inside the 1 ms control tick budget. Peak-to-peak jitter falls by roughly 1.6×, with diminishing returns past four samples.

== Exponential Moving Average

A first-order EMA is applied in software on top of the hardware-averaged readings:

$ V_("filt")[n] = (1 - alpha) dot V_("filt")[n-1] + alpha dot V[n] $

with $alpha = 0.05$ at the 1 kHz sample rate, giving a time constant $tau approx 20$ ms and a corner frequency near 8 Hz. The filtered signals drive the dashboard display, the three-second block averages, the P&O power comparison (Section 3.2) and the cycle-test energy integrators (Section 4.2). $alpha = 0.05$ is bounded both ways: too small (longer $tau$) and the filter adds phase lag that slows displayed transients on dashboard reads; too large (shorter $tau$) and it passes switching-ripple aliasing through. 20 ms gives about 60 ms to 95% step settling, which fits inside the 150 ms second-half averaging window of the P&O dwell and the 200 ms tail of the cycle-test settle phases. @fig:ema-response shows the response: a corner frequency near 8 Hz that rejects aliased ripple, with a step settling inside 60 ms so the displayed transient is barely delayed.

#figure(
  image("images/ema_filter_response.png", width: 100%),
  caption: [Telemetry EMA magnitude and step response at alpha = 0.05.],
) <fig:ema-response>

The inner PI loops and safety guards bypass the software EMA and block-average outputs, mainly for two reasons. First, adding 20 ms of phase lag to a current PI tuned against unfiltered inputs would shift its stability margin and force a retune. Second, the trip thresholds (panel undervolt, bus overvolt, overcurrent) were designed for instantaneous response; a filtered safety guard would react 20 ms late, allowing more energy into a fault before tripping. Keeping the filter on the display and characterisation paths only preserves control-loop behaviour and trip response while still giving the operator clean numbers. Note that the current readings still include the INA219's internal conversion averaging, but no additional software filtering is inserted into the control path.

== Three-Second Block Average

Each module computes a true block average of its bus-side power over a three-second window in firmware:

$ P_("avg3s") = (1 / N) sum_(i=1)^(N) P[i] $

with $N = 3000$ at 1 kHz. The window restarts on changes to the commanded operating point (MPPT mode for PV, $I_("cmd")$ for supercapacitor, $V_("target")$ and $I_("max")$ for import and export), so each completed average reflects one operating point. Float-rounding the operating-point tuple before comparison avoids spurious resets from JSON-parser dust. The computed average lives in each module's telemetry dictionary; persistence into the backend SQLite store and rendering on the operator dashboard are scheduled wiring work, so the side-by-side comparisons in Sections 3.3 and 5.3 read the filtered live telemetry directly. Inside the supercapacitor cycle test the block average sits on top of phase changes as a real-time sanity check that the commanded current has settled.

== Evaluation

The three-layer treatment is evaluated by the noise reduction it delivers on the per-module bus-side power telemetry. @fig:noise-raw-filt overlays a raw single-sample trace against the same operating point after the three-layer filter, shifted to a 2W PV operating point for visual context.

#figure(
  image("images/noise_raw_vs_filtered.png", width: 100%),
  caption: [Bus-side power telemetry: raw single-sample versus three-layer filtered.],
) <fig:noise-raw-filt>

Raw $P_("panel")$ oscillation falls from about 300 mW peak-to-peak at the 1 kHz tick to under 10 mW per P&O dwell-averaged comparison (Section 3.2), roughly a 30× reduction. Equivalent attenuation on the supercapacitor, import and export modules brings the three-second-averaged readings inside a few milliwatts, fine enough to resolve the 1.4 percentage-point irradiance-to-irradiance spread in the PV efficiency sweep (Section 3.3) and the 1 to 2 percentage-point steps between adjacent supercapacitor charge currents in the round-trip sweep (Section 4.2).

#pagebreak()


// ----- 8. Software System (~1000 words) -----------------------
= Software System

The software system provides the communication, control and monitoring infrastructure for the smart-grid platform. It links the Azure simulation server, backend services, embedded modules and operator dashboard into a unified system.

== Architecture

The lowest tier consists of the firmware running on each Pico-controlled module. Every module hosts a lightweight HTTP server on the Pico's second core, exposing a JSON command endpoint for remote control. Keeping the networking stack on core 1 isolates it from the 1 kHz control loop running on core 0, preventing network activity from introducing jitter into the timing-critical control and safety logic. The same networking thread also pushes a telemetry snapshot to the backend once per second.

The middle tier is a Python FastAPI backend backed by a SQLite database. It stores grid snapshots, telemetry records and algorithm outputs, and acts as the communication bridge between the frontend and the embedded modules. A standalone poller retrieves simulation data from the Azure server and records one deduplicated snapshot per simulation tick.

The top tier is a React single-page application built with Vite. The frontend provides monitoring, visualisation and operator controls through a browser interface.

#figure(
image("images/sw_stack_architecture.png", width: 100%),
caption: [Software stack showing telemetry flowing upward to FastAPI and control commands flowing downward through the same backend.],
) <fig:sw-stack>

 The overall architecture is summarised in @fig:sw-stack. Telemetry is pushed from the Pico modules to the backend, while both operator commands and EMS-generated commands are routed through the backend before being forwarded to the corresponding module.

== Backend and Control Layer

The backend acts as the central coordination layer for the system. In addition to storing telemetry and simulation data, it hosts the Energy Management System (EMS), which evaluates the latest grid state together with module telemetry and generates control setpoints for the supercapacitor, load emulator and grid interfaces.

A standalone poller checks the Azure simulation endpoints once per second. When a new `(day, tick)` pair is detected, the corresponding irradiance, pricing and deferrable-load information is retrieved and stored as a single grid-state snapshot. This provides a persistent historical record that can be replayed and analysed independently of the external simulation server.

Multiple algorithms can be registered and selected at runtime through the dashboard, enabling direct comparison between baseline and improved control strategies without requiring firmware changes. Algorithm decisions are logged alongside telemetry and grid-state snapshots, allowing the behaviour of different control policies to be reconstructed and evaluated offline.

The backend also provides run-management facilities, including automatic EMS execution, CSV export of recorded data and a run-scoped profit-and-loss calculation based on imported and exported energy. Together, these features support both real-time operation and post-experiment analysis.

#figure(
image("images/sw_stack_architecture.png", width: 100%),
caption: [EMS CONTROL FLOW],
) <fig:ems-control-flow>

Azure Tick
      ↓
Grid State
      ↓
Load Latest Telemetry
      ↓
Selected Algorithm
      ↓
Generate Setpoints
      ↓
Command Dispatcher
      ↓
Pico Modules

== Frontend Dashboard

#figure(
image("images/sw_stack_architecture.png", width: 100%),
caption: [HOW TO PRESENT DASHBOARD?],
) <fig:dashboard>

Three operator views are provided. The default *My Energy* dashboard presents a high-level overview of the microgrid, including current demand, solar irradiance, energy prices, active deferrable loads and module health indicators. Historical demand and irradiance data are displayed as charts, while a status panel highlights whether each module is online, stale, tripped, disabled or in a watchdog state.

The *SMPS Overview* page focuses on system-level monitoring. Historical telemetry from the PV, grid, export, supercapacitor and LED modules is visualised using time-series plots of voltages, currents and power flows. This view is intended for observing overall energy movement through the system and diagnosing interactions between subsystems.

The *SMPS Modules* page provides detailed engineering controls. Each module is represented by a dedicated card showing live telemetry, recent history and module-specific controls. Operators can configure MPPT modes on the PV converter, adjust bus-voltage targets for grid and export modules, command supercapacitor charge or discharge currents, set LED load power levels and reset protection trips. The same interface also provides algorithm selection, automatic EMS execution controls, run-scoped profit-and-loss summaries and data export tools for post-run analysis.

== Design Trade-offs

Several implementation choices were revised during integration to improve timing reliability. The first version of the Azure poller attempted to fetch the full grid state at a fixed five-second interval. In practice, a complete cycle of `/demand`, `/sun`, `/price` and `/deferables` requests could take longer than the Azure update period, causing occasional missed ticks. The final design instead checks only `/demand` once per second and treats `(day, tick)` as the change detector. The remaining endpoints are fetched only when a new tick is observed, and are requested in parallel. This keeps tick-detection latency below one second while avoiding unnecessary repeated requests to the slower auxiliary endpoints.

Telemetry collection was changed for a similar reason. Early versions used backend polling to retrieve telemetry from each module. In practice, modules may be temporarily offline during startup, reconfiguration or network interruptions, causing polling requests to block until timeout. Achieving higher telemetry update rates would therefore require either aggressive polling, increasing network traffic, or accepting delays caused by repeated timeout handling. The final implementation uses push-based telemetry: each module sends its latest snapshot to the backend once per second whenever it is online. This makes new measurements available immediately after acquisition, avoids backend resources being tied up waiting for unresponsive modules, and scales more efficiently as the number of modules increases. The trade-off is that telemetry collection now depends on each module maintaining its own network connection and upload loop.

Control commands were kept backend-mediated rather than being sent directly from the frontend to the Pico modules. This allows the EMS algorithm to run headlessly on the backend and issue commands without requiring the dashboard to remain open. It also provides a single control interface for both automated EMS actions and manual operator commands. Centralising command dispatch in the backend ensures that all control actions are logged alongside telemetry and grid-state data, enabling consistent run replay, debugging and post-experiment analysis. In addition, module addressing and communication logic are implemented in one location rather than being duplicated across multiple frontend views or external clients.


== On-Module Fallback Dashboard [R WE MENTIONING THIS AS /TLM IS REMOVED]

As a final redundancy, a single-file dashboard is bundled into the firmware filesystem and served by the module's own HTTP server at its root path. This gives a usable monitoring and control surface with no backend, database or Node toolchain, useful during bench bring-up and as a fallback if the main stack is unavailable on demo day.

#pagebreak()


// ----- 9. Algorithm Software (~1000 words) -------------------
= Algorithm Software

The per-module loops of Sections 3 to 6 keep the bus stable; this section covers the coordinator that decides what each module should be doing. Two policies share the same framework: a reactive naive baseline that the brief asks the smart policy to beat, and a forecast-aware Smart V1 that schedules deferrable loads into cheap ticks and arbitrages the supercapacitor against the evening price spike. Both are evaluated on the same grid under the same scripted day, and the smart policy delivers a 20% net-cost saving averaged across two lab runs.

== Coordinator Loop and Economic Objective

The coordinator is a background thread inside the FastAPI backend, woken whenever the poller commits a new Azure tick (with a 5-second fallback timer in case a wake-up is missed). On each pass it reads the latest grid snapshot and the latest PV and supercapacitor telemetry from the database, evaluates the active algorithm's `decide(state)` function, and dispatches the resulting commands to the four actuators (LED Load, supercapacitor, grid, export) in that fixed order. The loop deduplicates against the Azure tick so the same tick is never applied twice, skips any tick where the grid snapshot is older than 15 seconds, and refuses to dispatch to a module currently latched in a trip. Because each module's inner loop holds the last commanded setpoint autonomously, a coordinator stall cannot destabilise the bus: droop, PI control and per-module clamps run independently at 1 kHz.

The objective is to minimise the net cost of grid energy over a daily Azure cycle while always meeting demand. Under the dual-meter framework of Section 2.3, import is debited at the PSU reading and export credited at the bus reading, so the per-day cost is

$ C = sum_t (P_("PSU")(t) dot p_("sell")(t) - P_("export,bus")(t) dot p_("buy")(t)) dot Delta t $

with $P_("PSU")(t) = P_("import,bus")(t) / eta_("import")(V_("bus"), I_L)$ coupling the import draw to the efficiency map of Section 5.3.2. Prices follow the grid's perspective: $p_("sell")$ is what the utility charges us on imports, $p_("buy")$ what it credits us on exports, with $p_("buy") approx 0.5 dot p_("sell")$ at every tick. That spread is the headline arbitrage opportunity. The coordinator's levers are deferrable scheduling, supercapacitor charge or discharge, and net import or export, subject to instantaneous demand being met, each deferrable receiving its full energy inside its window, and the supercapacitor and grid modules staying inside their hardware envelopes.

== Algorithm Framework

Each policy exposes a pure `decide(state: GridState) -> Commands` function and is registered with an in-process registry; the operator switches the active policy at runtime from the dashboard and the choice is persisted to disk. `GridState` carries the Azure tick, base demand, PV panel power, bus voltage from the supercapacitor module, supercapacitor terminal voltage, the live current-tick prices and the full deferrable list. `Commands` carries the four actuator payloads plus a diagnostics block (regime, PV derate, effective load, net imbalance, supercapacitor headroom, per-deferrable rates) that the dashboard renders for whichever policy is active. Adding a policy is a register call plus one module.

One detail makes the live path produce the right answer: the Azure feed republishes each deferrable's full original energy at every tick of its window, so a policy that treats `d.energy` as remaining joules would re-allocate the same load over and over. A small served-tracker module accumulates the bus-side energy actually dispatched per deferrable, credits only after a successful LED command (a dropped command does not bank served energy), and subtracts the running total from `d.energy` before the policy sees it. Without the tracker the LED was over-driven by 233 J on a 615 J target, a 38% over-dissipation; with it, the commanded LED energy lands within 7 J of target on both naive runs and within 41 J on the smart runs, where the residual falls out as export (the LED clamp at 9 W spills surplus into the bus).

== Naive Baseline

The naive policy is a five-step reactive symmetric-droop rule. PV is first derated to bus side by a conservative $eta_("PV") = 0.90$ (the measured value in Section 3.3 is 96 to 98%, so the bias keeps the algorithm on the surplus side of modelling error). Active deferrables are then spread linearly across their remaining real-time window so the per-tick rate is $E_("remaining")/(5 dot N_("ticks remaining"))$ watts, with adaptive catch-up baked in: under-serving last tick raises the next tick's rate. Effective load is base demand plus the sum of those rates and is commanded to the LED Load, split three ways across red, yellow and blue channels with each firmware-clamped to 3 W. The net imbalance $P_("net") = P_("PV,bus") - P_("load,eff")$ is then offered to the supercapacitor through a 1 W deadband (noise floor of the bus), with charge current $P_("net")/V_("bus")$ clamped to 0.6 A and refused above 15.7 V, discharge current $|P_("net")|/(V_("bus") dot eta_("cap"))$ refused below 10.5 V and linearly tapered through the 10.5 to 11 V firmware soft region. Anything the supercapacitor cannot absorb spills to droop: the grid and export modules sit permanently enabled at 9.9 V and 10.1 V respectively and passively make up the residual.

@fig:algo_naive_trace shows the naive policy across one Azure day on the grid. The cap power panel is small and twitchy, charging only when noise pushes the bus above the deadband; the grid panel does almost all of the work, importing through the morning, evening and night and exporting only the small midday surplus that the cap could not absorb.

#figure(
  image("images/algo_naive_trace.png", width: 88%),
  caption: [Naive baseline: per-tick dispatch over one Azure day (V4 test 1).],
) <fig:algo_naive_trace>

== Smart V1: Forecast-Aware Scheduling and Arbitrage

Smart V1 keeps every safety guard of the naive policy (LED clamp, supercapacitor taper, 0.6 A clamp, deadband, discharge-side $eta_("cap")$ compensation) and replaces two of its reactive steps with forecast-aware ones. The forecast itself is closed-form: the Azure simulation has a deterministic mean (sun follows a sine over ticks 15 to 45, base demand follows a piecewise-linear envelope, sell price = max(10, 10 + base $-$ sun)), with Gaussian noise on top. Smart V1 evaluates that mean per tick rather than fitting historical data.

The first replacement is the deferrable scheduler. Instead of smearing each deferrable across its window, future ticks are ranked by marginal cost-to-serve: a tick in forecast PV surplus costs $p_("buy")$ (the foregone export revenue), a tick in deficit costs $p_("sell")$ (the imported energy). The scheduler greedy-fills the cheapest ticks first, respecting the LED's 9 W per-tick capacity and giving the tightest-deadline deferrable first pick. The second replacement is the supercapacitor dispatcher. At every tick it compares the current sell price against the best leakage-discounted future sell price across the rest of the day, using a piecewise leakage model fitted to Section 4.2.3 (a 12% dielectric step over the first minute, then 0.25% per Azure tick). It emits one of six actions: end-of-day drain past tick 55, arbitrage discharge when now beats the best future by more than 20 ¢/J, arbitrage charge when forecast yield clears charging cost by the same margin, an empty-cap refill rule that lowers the import bar when a forecast peak is within eight ticks, and a fall-back passive rule that mirrors the naive deadband when no arbitrage triggers fire. Two pre-peak guards (refuse passive discharge below 70 ¢/J after tick 42, and a fixed price floor instead of forecast comparison) were added after a lab trace showed the supercapacitor being drained at moderate prices and arriving empty at the real evening peak.

@fig:algo_smart_trace shows the smart policy on the same day. The supercapacitor panel now has a large midday charge burst (ticks 24 to 32, where PV surplus and cheap prices coincide) and an evening discharge burst (ticks 45 to 50, where the sell price clears 100 ¢/J). The grid panel imports most of its energy in the cheap morning and exports the midday surplus that exceeds the LED clamp.

#figure(
  image("images/algo_smart_trace.png", width: 88%),
  caption: [Smart V1: per-tick dispatch over the same Azure day (V4 test 1).],
) <fig:algo_smart_trace>

== Evaluation

Each policy was run on the grid against the same fixed price, demand and irradiance profile (514 J base demand, 100.6 J of deferrables, 615 J LED target). Net cost integrates the grid module's `p_import` and the export module's `p_dissip` trapezoidally over every consecutive sample pair, multiplied by the sell or buy price in effect at the earlier timestamp; sample gaps longer than 30 s are skipped. The same integrator drives the `/algo/run/cost` endpoint the dashboard renders during a run, so the numbers in @tbl:algo_cost are directly comparable to a live P&L card.

#protable(
  caption: [V4 lab cost summary (cents). Smart V1 saves 20% on average.],
  columns: (1.5fr, 1fr, 1fr, 1fr, 1fr),
  align: (left + horizon, center + horizon, center + horizon, center + horizon, center + horizon),
  [*Run*], [*Import (¢)*], [*Export (¢)*], [*Net (¢)*], [*Saving vs naive*],
  [Naive, test 1], [34,789], [70],  [34,719], [baseline],
  [Naive, test 2], [33,493], [63],  [33,430], [baseline],
  [Smart, test 1], [27,863], [450], [27,413], [21.0%],
  [Smart, test 2], [27,447], [384], [27,064], [19.0%],
) <tbl:algo_cost>

@fig:algo_price_band attributes the saving to where each policy spent its import allowance. Smart V1 imports roughly 3.6 times as much energy in the cheapest band (below 30 ¢/J) and correspondingly less in the 30 to 100 ¢/J middle bands, which is where the naive policy is forced to draw whenever the bus sags. Total imported energy is almost the same across both policies (476 J for smart versus 463 J for naive, averaged across the two paired tests): the saving comes from when the energy is bought, not how much. The supercapacitor cycles about 2.2 times as hard under smart (120 J charged, 98 J discharged on average, versus 54 J and 49 J under naive) and the grid exports about five times as much (36 J versus 7 J on average), the export being PV surplus that exceeds the 9 W LED clamp on peak midday ticks while the supercapacitor is also fully charging. The dominant lever is therefore price arbitrage on the supercapacitor: cheap-band imports park energy in the cap, which is then discharged later to displace what would otherwise be 70 to 100 ¢/J imports.

#figure(
  image("images/algo_price_band.png", width: 92%),
  caption: [Imported energy by sell-price band: smart shifts imports into the cheap band.],
) <fig:algo_price_band>

== Auxiliary Power Overhead

#figure(
  image("images/usb_power_tester.png", width: 55%),
  caption: [USB inline meter: a single Pico W draws 0.262 W on its 5 V rail.],
) <fig:usb_power_tester>

The five Pico W controllers run from a separate USB powered hub, unmetered by the algorithm. A USB inline meter reads 0.262 W per module (@fig:usb_power_tester), so the aggregate fixed draw is 1.31 W or 393 J per 300 s Azure day. Total energy throughput across the grid (PV panel-side, supercapacitor charge and discharge, grid import and export, LED dissipation) averaged 1724 J per day, or 5.75 W. The controllers therefore account for $1.31 / (1.31 + 5.75) approx 19%$ of total grid power. However, we note that this is a fixed cost: with a small-scale grid it is highly inefficient, but with a larger supercapacitor, higher demand, it can improve the efficiency.

#pagebreak()


// ----- 10. Mechanical Design (~400 words) -------------------
= Mechanical Design

== 3D-Modelled SMPS Enclosure

The four bidirectional SMPS boards sit in a 3D-printed chassis that protects the exposed power electronics from accidental shorts and keeps the assembly stable enough to move and demo without disturbing the wiring.

The v1 print (@fig:smps-stand, left) had solid side walls and a solid base. It was mechanically fine but trapped heat: with no intake from the sides or below, the lower boards had no convection path.

The v2 revision (@fig:smps-stand, right) added vertical slots in the side walls and vents in the base, so cool air enters from below and rises through to the open top. 3 mm standoff ribs on the inside walls hold each board off the wall so air flows between them.

#figure(
  grid(
    columns: (1fr, 1fr),
    column-gutter: 10pt,
    image("images/smps_stand_before.png", width: 100%),
    image("images/smps_stand_after.png", width: 100%),
  ),
  caption: [SMPS stand iteration: v1 (left) and v2 (right)],
) <fig:smps-stand>

#pagebreak()


// ----- 11. Extra Test & Requirement Verification (~700 words) -
= Extra Test & Requirement Verification

== Communication & Integration Tests
// ---------- Smart V1 latency bar chart helper ----------

#let bar-chart(data, max-val: 1000) = {
  let chart-width = 280pt
  let label-width = 115pt
  let value-width = 45pt
  let bar-height = 13pt
  let gap = 8pt

  stack(
    dir: ttb,
    spacing: gap,
    ..data.map(item => {
      let name = item.at(0)
      let value = item.at(1)
      let width = chart-width * value / max-val

      grid(
        columns: (label-width, chart-width, value-width),
        column-gutter: 8pt,
        align: (right, left, left),

        [#text(size: 8pt)[#name]],

        [
          #rect(
            width: width,
            height: bar-height,
            fill: rgb("#4f6f8f"),
            radius: 2pt,
          )
        ],

        [#text(size: 8pt)[#value ms]],
      )
    })
  )
}


// ---------- Figure: median latency breakdown ----------

#figure(
  align(center)[
    #bar-chart((
      ("State acquisition", 471),
      ("Smart V1 decision", 2),
      ("Command dispatch RTT", 307),
      ("Pico control adoption", 4),
      ("Telemetry confirmation", 942),
    ))
  ],
  caption: [Median Smart V1 latency breakdown across the 20-point dataset.]
)


// ---------- Table: latency summary ----------

#figure(
  table(
    columns: (1.8fr, 1fr),
    inset: 6pt,
    align: (left, right),
    stroke: 0.5pt,
    fill: (x, y) => if y == 0 { rgb("#4f6f8f") } else { none },

    [*Metric*], [*Value*],
    [Dataset size], [20 traces],
    [Mean end-to-end latency], [1450 ms],
    [Median end-to-end latency], [1417 ms],
    [Minimum end-to-end latency], [597 ms],
    [Maximum end-to-end latency], [2797 ms],
    [95th percentile end-to-end latency], [2271 ms],
    [Median Azure HTTP fetch latency], [348 ms],
    [Median state acquisition latency], [471 ms],
    [Median Smart V1 decision latency], [2.1 ms],
    [Median command dispatch RTT], [307 ms],
    [Median Pico control adoption latency], [4.0 ms],
    [Median telemetry confirmation latency], [942 ms],
    [Median total latency including Azure fetch], [1759 ms],
  ),
  caption: [Summary statistics for Smart V1 end-to-end latency across the 20-point dataset.]
)


// ---------- Report text ----------

A set of latency data was captured using an autonomous script during Smart V1 operation. After removing incomplete or invalid traces, a 20-point dataset remained for analysis. Each trace was associated with a unique trace identifier, allowing the same control event to be tracked from Azure tick acquisition, through Smart V1 decision generation and command dispatch, to Pico control-loop adoption and telemetry confirmation.

Across the 20 traces, the median end-to-end latency from backend detection of a new Azure tick to telemetry confirmation was 1417 ms, with a mean of 1450 ms. The minimum and maximum measured end-to-end latencies were 597 ms and 2797 ms respectively, while the 95th percentile was 2271 ms. Including the initial Azure HTTP fetch stage, the median total latency was 1759 ms.

The latency breakdown shows that Smart V1 computation and embedded control adoption were not significant contributors to the total delay. The median Smart V1 decision time was 2.1 ms, and the Pico control loop adopted the received command in 4.0 ms. In contrast, state acquisition, command dispatch and telemetry confirmation required median latencies of 471 ms, 307 ms and 942 ms respectively.

This indicates that the remaining delay in the system was dominated by communication and telemetry handling rather than algorithm execution or low-level embedded control response. The test therefore confirms that the full Azure-to-backend-to-SMPS command path operated successfully under autonomous Smart V1 control, while also identifying the communication path as the main target for future optimisation.

== Requirements Verification

Each of the brief's six requirements is mapped below to the subsystem that realises it, the test that verifies it, and its current status. Requirement 5 (the economic dispatch algorithm) is the main item still in progress (Section 9); the rest are implemented and verified by the tests in the cited sections.

#protable(
  caption: [Brief requirements: verification method and current status.],
  columns: (0.5fr, 2fr, 1.4fr, 1.5fr, 1.4fr),
  align: (center + horizon, left + horizon, left + horizon, left + horizon, left + horizon),
  [*Req*], [*Requirement*], [*Realised by*], [*Verification*], [*Status*],
  [1], [Supply domestic LEDs per web demand], [LED Load SMPS (Section 6)], [Power-tracking test (Section 6.3)], [Implemented; tracking within ±3% across channels],
  [2], [Extract PV energy with MPPT], [PV SMPS (Section 3)], [MPPT mode comparison; efficiency sweep], [Implemented; P&O shipped as default with Fixed and LUT fallbacks],
  [3], [Store excess in supercapacitor, no batteries], [Supercapacitor SMPS (Section 4)], [Cycle test; round-trip efficiency], [Implemented],
  [4], [Import and export to grid, metered], [Import/Export SMPS (Section 5)], [Import efficiency sweep; export efficiency sweep; bus dead-band], [Implemented; export sweep scheduled],
  [5], [Minimise cost; schedule storage and deferrables; beat naive], [Algorithm (Section 9)], [Dry run versus naive baseline], [In progress],
  [6], [UI for current and historic energy data], [User Interface (Section 8)], [Live dashboard; telemetry plots], [Implemented],
)

// ============================================================
//  References
// ============================================================
#pagebreak()
#bibliography("references.bib", title: "References", style: "ieee")