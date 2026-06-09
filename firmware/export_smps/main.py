# export_smps.py — Export buck SMPS, bus voltage regulator in dissipate direction.
#
# Hardware: Bidirectional Buck/Boost SMPS Module. Set BU/BO switch to BUCK.
#   Port A = bus (10 V nominal), Port B = dummy resistor bank.
#
# Control:
#   Outer loop: voltage PI on the bus, but with the error sign FLIPPED relative
#   to the grid module. Pushes more dissipation when bus is ABOVE target.
#     v_err = v_bus - vb_target
#     i_ref = PI_v(v_err), clamped to [0, I_REF_HI]
#   Inner loop: current PI servoing iL → pwm_out.
#
# Symmetric-droop role: vb_target = 10.1 V (higher than grid's 9.9 V).
# Export sinks only when the bus overshoots, idles in the 9.9–10.1 deadband.
#
# Telemetry:  { role, vb_bus, v_resistor, iL, p_dissip, p_avg3s,
#               i_ref, pwm, trip, vb_target, i_ref_max, enable, wd, grace }
# Commands:   { enable, vb_target, i_ref_max }
#     i_ref_max acts as a max-dissipation cap, useful if your resistor or
#     scheduler imposes one. Default 1.0 A (~10 W).
#
# Noise treatment (matches pv_smps / cap_smps / grid_smps):
#   - INA219 default config in common.py bumped to 16-sample averaging.
#   - 4x ADC oversample on va, vb reads.
#   - EMA on va, vb, iL drives the telemetry. Inner PI + safety still
#     use raw values for fast response.
#   - p_dissip = vb_lp * iL_lp; this is the resistor-side dissipated
#     power (post-SMPS-loss) since both vb and iL are port-B quantities.
#   - p_avg3s = 3-second block average; window restarts on (vb_target,
#     i_ref_max, enable) change so steady-state numbers are clean.

import time
from machine import Pin, ADC, I2C, PWM, Timer
from common import (PI, INA219, saturate, wifi_connect, start_http_thread,
                    watchdog_tripped, PWM_FREQ_HZ, PWM_MIN, PWM_MAX,
                    VB_HI_TRIP, VB_LO_TRIP, I_TRIP_ABS, TICK_HZ)

# ---------------- Hardware ----------------

va_pin  = ADC(Pin(28))   # Port A = bus
vb_pin  = ADC(Pin(26))   # Port B = dummy resistor
pwm     = PWM(Pin(9))
pwm.freq(PWM_FREQ_HZ)
ina_i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=2_400_000)

def read_va():
    # 4x oversample -- kills Pico ADC LSB noise (the dominant noise floor
    # on the displayed bus / resistor voltages). ~10 us overhead per call.
    s = va_pin.read_u16() + va_pin.read_u16() + va_pin.read_u16() + va_pin.read_u16()
    return (12490 / 2490) * 3.3 * ((s >> 2) / 65536)

def read_vb():
    s = vb_pin.read_u16() + vb_pin.read_u16() + vb_pin.read_u16() + vb_pin.read_u16()
    return (12490 / 2490) * 3.3 * ((s >> 2) / 65536)

# ---------------- Tuning ----------------

VB_TARGET_DEFAULT = 10.2   # bring-up: wide 1 V deadband with grid at 9.5
                           # narrow to 9.9/10.1 once the loops are tuned and noise is bounded
KP_V, KI_V = 0.5, 5.0
KP_I, KI_I = 100, 300
I_REF_HI   = 2.0          # max dissipation cap. 5 ohm load at ~10 V bus -> 2 A, 20 W.
                          # Sized to worst-case export surplus (PV + supercap peak);
                          # sits under the 2.8 A I_TRIP_ABS. Derives pi_v.out_hi / i_hi below.

# ---------------- State ----------------

state = {
    'cmd':  {'enable': 1, 'vb_target': VB_TARGET_DEFAULT, 'i_ref_max': I_REF_HI},
    'tlm':  {},
    'last_cmd_ms': time.ticks_ms(),
    'last_cmd_received_ms': 0,
    'push_tlm_now': False,
}

timer_elapsed = 0
def tick(_t):
    global timer_elapsed
    timer_elapsed = 1

# ---------------- Boot ----------------

print("Export SMPS booting...")
ina = INA219(ina_i2c)
wlan = wifi_connect("export")
print("Local IPv4:", wlan.ifconfig()[0] if wlan.isconnected() else "NOT CONNECTED")
start_http_thread(state)

