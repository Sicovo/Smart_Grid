"""PV light intensity actuator.

Commands:
    POST /cmd {"intensity": 0..100}
    POST /cmd {"position": 0..4095}  # direct positioning for calibration

Set SERVO_POS_AT_0_PCT and SERVO_POS_AT_100_PCT after measuring the two
usable ends of the PSU knob. Swapping the values reverses the direction.
"""

import time
from machine import UART
from common import start_http_thread, wifi_connect

SERVO_ID = 1
SERVO_SPEED = 800
SERVO_ACCELERATION = 50

# Initial estimate: the PSU knob uses about 330 degrees of the servo's
# 360-degree / 4096-count range. Replace these with measured safe endpoints.
SERVO_POS_AT_0_PCT = 0
SERVO_POS_AT_100_PCT = 3754

uart = UART(2, baudrate=1_000_000, tx=17)

state = {
    "cmd": {"intensity": 0.0},
    "tlm": {},
    "last_cmd_ms": time.ticks_ms(),
}


def clamp(value, low, high):
    return max(low, min(high, value))


def checksum(data):
    return (~sum(data)) & 0xFF


def write_reg(servo_id, address, values):
    length = len(values) + 3
    packet_body = [servo_id, length, 0x03, address] + values
    packet = bytearray(
        [0xFF, 0xFF] + packet_body + [checksum(packet_body)]
    )
    uart.write(packet)


def move_to(position, speed=SERVO_SPEED, acceleration=SERVO_ACCELERATION):
    position = int(clamp(position, 0, 4095))
    values = [
        position & 0xFF,
        (position >> 8) & 0xFF,
        0,
        0,
        speed & 0xFF,
        (speed >> 8) & 0xFF,
        acceleration,
    ]
    write_reg(SERVO_ID, 0x2A, values)


def position_from_intensity(intensity):
    intensity = clamp(float(intensity), 0.0, 100.0)
    span = SERVO_POS_AT_100_PCT - SERVO_POS_AT_0_PCT
    return int(round(SERVO_POS_AT_0_PCT + span * intensity / 100.0))


print("[servo] booting")
wlan = wifi_connect("servo")
print(
    "[servo] Local IPv4:",
    wlan.ifconfig()[0] if wlan.isconnected() else "NOT CONNECTED",
)
start_http_thread(state)

last_position = None
last_intensity = 0.0

try:
    while True:
        cmd = state["cmd"]

        # Direct position wins when supplied, making endpoint calibration easy.
        if "position" in cmd:
            target_position = int(clamp(int(cmd.pop("position")), 0, 4095))
            span = SERVO_POS_AT_100_PCT - SERVO_POS_AT_0_PCT
            if span:
                last_intensity = clamp(
                    100.0
                    * (target_position - SERVO_POS_AT_0_PCT)
                    / span,
                    0.0,
                    100.0,
                )
        else:
            try:
                last_intensity = clamp(
                    float(cmd.get("intensity", last_intensity)), 0.0, 100.0
                )
            except (TypeError, ValueError):
                last_intensity = 0.0
            target_position = position_from_intensity(last_intensity)

        if target_position != last_position:
            move_to(target_position)
            last_position = target_position
            print(
                "[servo] intensity={:.1f}% position={}".format(
                    last_intensity, last_position
                )
            )

        state["tlm"] = {
            "role": "servo",
            "intensity": last_intensity,
            "position": last_position,
            "pos_0_pct": SERVO_POS_AT_0_PCT,
            "pos_100_pct": SERVO_POS_AT_100_PCT,
        }
        time.sleep_ms(50)
except KeyboardInterrupt:
    print("[servo] stopped")
finally:
    state["shutdown"] = True
    time.sleep_ms(600)
