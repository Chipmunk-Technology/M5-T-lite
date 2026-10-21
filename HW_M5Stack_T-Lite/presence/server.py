"""Local page for factory T-Lite firmware. The browser only talks to 127.0.0.1.

The device is polled at /json. Nothing here is written back to the device.

    python server.py --demo
    python server.py --url http://192.168.1.20
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import socket
import struct
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import count

STATIC = ROOT / "static"
HOST = "127.0.0.1"
PORT = 8766
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
POLL_S = 0.25
FEVER_C = 36.7
MEASURE_SAMPLES = 10
LONG_ALARM_S = 8.0


def device_url(raw: str) -> str | None:
    text = (raw or "").strip()
    if not text:
        return None
    if "://" not in text:
        text = "http://" + text
    parts = urllib.parse.urlsplit(text)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    if parts.username or parts.password:
        return None
    host = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
    port = f":{parts.port}" if parts.port else ""
    return f"{parts.scheme}://{host}{port}/json"


def device_label(url: str | None) -> str:
    if not url:
        return ""
    parts = urllib.parse.urlsplit(url)
    return parts.netloc


def _cdeg(payload: dict, key: str):
    value = payload.get(key) if isinstance(payload, dict) else None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return int(round(number * 100))


def parse_frame(payload: dict) -> list[int] | None:
    frame = payload.get("frame") if isinstance(payload, dict) else None
    if not isinstance(frame, list) or len(frame) != count.PIXELS:
        return None
    out = []
    for value in frame:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        number = float(value)
        if not math.isfinite(number):
            return None
        out.append(int(round(number * 100)))
    return out


def demo_pixels(t: float) -> list[int]:
    pixels = [2200] * count.PIXELS
    if t < 4.0:
        return pixels
    x = 4 + int((t - 4.0) * 2) % 10
    _paint(pixels, x, 8, 3, 5, 3200)
    if t >= 9.0:
        _paint(pixels, 24, 16, 3, 4, 3300)
    return pixels


def _paint(pixels, x, y, w, h, temp):
    for yy in range(y, min(count.HEIGHT, y + h)):
        for xx in range(x, min(count.WIDTH, x + w)):
            pixels[yy * count.WIDTH + xx] = temp


def _clock():
    now = time.localtime()
    return time.strftime("%Y-%m-%d", now), time.strftime("%H:%M:%S", now)


class Session:
    """Ten temperature samples, one second apart."""

    def __init__(self):
        self.phase = "idle"
        self.rows = []
        self.next_at = 0.0
        self.average = None
        self.fever = None
        self.alarm = None

    def start(self, now: float, temp: float, date: str, clock: str):
        self.phase = "run"
        self.rows = [{"date": date, "time": clock, "temp": temp}]
        self.next_at = now + 1.0
        self.average = None
        self.fever = None
        self.alarm = None

    def tick(self, now: float, temp, date: str, clock: str):
        if self.phase != "run" or temp is None or now < self.next_at:
            return None
        self.rows.append({"date": date, "time": clock, "temp": temp})
        if len(self.rows) < MEASURE_SAMPLES:
            self.next_at = now + 1.0
            return None
        tenths = [int(round(row["temp"] * 10)) for row in self.rows]
        mean = sum(tenths) / len(tenths)
        self.average = mean / 10.0
        self.fever = mean > int(round(FEVER_C * 10))
        self.phase = "done"
        self.alarm = "long" if self.fever else "triple"
        return self.alarm


class Hub:
    def __init__(self, url: str | None, demo: bool):
        self.demo = demo
        self.url = device_url(url) if url else None
        self.lock = threading.Lock()
        self.clients = []
        self.counter = count.Counter()
        self.started = time.time()
        self.pixels = None
        self.presence = None
        self.highest = None
        self.mask = []
        self.sensitivity = count.DEFAULT_SENSITIVITY
        self.interval_ms = count.DEFAULT_INTERVAL_MS
        self.distance = "room"
        self.link = "wait"
        self.fails = 0
        self.flow = count.Flow()
        self.flow_until = 0.0
        self.pending_buzz = False
        self.session = Session()
        self.pending_alarm = None

    def command(self, msg: dict):
        op = msg.get("op")
        with self.lock:
            if op == "distance" and msg.get("distance") in count.DISTANCES:
                if msg["distance"] != self.distance:
                    self.distance = msg["distance"]
                    self.counter.reset()
            elif op == "sensitivity":
                self.sensitivity = count.clamp_sensitivity(msg.get("sensitivity"))
            elif op == "interval":
                self.interval_ms = count.clamp_interval(msg.get("interval"))
            elif op == "mask":
                cells = []
                for item in msg.get("cells", []):
                    try:
                        index = int(item)
                    except (TypeError, ValueError):
                        continue
                    if 0 <= index < count.PIXELS:
                        cells.append(index)
                merged = set(self.mask)
                merged.update(cells)
                self.mask = sorted(merged)
                self._retake()
            elif op == "clearmask":
                self.mask = []
                self._retake()
            elif op == "measure" and msg.get("action") == "start":
                if self.link != "live" or self.session.phase == "run":
                    return
                temp = self._reading_c()
                if temp is None:
                    return
                self.pending_buzz = False
                self.pending_alarm = None
                self.session.start(time.time(), temp, *_clock())
            elif op == "url" and not self.demo:
                url = device_url(str(msg.get("url") or ""))
                if url != self.url:
                    self.url = url
                    self.pixels = None
                    self.presence = None
                    self.fails = 0
                    self.link = "wait"
                    self.counter.reset()
                    self.flow = count.Flow()
                    self.pending_buzz = False
                    self.flow_until = 0.0
                    self.session = Session()
                    self.pending_alarm = None

    def _reading_c(self):
        if self.highest is not None:
            return round(self.highest / 100.0, 1)
        if self.pixels:
            return round(max(self.pixels) / 100.0, 1)
        return None

    def _retake(self):
        if self.pixels:
            self.presence = count.spot_reading(self.pixels, self.highest, self.mask)

    def ingest(self, pixels, now: float, highest=None):
        with self.lock:
            self.pixels = list(pixels)
            self.highest = highest
            self.fails = 0
            self.link = "live"
            self.presence = count.spot_reading(self.pixels, highest, self.mask)
            if self.session.phase == "run":
                alarm = self.session.tick(now, self._reading_c(), *_clock())
                if alarm:
                    self.pending_alarm = alarm
                    self.pending_buzz = False
            elif self.pending_alarm is None and self.flow.step(
                self.pixels, now, self.mask, self.sensitivity, self.interval_ms
            ):
                self.flow_until = now + 3.0
                if not self.demo:
                    self.pending_buzz = True

    def mark_down(self):
        with self.lock:
            self.fails += 1
            if self.fails < 3:
                return
            self.link = "down"
            self.pixels = None
            self.presence = None
            self.counter.reset()
            self.flow = count.Flow()
            self.pending_buzz = False
            self.flow_until = 0.0
            if self.session.phase == "run":
                self.session = Session()
            self.pending_alarm = None

    def snapshot(self):
        with self.lock:
            return self._view()

    def _view(self):
        lo, hi = 0, 1
        if self.pixels:
            lo = min(self.pixels)
            hi = max(self.pixels)
            if hi <= lo:
                hi = lo + 1
        base = {
            "demo": self.demo,
            "device": device_label(self.url),
            "distance": self.distance,
            "sensitivity": self.sensitivity,
            "interval": self.interval_ms,
            "mask": self.mask,
            "pixels": self.pixels,
            "range": [lo, hi],
            "marks": [],
            "link": self.link,
            "measure": self._measure_view(),
        }
        if self.link == "down":
            base.update(text="裝置已卸下。", number="", unit="", small="熱圖已停下。", status="down")
            base["pixels"] = None
            return base
        if self.presence is None:
            small = "填下面的裝置位址。" if not self.demo and not self.url else ""
            base.update(text="尚未連接。", number="", unit="", small=small, status="wait")
            return base
        text = self.presence.text
        small = self.presence.small
        status = self.presence.status
        if time.time() < self.flow_until:
            text = "溫度在流動。"
            small = "蜂鳴一聲。" + small
            status = "flow"
        base.update(
            text=text,
            number=self.presence.number,
            unit=self.presence.unit,
            small=small,
            status=status,
            marks=self.presence.marks,
        )
        return base

    def _measure_view(self):
        average = None if self.session.average is None else round(self.session.average, 1)
        return {
            "phase": self.session.phase,
            "rows": [dict(row) for row in self.session.rows],
            "average": average,
            "fever": self.session.fever,
        }

    def consume_buzz(self) -> bool:
        with self.lock:
            pending = self.pending_buzz
            self.pending_buzz = False
            return pending

    def consume_alarm(self):
        with self.lock:
            alarm = self.pending_alarm
            self.pending_alarm = None
            return alarm


def fetch_frame(url: str):
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=2) as response:
        payload = json.loads(response.read().decode("utf-8"))
    pixels = parse_frame(payload)
    if pixels is None:
        raise ValueError("frame")
    return pixels, _cdeg(payload, "highest")


def poll_loop(hub: Hub):
    while True:
        with hub.lock:
            url = hub.url
        if not url:
            time.sleep(0.5)
            continue
        try:
            pixels, highest = fetch_frame(url)
        except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError, TimeoutError):
            hub.mark_down()
            time.sleep(0.5)
            continue
        hub.ingest(pixels, time.time(), highest)
        origin = url[: -len("/json")]
        alarm = hub.consume_alarm()
        try:
            if alarm == "long":
                buzz_long(origin, LONG_ALARM_S)
            elif alarm == "triple":
                buzz_triple(origin)
            elif hub.consume_buzz():
                buzz_once(origin)
        except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError, TimeoutError):
            print("蜂鳴沒有送出", flush=True)
        time.sleep(POLL_S)


def _param(origin: str, **fields):
    query = urllib.parse.urlencode({key: value for key, value in fields.items()})
    request = urllib.request.Request(origin + "/param?" + query, method="GET")
    with urllib.request.urlopen(request, timeout=2) as response:
        return response.read()


def _alarm_saved(origin: str):
    request = urllib.request.Request(origin + "/param", method="GET")
    with urllib.request.urlopen(request, timeout=2) as response:
        saved = json.loads(response.read().decode("utf-8"))
    mode = str(saved.get("alarm_mode", "0")).strip()
    temp = str(saved.get("alarm_temperature", "100.0")).strip()
    ref = str(saved.get("alarm_reference", "0")).strip()
    try:
        if float(temp) < 0:
            mode = "0"
            temp = "100.0"
    except ValueError:
        mode = "0"
        temp = "100.0"
    volume = str(saved.get("misc_volume", "2")).strip()
    return mode, temp, ref, volume


def _alarm_restore(origin: str, mode: str, temp: str, ref: str, volume: str):
    for fields in (
        {"alarm_mode": mode},
        {"alarm_temperature": temp},
        {"alarm_reference": ref},
    ):
        try:
            _param(origin, **fields)
        except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError, TimeoutError):
            print("警報設定沒有還原", flush=True)
    if volume == "0":
        try:
            _param(origin, misc_volume="0")
        except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError, TimeoutError):
            print("音量沒有還原", flush=True)


def _alarm_arm(origin: str, volume: str):
    if volume == "0":
        _param(origin, misc_volume="2")
    _param(origin, alarm_reference="0")
    _param(origin, alarm_temperature="-10")


def buzz_once(origin: str):
    """One device beep. The alarm is on only long enough for a single tone."""
    mode, temp, ref, volume = _alarm_saved(origin)
    try:
        _alarm_arm(origin, volume)
        _param(origin, alarm_mode="2")
        time.sleep(0.03)
    finally:
        _alarm_restore(origin, mode, temp, ref, volume)


def buzz_triple(origin: str):
    """Three separate beeps. Each one is turned off before the device repeats it."""
    mode, temp, ref, volume = _alarm_saved(origin)
    try:
        _alarm_arm(origin, volume)
        for index in range(3):
            _param(origin, alarm_mode="2")
            time.sleep(0.04)
            _param(origin, alarm_mode="0")
            if index < 2:
                time.sleep(0.4)
    finally:
        _alarm_restore(origin, mode, temp, ref, volume)


def buzz_long(origin: str, seconds: float):
    """Hold the device alarm for a long ring, then put the old setting back."""
    mode, temp, ref, volume = _alarm_saved(origin)
    try:
        _alarm_arm(origin, volume)
        _param(origin, alarm_mode="2")
        time.sleep(seconds)
    finally:
        _alarm_restore(origin, mode, temp, ref, volume)


def demo_loop(hub: Hub):
    while True:
        now = time.time()
        pixels = demo_pixels(now - hub.started)
        hub.ingest(pixels, now, max(pixels))
        time.sleep(POLL_S)


class Page:
    def __init__(self, hub: Hub):
        self.hub = hub

    def serve(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((HOST, PORT))
        sock.listen(8)
        print(f"在席  http://{HOST}:{PORT}", flush=True)
        while True:
            conn, addr = sock.accept()
            if addr[0] != HOST:
                conn.close()
                continue
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn: socket.socket):
        try:
            conn.settimeout(10)
            data = b""
            while b"\r\n\r\n" not in data:
                chunk = conn.recv(4096)
                if not chunk:
                    conn.close()
                    return
                data += chunk
                if len(data) > 65536:
                    conn.close()
                    return
            head, rest = data.split(b"\r\n\r\n", 1)
            lines = head.decode("iso-8859-1", "replace").split("\r\n")
            method, path, _proto = lines[0].split(" ", 2)
            headers = {}
            for line in lines[1:]:
                if ":" in line:
                    key, value = line.split(":", 1)
                    headers[key.strip().lower()] = value.strip()
            if headers.get("upgrade", "").lower() == "websocket":
                self._websocket(conn, headers, rest)
                return
            rel = "index.html" if path.split("?", 1)[0] in ("/", "") else path.split("?", 1)[0].lstrip("/")
            file_path = (STATIC / rel).resolve()
            if not str(file_path).startswith(str(STATIC.resolve())) or not file_path.is_file():
                self._reply(conn, 404, b"not found", "text/plain; charset=utf-8")
                return
            kind = "text/html; charset=utf-8"
            if file_path.suffix == ".css":
                kind = "text/css; charset=utf-8"
            elif file_path.suffix == ".js":
                kind = "text/javascript; charset=utf-8"
            self._reply(conn, 200, file_path.read_bytes(), kind)
        except Exception:
            try:
                conn.close()
            except Exception:
                pass

    def _reply(self, conn, status, payload: bytes, content_type: str):
        reason = {200: "OK", 404: "Not Found"}.get(status, "OK")
        head = (
            f"HTTP/1.1 {status} {reason}\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(payload)}\r\n"
            "Cache-Control: no-store\r\n"
            "Connection: close\r\n\r\n"
        )
        conn.sendall(head.encode("ascii") + payload)
        conn.close()

    def _websocket(self, conn, headers, rest):
        key = headers.get("sec-websocket-key", "")
        accept = base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()
        conn.sendall(
            (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
            ).encode("ascii")
        )
        conn.settimeout(None)
        with self.hub.lock:
            self.hub.clients.append(conn)
        try:
            pending = rest
            while True:
                message, pending = _ws_read(conn, pending)
                if message is None:
                    break
                if message:
                    self.hub.command(json.loads(message))
        finally:
            with self.hub.lock:
                if conn in self.hub.clients:
                    self.hub.clients.remove(conn)
            try:
                conn.close()
            except Exception:
                pass


def _ws_read(conn, pending: bytes):
    while len(pending) < 2:
        chunk = conn.recv(4096)
        if not chunk:
            return None, pending
        pending += chunk
    first, second = pending[0], pending[1]
    pending = pending[2:]
    opcode = first & 0x0F
    masked = second & 0x80
    length = second & 0x7F
    if length == 126:
        while len(pending) < 2:
            pending += conn.recv(4096)
        length = struct.unpack(">H", pending[:2])[0]
        pending = pending[2:]
    elif length == 127:
        while len(pending) < 8:
            pending += conn.recv(4096)
        length = struct.unpack(">Q", pending[:8])[0]
        pending = pending[8:]
    mask = b""
    if masked:
        while len(pending) < 4:
            pending += conn.recv(4096)
        mask = pending[:4]
        pending = pending[4:]
    while len(pending) < length:
        chunk = conn.recv(length - len(pending))
        if not chunk:
            return None, pending
        pending += chunk
    data = bytearray(pending[:length])
    pending = pending[length:]
    if masked:
        for i in range(len(data)):
            data[i] ^= mask[i % 4]
    if opcode == 0x8:
        return None, pending
    if opcode == 0x1:
        return data.decode("utf-8"), pending
    return "", pending


def ws_send(conn, text: str):
    raw = text.encode("utf-8")
    header = bytes([0x81])
    n = len(raw)
    if n < 126:
        header += bytes([n])
    elif n < 65536:
        header += bytes([126]) + struct.pack(">H", n)
    else:
        header += bytes([127]) + struct.pack(">Q", n)
    conn.sendall(header + raw)


def broadcast(hub: Hub):
    while True:
        payload = json.dumps(hub.snapshot(), ensure_ascii=False)
        with hub.lock:
            clients = list(hub.clients)
        dead = []
        for conn in clients:
            try:
                ws_send(conn, payload)
            except Exception:
                dead.append(conn)
        if dead:
            with hub.lock:
                for conn in dead:
                    if conn in hub.clients:
                        hub.clients.remove(conn)
        time.sleep(POLL_S)


def main():
    parser = argparse.ArgumentParser(description="在席：用出廠韌體的區網熱圖估計視野裡有幾人")
    parser.add_argument("--url", default="", help="裝置位址，例如 http://192.168.1.20 或 t-lite-xxxx.local")
    parser.add_argument("--demo", action="store_true", help="沒有裝置時的示範畫面")
    args = parser.parse_args()
    hub = Hub(args.url, args.demo)
    if args.demo:
        threading.Thread(target=demo_loop, args=(hub,), daemon=True).start()
    else:
        threading.Thread(target=poll_loop, args=(hub,), daemon=True).start()
    threading.Thread(target=broadcast, args=(hub,), daemon=True).start()
    Page(hub).serve()


if __name__ == "__main__":
    main()
