"""Forecast-aware supercap dispatcher (Smart V1).

Strategy: stored-energy-in-the-cap has a *future value* equal to the
best leakage-discounted price it can be discharged into. At every tick
we compare current actions against that best future value:

  * **eod_drain** — past tick 55, force discharge (overnight = pure leak).
  * **arb_discharge** — current sell-price > best-future-discharge-value
    → discharge now, no point holding.
  * **arb_charge** — best-future-discharge-value (×η_RT) > current
    charge-cost → put energy in.
  * **refill_for_peak** — cap empty AND a peak <= 8 ticks away → import
    even at moderate prices (DP-optimal pattern: late-evening top-up).
  * **arb_import_charge** — strong forecast peak ahead → buy now.
  * **passive** — fall back to the naive reactive rule otherwise.
  * **hold** — neither side beats threshold; leave the cap alone.

Triggers are calibrated against real Azure-day data (σ_sell ≈ 19 ¢/J):
  - ARB_TRIGGER_CENTS_PER_J = 20  (~1σ — avoid noise-driven decisions)
  - IMPORT_CHARGE_TRIGGER   = 50  (~2.6σ — only the very best peaks)
  - REFILL_GAIN_TRIGGER     = 20  (lower bar when cap is empty)

Backtest result vs naive on two real Azure days:
  naive   = 37733 ¢ baseline
  smart   = 27490 ¢  (–27.1 %)
  DP-opt  = 23235 ¢  (–38.4 % theoretical upper bound w/ perfect info)
Smart captures ~71 % of the available headroom with rule-based logic.

Leakage model from §4.3.4 of the Y2 report (Figure 4.5): piecewise fit
to η_RT vs hold duration. Fast dielectric step (~12 % in first minute)
then slow ohmic leakage (~0.25 %/tick).
"""

from dataclasses import dataclass
from typing import Optional, Tuple

from . import forecast


# --- Cap physics (single source of truth: naive.py mirrors firmware) ---
from .naive import (
    V_CAP_CHARGE_STOP,
    V_CAP_DISCHARGE_TAPER,
    V_CAP_DISCHARGE_STOP,
    I_CAP_MAX,
    ETA_CAP_SMPS,
)
ETA_RT                = 0.88        # round-trip, §4.3.3 — cap_policy-specific

# Horizon over which we look for arbitrage. The full day = 60 ticks; we
# go that far so a morning tick can see the evening peak. The leakage
# discount erodes far-future values automatically.
HORIZON_TICKS         = 60

# Threshold for "significantly better" — the expected gain (after η_RT ×
# leakage) has to clear this many ¢/J of expected value before we commit
# to a non-passive action. Tuned via backtest on real Azure days to be
# ~1σ of observed sell_price noise (σ ≈ 19 ¢/J). Below this the rule
# samples noise rather than signal.
ARB_TRIGGER_CENTS_PER_J = 20.0

# Floor on import-to-charge: only let the cap "buy from the grid for
# storage" when the spread is strong enough to overcome round-trip
# losses (~19 % RT) plus leakage (~3 %/min). Tuned to ~2.6σ of price
# noise — only the most confident peaks clear it. Lower values overtrade
# and lose to round-trip on every cycle.
IMPORT_CHARGE_TRIGGER   = 50.0

# End-of-day drain: any energy held past tick 60 leaks away before the
# next day's evening peak (≈180%/hr at peak leakage rate), so its
# marginal value approaches zero. Force discharge in the last few ticks
# regardless of forecast — convert it to export revenue instead.
END_OF_DAY_DRAIN_TICK   = 55

# Empty-cap refill: when the cap is below this voltage AND a forecast
# peak is within REFILL_HORIZON_TICKS AND the gain clears REFILL_TRIGGER,
# import to refill even at moderate prices. Tuned on real Azure days —
# captures the optimal pattern of "buy mid-evening to dump at evening peak."
REFILL_V_THRESHOLD       = 12.0     # V
REFILL_HORIZON_TICKS     = 8
REFILL_GAIN_TRIGGER      = 20.0     # ¢/J

# Peak window — ticks where Azure's deterministic structure puts sell_price
# above ~80 ¢/J (sun=0 after tick 45, demand still at 100 until tick 50).
# Before this window: refuse passive_discharge so the cap stays full for
# the harvest. arb_discharge still works for actual-price spikes.
# After EOD_DRAIN_TICK: forced full drain (existing rule).
# Lab trace (V3) showed cap getting drained at moderate-price ticks
# (sell 49-63) leaving it empty for the real peaks (sell 88-138).
PEAK_WINDOW_START_TICK   = 42