# Tight integrator bounds == clamping anti-windup. Without them, the default
# PI class lets integ run to ±10000, which at KI_V=5 is 50000x past the value
# (I_REF_HI/KI_V) that already saturates the output. That extra wind-up takes
# many seconds to unwind, producing low-frequency limit cycling on the bus
# (visible as bus voltage swinging ~8–12 V at ~1 Hz when PV and export run
# alone without grid). Bounding integ to [0, I_REF_HI/KI_V] means it can wind
# up just enough to saturate, and unwinds in O(error) time.
pi_v = PI(KP_V, KI_V, out_lo=0.0, out_hi=I_REF_HI,
          i_lo=0.0, i_hi=I_REF_HI / KI_V)
pi_i = PI(KP_I, KI_I, out_lo=float(PWM_MIN), out_hi=float(PWM_MAX),
          i_lo=float(PWM_MIN) / KI_I, i_hi=float(PWM_MAX) / KI_I)

trip_latched = 0
trip_reason  = ''
i_ref   = 0.0
pwm_out = PWM_MIN

# Display power filter -- feeds telemetry only. Inner PI + safety guards
# below this still consume the raw single-sample va / vb / iL.
EMA_ALPHA = 0.05
va_lp = 0.0
vb_lp = 0.0
iL_lp = 0.0
p_lp  = 0.0

# 3-second block average of p_dissip. Window restarts on operating-point
# change so each completed average reflects a single (vb_target, i_max,
# enable) configuration -- the dashboard number you read at steady state.
P_AVG_WINDOW_MS = 3000
pavg_sum   = 0.0
pavg_n     = 0
pavg_start = 0
p_avg3s    = 0.0
prev_op    = None
active_trace_id = None
active_trace_tick = None
active_trace_received_ms = 0
active_trace_applied_ms = 0
last_trace_published = None

loop_timer = Timer(mode=Timer.PERIODIC, freq=TICK_HZ, callback=tick)
cnt = 0

# Soft-start grace: during bring-up the bus may sit at ~0 V before the grid
# module energises it, which would latch an undervolt trip on tick 0. Mask the
# undervolt trip for STARTUP_GRACE_TICKS whenever the controller transitions
# from inactive to active (enable rises, watchdog clears, or trip is reset).
# Over-volt and over-current stay armed throughout. (Export only sinks, so the
# grace just lets us wait for another source to lift the bus — pi_v output
# clamps to 0 while va < target anyway.)
STARTUP_GRACE_TICKS = 500     # 500 ms at TICK_HZ = 1000
startup_grace = 0
prev_active   = False

# ---------------- Main loop ----------------

