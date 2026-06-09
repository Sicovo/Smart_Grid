"""Minimal Pico W WiFi and HTTP command server for the servo board."""

import _thread
import gc
import json
import network
import socket
import time

from wifi_config import (
    DNS,
    GATEWAY,
    STATIC_IP,
    SUBNET,
    WIFI_PASS,
    WIFI_SSID,
)

CORS = (
    b"Access-Control-Allow-Origin: *\r\n"
    b"Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
    b"Access-Control-Allow-Headers: Content-Type\r\n"
)


def wifi_connect(hostname, timeout_ms=15000):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if STATIC_IP:
        wlan.ifconfig((STATIC_IP, SUBNET, GATEWAY, DNS))
    try:
        wlan.config(hostname=hostname)
    except (OSError, ValueError):
        pass
    wlan.connect(WIFI_SSID, WIFI_PASS)

    deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
    while not wlan.isconnected() and time.ticks_diff(deadline, time.ticks_ms()) > 0:
        time.sleep_ms(200)
    return wlan


def _send(sock, status, content_type, body):
    sock.sendall(
        status
        + b"\r\nContent-Type: "
        + content_type
        + b"\r\n"
        + CORS
        + b"Content-Length: "
        + str(len(body)).encode()
        + b"\r\nConnection: close\r\n\r\n"
        + body
    )


def _http_server(state, port):
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", port))
    server.listen(2)
    server.settimeout(0.5)
    request_count = 0

    while not state.get("shutdown", False):
        client = None
        try:
            client, _ = server.accept()
            client.settimeout(2.0)
            request = client.recv(2048)
            first_line = request.split(b"\r\n", 1)[0].split(b" ")
            if len(first_line) < 2:
                continue
            method, path = first_line[0], first_line[1]

            if method == b"OPTIONS":
                _send(client, b"HTTP/1.1 204 No Content", b"text/plain", b"")
            elif method == b"GET" and path == b"/tlm":
                body = json.dumps(state["tlm"]).encode()
                _send(client, b"HTTP/1.1 200 OK", b"application/json", body)
            elif method == b"POST" and path == b"/cmd":
                body_start = request.find(b"\r\n\r\n")
                body = request[body_start + 4 :] if body_start >= 0 else b""
                command = json.loads(body)
                if not isinstance(command, dict):
                    raise ValueError("command must be a JSON object")
                state["cmd"].update(command)
                state["last_cmd_ms"] = time.ticks_ms()
                print("[cmd] received", command)
                _send(client, b"HTTP/1.1 200 OK", b"text/plain", b"OK")
            else:
                _send(client, b"HTTP/1.1 404 Not Found", b"text/plain", b"")
        except Exception as exc:
            if client is not None:
                try:
                    body = json.dumps({"error": str(exc)}).encode()
                    _send(
                        client,
                        b"HTTP/1.1 400 Bad Request",
                        b"application/json",
                        body,
                    )
                except Exception:
                    pass
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
            request_count += 1
            if request_count >= 10:
                request_count = 0
                gc.collect()

    server.close()


def start_http_thread(state, port=80):
    state.setdefault("shutdown", False)
    _thread.start_new_thread(_http_server, (state, port))