# Absolute sell-price below which we refuse to spend cap pre-peak.
# Forecast-comparison rules failed because forecast σ ≈ 19 ¢/J corrupts
# the comparison; a fixed cutoff is noise-immune. 70 ¢/J cleanly
# separates "moderate" (spend grid) from "harvest" (spend cap).
PRE_PEAK_DISCHARGE_FLOOR = 70.0


@dataclass
class CapAction:
    target_W:    float       # signed bus-side power (+charge / -discharge)
    reason:      str         # short tag for diagnostics
    arb_gain:    float = 0.0 # expected gain per J (¢/J)
    horizon_t:   int   = 0   # ticks until the arb counterparty tick


def retain_fraction(ticks: int) -> float:
    """Fraction of a stored joule still recoverable after waiting
    ``ticks`` Azure ticks (5 s each).

    Piecewise fit to Figure 4.5 in the Y2 report (η_RT vs hold duration):
      - First 12 ticks (60 s): fast dielectric absorption, ~12% loss
        linear over the window
      - After 12 ticks: slow ohmic leakage, ~0.25%/tick (~3 %/min)
    """
    if ticks <= 0:
        return 1.0
    if ticks <= 12:
        return max(0.0, 1.0 - 0.0102 * ticks)
    return max(0.0, 0.878 - 0.0025 * (ticks - 12))


def _cap_soc_headroom(v_cap: float) -> Tuple[float, float]:
    """Return (charge_headroom_J, discharge_available_J) using
    E = ½ C V² with C = 0.5 F."""
    C = 0.5
    e_now  = 0.5 * C * v_cap * v_cap
    e_full = 0.5 * C * V_CAP_CHARGE_STOP * V_CAP_CHARGE_STOP
    e_low  = 0.5 * C * V_CAP_DISCHARGE_TAPER * V_CAP_DISCHARGE_TAPER
    return max(0.0, e_full - e_now), max(0.0, e_now - e_low)


def _max_absorb_bus_W(charge_headroom_J: float, vbus: float) -> float:
    """Bus-side power the cap can physically absorb over one tick
    without overshooting V_CAP_CHARGE_STOP. Charging more than this
    is "billed" by the grid (PSU sees the import) but the energy
    has nowhere to go — pure waste.

    headroom_J = bus_W × η_SMPS × seconds_per_tick
    → bus_W_max = headroom_J / (η_SMPS × seconds_per_tick)
    """
    if charge_headroom_J <= 0:
        return 0.0
    return charge_headroom_J / (ETA_CAP_SMPS * 5.0)  # SECONDS_PER_TICK