try:
    while True:
        if timer_elapsed:
            timer_elapsed = 0

            va = read_va()      # bus
            vb = read_vb()      # resistor side
            iL = ina.iL()       # current into resistor (positive = dissipating)

            # EMA filter for telemetry only. Kick filters with first sample
            # to skip the boot-time ramp from 0 to true value.
            if va_lp == 0.0:
                va_lp = va
                vb_lp = vb
                iL_lp = iL
            else:
                va_lp = (1.0 - EMA_ALPHA) * va_lp + EMA_ALPHA * va
                vb_lp = (1.0 - EMA_ALPHA) * vb_lp + EMA_ALPHA * vb
                iL_lp = (1.0 - EMA_ALPHA) * iL_lp + EMA_ALPHA * iL
            p_lp = vb_lp * iL_lp

            cmd     = state['cmd']
            trace_id = cmd.get('_trace_id')
            if trace_id is not None and trace_id != active_trace_id:
                active_trace_id = trace_id
                active_trace_tick = cmd.get('_trace_tick')
                active_trace_received_ms = state.get('last_cmd_received_ms', 0)
                active_trace_applied_ms = time.ticks_ms()
            target  = cmd.get('vb_target', VB_TARGET_DEFAULT)
            i_max   = min(I_REF_HI, max(0.0, cmd.get('i_ref_max', I_REF_HI)))
            wd      = watchdog_tripped(state, time.ticks_ms())
            # vb_target <= 0.1 V means "off" — scheduler hands the bus to grid.
            enabled = bool(cmd.get('enable', 0)) and target > 0.1

            # 3-second block average of p_dissip. Restart on any change to
            # the commanded operating point so steady-state numbers compare
            # cleanly across sweeps.
            now_ms_pavg = time.ticks_ms()
            op_point = (round(target, 2), round(i_max, 3), 1 if enabled else 0)
            if op_point != prev_op:
                pavg_sum   = 0.0
                pavg_n     = 0
                pavg_start = now_ms_pavg
                prev_op    = op_point
            pavg_sum += p_lp
            pavg_n   += 1
            if time.ticks_diff(now_ms_pavg, pavg_start) >= P_AVG_WINDOW_MS:
                p_avg3s    = pavg_sum / pavg_n
                pavg_sum   = 0.0
                pavg_n     = 0
                pavg_start = now_ms_pavg

            # Trip reset from dashboard (one-shot). Re-latches next tick if the
            # fault persists, unless the grace window masks it.
            if cmd.get('reset_trip', 0):
                cmd['reset_trip'] = 0
                trip_latched = 0
                trip_reason  = ''

            # Rising edge of "controller will run this tick" → arm grace window.
            # Catches enable 0→1, wd clear, and trip reset all in one check.
            active = enabled and not trip_latched and not wd
            if active and not prev_active:
                startup_grace = STARTUP_GRACE_TICKS
            prev_active = active

            uv_armed = active and startup_grace <= 0
            if va > VB_HI_TRIP or (uv_armed and va < VB_LO_TRIP) or abs(iL) > I_TRIP_ABS:
                if not trip_latched:
                    if va > VB_HI_TRIP:                trip_reason = 'bus_overvolt'
                    elif uv_armed and va < VB_LO_TRIP: trip_reason = 'bus_undervolt'
                    else:                              trip_reason = 'overcurrent'
                trip_latched = 1

            if startup_grace > 0:
                startup_grace -= 1

            if (not enabled) or trip_latched or wd:
                i_ref   = 0.0
                pi_v.reset()
                pi_i.reset()
                pwm_out = PWM_MIN
            else:
                pi_v.hi   = i_max
                pi_v.i_hi = i_max / KI_V    # keep anti-windup limit in sync
                # SIGN FLIPPED vs grid: act when bus is HIGH, not low.
                v_err   = va - target
                i_ref   = pi_v.step(v_err)
                i_err   = i_ref - iL
                pwm_out = int(pi_i.step(i_err))

            duty = 65536 - pwm_out
            pwm.duty_u16(duty)

            state['tlm'] = {
                'role':       'export',
                'vb_bus':     va_lp,
                'v_resistor': vb_lp,
                'iL':         iL_lp,
                'p_dissip':   p_lp,
                'p_avg3s':    p_avg3s,
                'i_ref':      i_ref,
                'pwm':        pwm_out,
                'trip':       trip_latched,
                'trip_reason': trip_reason,
                'vb_target':  target,
                'i_ref_max':  i_max,
                'enable':     1 if enabled else 0,
                'wd':         1 if wd else 0,
                'grace':      startup_grace,
                'trace_id':    active_trace_id,
                'trace_tick':  active_trace_tick,
                'fw_cmd_received_ms': active_trace_received_ms,
                'fw_cmd_applied_ms': active_trace_applied_ms,
                'fw_cmd_to_apply_ms': time.ticks_diff(
                    active_trace_applied_ms, active_trace_received_ms
                ) if active_trace_received_ms else None,
            }
            if (
                active_trace_id is not None
                and active_trace_id != last_trace_published
            ):
                last_trace_published = active_trace_id
                state['push_tlm_now'] = True

            cnt += 1
            if cnt >= 500:
                print("[exp] vbus=%.2f vres=%.2f iL=%+.3f P=%+.2fW P_3s=%+.2fW iref=%.3f pwm=%d tgt=%.2f trip=%d wd=%d grace=%d" %
                      (va_lp, vb_lp, iL_lp, p_lp, p_avg3s, i_ref, pwm_out, target,
                       trip_latched, 1 if wd else 0, startup_grace))
                cnt = 0
except KeyboardInterrupt:
    print("\n[exp] interrupted — entering safe state...")
finally:
    try: loop_timer.deinit()
    except Exception: pass
    try: pwm.duty_u16(65535)        # hardware inverts → MOSFET fully off
    except Exception: pass
    state['shutdown'] = True
    time.sleep_ms(700)
    print("[exp] safe. PWM gated off, timer stopped, HTTP server stopped.")