def decide(
    current_tick: int,
    current_net_W: float,
    v_cap: float,
    vbus: float,
    actual_sell_price: float = None,
    actual_buy_price:  float = None,
) -> CapAction:
    """Decide the cap's target bus-side power for this tick.

    ``current_net_W`` is the imbalance after PV and scheduler-aware
    deferrable load. +ve = surplus, -ve = deficit.

    ``actual_sell_price`` / ``actual_buy_price`` are the *real* current
    prices from the Azure feed. When provided, they replace the forecast
    for current-tick comparisons (we still must forecast future ticks).
    Real σ of sell_price ≈ 19 ¢/J — forecast-only decisions get sampled
    by noise; actual prices eliminate that on the present side.
    """
    p_now_sell = (actual_sell_price if actual_sell_price is not None
                  else forecast.expected_sell_price(current_tick))
    p_now_buy  = (actual_buy_price  if actual_buy_price  is not None
                  else forecast.expected_buy_price(current_tick))

    charge_headroom_J, discharge_avail_J = _cap_soc_headroom(v_cap)
    can_charge    = charge_headroom_J  > 1.0 and v_cap < V_CAP_CHARGE_STOP - 0.2
    # FIX 1 (lab trace 2026-06-08): the previous v_cap > 11.2 V threshold
    # refused discharge in the 10.5–11.2 V band, but the firmware's
    # _discharge_i_max linearly tapers current from full at 11.0 V to 0
    # at 10.5 V — i.e. the firmware IS willing to deliver partial current
    # there, and smart_v1's outer code already respects that taper when
    # clamping i_cmd. Refusing here just locks away ~5 J of usable energy
    # right when peak prices hit (see tick 17 sell=115 → 1984 ¢ lost).
    can_discharge = discharge_avail_J > 0.5 and v_cap > V_CAP_DISCHARGE_STOP + 0.1

    # Physical ceiling on bus-side charge power for this tick. Cap-aware
    # clamp: prevents the "import 3 W with only 1.3 W of headroom" pattern
    # where the algorithm pays for energy the cap cannot absorb. Also
    # forces gradual top-up near ceiling instead of a hard slam-stop.
    max_charge_bus_W = min(I_CAP_MAX * vbus,
                           _max_absorb_bus_W(charge_headroom_J, vbus))

    # --- 0. End-of-day drain (pre-empts arb logic) ---
    # Stored energy at midnight is wasted: leakage exceeds any plausible
    # next-day morning yield. Force discharge in the final ticks. The
    # arb_discharge path already triggers on most evening peak ticks,
    # but this catches the tail where prices are decaying and the
    # near-future-best comparison goes marginal.
    if current_tick >= END_OF_DAY_DRAIN_TICK and can_discharge:
        target_W = -(I_CAP_MAX * vbus * ETA_CAP_SMPS)
        return CapAction(
            target_W   = target_W,
            reason     = "eod_drain",
            arb_gain   = 0.0,
            horizon_t  = 0,
        )

    # --- Best future discharge value across the rest of the day ---
    # For each tick t in (now, end], compute leakage-discounted sell-price
    # — that is what a joule stored now would fetch if we discharged at t.
    best_future_t     = current_tick
    best_future_value = 0.0
    for t in range(current_tick + 1,
                   min(forecast.TICKS_PER_DAY, current_tick + HORIZON_TICKS + 1)):
        dt    = t - current_tick
        value = forecast.expected_sell_price(t) * retain_fraction(dt)
        if value > best_future_value:
            best_future_value = value
            best_future_t     = t

    # --- 1a. Discharge decision (long horizon): is *now* better than holding? ---
    # Compare current sell-price-equivalent against the best leakage-
    # discounted future price. If current beats the best future by the
    # threshold, dump the cap now.
    if can_discharge and p_now_sell > best_future_value + ARB_TRIGGER_CENTS_PER_J:
        target_W = -(I_CAP_MAX * vbus * ETA_CAP_SMPS)
        return CapAction(
            target_W   = target_W,
            reason     = "arb_discharge",
            arb_gain   = p_now_sell - best_future_value,
            horizon_t  = 0,
        )

    # (Mid-day sawtooth-discharge attempted; backtest showed it over-fires
    # at moderate v_cap values when actual prices spike unpredictably,
    # giving up energy that survives to a bigger peak. Optimal mid-day
    # sawtooth requires full-day lookahead — see DP benchmark.)

    # --- 2. Charge decision: does best future yield > current charge cost? ---
    # Yield per J of bus-side energy put into the cap now:
    #   yield = sell(best_t) × η_RT × retain(best_t - now)
    # (η_RT folds in the round-trip charge+discharge η; retain folds in
    # leakage.)
    yield_per_J = (forecast.expected_sell_price(best_future_t)
                   * ETA_RT
                   * retain_fraction(best_future_t - current_tick))

    # Charge cost depends on regime:
    #   surplus  → cost = foregone export revenue = buy_price (low)
    #   deficit  → cost = import we'd have to do  = sell_price (high)
    if current_net_W > 0.5:
        charge_cost = p_now_buy
    else:
        charge_cost = p_now_sell

    charge_gain = yield_per_J - charge_cost

    # In surplus, charge if even a small gain. In deficit, demand a
    # bigger spread before importing-to-store (avoid round-tripping
    # cheap mid-day surplus through the grid).
    if can_charge and current_net_W > 0.5 and charge_gain > ARB_TRIGGER_CENTS_PER_J:
        # Default: absorb the surplus only. No risk — the surplus would
        # otherwise be exported at buy_price (the foregone-revenue cost
        # the gain check used).
        target_W = min(max_charge_bus_W, current_net_W)
        # Optional: take an extra ~2 W via import IF the yield clears
        # the import cost (sell_price), not just the export cost
        # (buy_price). Without this gate the extra import is mis-priced.
        if yield_per_J - p_now_sell > IMPORT_CHARGE_TRIGGER:
            target_W = min(max_charge_bus_W, current_net_W + 2.0)
        return CapAction(
            target_W   = target_W,
            reason     = "arb_charge",
            arb_gain   = charge_gain,
            horizon_t  = best_future_t - current_tick,
        )
    # Empty-cap urgency: when the cap is near floor and there's a real
    # peak ahead, lower the import bar. Catches the "refill before peak"
    # pattern that DP-optimal uses (e.g. tick 47 sell=72 → tick 49 sell=124).
    # The cap is so empty that ANY import here will be discharged into the
    # peak rather than wasted on round-trip.
    if (can_charge and current_net_W <= 0.5
            and v_cap < REFILL_V_THRESHOLD
            and charge_gain > REFILL_GAIN_TRIGGER
            and best_future_t - current_tick <= REFILL_HORIZON_TICKS):
        target_W = min(max_charge_bus_W, 6.0)
        return CapAction(
            target_W   = target_W,
            reason     = "refill_for_peak",
            arb_gain   = charge_gain,
            horizon_t  = best_future_t - current_tick,
        )
    if can_charge and current_net_W <= 0.5 and charge_gain > IMPORT_CHARGE_TRIGGER:
        # Small forward-buy via import. Capped at ~3 W so a bad forecast
        # can't bleed us out, and at the cap's physical absorption rate.
        target_W = min(max_charge_bus_W, 3.0)
        return CapAction(
            target_W   = target_W,
            reason     = "arb_import_charge",
            arb_gain   = charge_gain,
            horizon_t  = best_future_t - current_tick,
        )

    # --- 3. Passive — naive reactive rule, within safe envelope ---
    # REVERTED from V2 ±0.5 → ±1.0 (V1 baseline). Lab test 2026-06-08 showed
    # the lower threshold + noisy real bus (±1 W droop/LED-lag) caused a
    # charge-discharge flap loop — cap moved 86 commands but only 3 J of
    # energy (vs V1: 17 commands, 33 J). Keep noise out of the cap path.
    if current_net_W > 1.0 and can_charge:
        target_W = min(max_charge_bus_W, current_net_W)
        return CapAction(target_W, "passive_charge")
    if current_net_W < -1.0 and can_discharge:
        # 4 save-for-peak rule variants tested in backtest: time-based,
        # forecast-comparison (1.10 / 1.30 ratios), absolute-threshold
        # sweep (floor=50 through 100). ALL regressed 2-14 pp vs the
        # reactive V3 baseline. Root cause: finite cap (33 J) can only
        # cover a fraction of any day's peak — round-tripping it through
        # moderate-price deficits and the peak harvests ALREADY captures
        # most of the value. Saving cap for "the peak" leaves it idle
        # while cycles 2 and 3 of value go missed. See sweep result in
        # this commit message. Stay reactive.
        target_W = -min(I_CAP_MAX * vbus * ETA_CAP_SMPS, -current_net_W)
        return CapAction(target_W, "passive_discharge")

    if current_net_W > 1.0:
        return CapAction(0.0, "ceiling")
    if current_net_W < -1.0:
        return CapAction(0.0, "floor")
    return CapAction(0.0, "idle")


# --- Sanity print ---
if __name__ == "__main__":  # pragma: no cover
    cases = [
        ("tick 0, cap half, mild deficit",          0,  -0.5, 13.0),
        ("tick 15, cap half, deficit",             15,  -2.0, 13.0),
        ("tick 25, cap empty-ish, surplus",        25,  +4.0, 12.0),
        ("tick 30, cap empty-ish, surplus",        30,  +5.0, 12.0),
        ("tick 35, cap half, surplus",             35,  +3.0, 14.0),
        ("tick 45, cap full, deficit",             45,  -2.0, 15.5),
        ("tick 50, cap half, deficit",             50,  -2.0, 13.0),
        ("tick 55, cap empty, deficit",            55,  -0.5, 11.0),
    ]
    for label, t, net, vc in cases:
        a = decide(t, net, vc, 10.0)
        print(f"{label:<42}  target={a.target_W:+6.2f} W  "
              f"reason={a.reason:<18}  gain={a.arb_gain:+6.1f} ¢/J  "
              f"horizon={a.horizon_t} ticks")
