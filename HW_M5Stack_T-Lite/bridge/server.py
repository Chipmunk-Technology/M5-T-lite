"""Local bridge. The browser only talks to 127.0.0.1. The serial port stays here."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import socket
import struct
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import analyze
import protocol
import report
import store

STATIC = ROOT / "static"
DATA = ROOT / "data" / "tlite.sqlite"
HOST = "127.0.0.1"
PORT = 8765
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
WORK_TO_ID = {"memory": protocol.WORK_MEMORY, "leak": protocol.WORK_LEAK, "sentry": protocol.WORK_SENTRY}
ID_TO_WORK = {v: k for k, v in WORK_TO_ID.items()}


class Hub:
    def __init__(self, db: store.Store, demo: bool):
        self.db = db
        self.demo = demo
        self.lock = threading.Lock()
        self.clients = []
        self.serial = None
        self.work = "memory"
        self.material = "plastic"
        self.distance = "hand"
        self.name = ""
        self.sensitivity = 1
        self.armed = False
        self.mask = []
        self.mac = ""
        self.battery = None
        self.pixels = None
        self.ta_cdeg = None
        self.reflected_cdeg = None
        self.emissivity_milli = 950
        self.link = "down"
        self.stability = analyze.Stability()
        self.saved_until = 0.0
        self.shake_until = 0.0
        self.last_frame_at = 0.0
        self.last_text = ""
        self.last_text_at = 0.0
        self.selected_event = None
        self.sentry_event_ms = None
        self.sentry_peak = 0
        self.sentry_cells = 0
        self.armed_since_ms = None
        self.boot_ms = None
        self.twin = analyze.SentryTwin()

    def snapshot(self):
        with self.lock:
            return self._view()

    def _view(self):
        now = time.time()
        sentence = self._sentence(now)
        pixels = self.pixels
        previous = self.db.previous(self.name) if self.name else None
        last = previous["pixels"] if previous else None
        marks = []
        if self.work == "leak" and pixels and sentence.status not in ("leak-quiet",):
            found = analyze.leak_marks(pixels)
            if found:
                marks = found["cells"]
        span = []
        if pixels:
            span = [min(pixels), max(pixels)]
            if last:
                span = [min(span[0], min(last)), max(span[1], max(last))]
        events = []
        for item in self.db.events():
            age = _event_sentence(item)
            events.append({"id": item["id"], "taken_at": item["taken_at"], "sentence": age})
        return {
            "demo": self.demo,
            "link": self.link,
            "work": self.work,
            "sentence": sentence.text,
            "number": sentence.number,
            "unit": sentence.unit,
            "emphasis": sentence.emphasis,
            "small": sentence.small,
            "status": sentence.status,
            "pixels": pixels,
            "last_pixels": last,
            "marks": marks,
            "mask": list(self.mask),
            "battery": self.battery,
            "mac": self.mac,
            "material": self.material,
            "distance": self.distance,
            "name": self.name,
            "sensitivity": self.sensitivity,
            "armed": self.armed,
            "can_remember": self._can_remember(now),
            "events": events,
            "selected_event": self.selected_event,
            "range": span,
            "ta_cdeg": self.ta_cdeg,
            "reflected_cdeg": self.reflected_cdeg,
            "emissivity_milli": None if self.material == "shiny" else self.emissivity_milli,
        }

    def _can_remember(self, now: float) -> bool:
        return (
            self.link == "live"
            and self.work == "memory"
            and self.material != "shiny"
            and bool(self.name.strip())
            and self.stability.steady(now)
            and self.pixels is not None
        )

    def _sentence(self, now: float):
        if self.link == "down":
            return analyze.Sentence("裝置已卸下。", "", "", False, "", "down")
        if self.link == "sensor":
            return analyze.Sentence("感測器未找到。", "", "", False, "", "sensor")
        if self.link != "live" or not self.pixels:
            return analyze.Sentence("尚未連接。", "", "", False, "", "wait")
        if self.work == "sentry":
            view = analyze.SentryView(
                self.armed,
                self.sensitivity,
                self.sentry_event_ms,
                self.sentry_peak,
                self.sentry_cells,
                self.armed_since_ms or 0,
            )
            return analyze.sentry_sentence(view, self.boot_ms or 0)
        if now < self.shake_until:
            return analyze.Sentence("請握穩。", "", "", False, analyze.cell_phrase(self.distance), "shake")
        if self.work == "leak":
            sentence, _marks = analyze.leak_sentence(self.pixels, self.distance)
            return sentence
        previous = self.db.previous(self.name) if self.name else None
        prev_pixels = previous["pixels"] if previous else None
        return analyze.memory_sentence(
            self.name.strip(),
            self.pixels,
            prev_pixels,
            self.material == "shiny",
            self.distance,
            self.stability.steady(now),
            self.stability.moving(),
            now < self.saved_until,
        )

    def on_frame(self, frame: protocol.ThermalFrame):
        with self.lock:
            self.link = "live"
            self.last_frame_at = time.time()
            self.boot_ms = frame.time_ms
            self.battery = None if frame.battery_pct == 255 else frame.battery_pct
            self.emissivity_milli = frame.emissivity_milli
            self.ta_cdeg = frame.ta_cdeg
            self.reflected_cdeg = frame.reflected_cdeg
            self.armed = frame.armed
            if frame.armed and self.armed_since_ms is None:
                self.armed_since_ms = frame.time_ms
            if not frame.armed:
                self.armed_since_ms = None
            self.sensitivity = frame.sensitivity if frame.sensitivity in (0, 1, 2) else self.sensitivity
            if not frame.stored:
                self.pixels = frame.pixels
                self.stability.push(frame.pixels, time.time())
            if frame.event:
                self.sentry_event_ms = frame.time_ms
                self.sentry_peak = frame.sentry_peak_cdeg
                self.sentry_cells = frame.sentry_cells
                self.db.add_event(self.mac or "unknown", frame.time_ms, frame.sentry_peak_cdeg, frame.sentry_cells, frame.pixels)
            if frame.button and self.work == "memory":
                self._remember_locked()

    def on_hello(self, hello: protocol.Hello):
        with self.lock:
            self.mac = hello.mac
            self.db.save_eeprom(hello.mac, hello.ee)
            if self.link == "down":
                self.link = "wait"

    def on_settings(self, settings: protocol.Settings):
        with self.lock:
            self.armed = settings.armed
            self.sensitivity = settings.sensitivity if settings.sensitivity in (0, 1, 2) else 1
            self.mask = protocol.cells_from_mask(settings.mask)
            if self.link == "down":
                self.link = "wait"

    def mark_down(self):
        with self.lock:
            self.link = "down"
            self.pixels = None

    def mark_sensor(self):
        with self.lock:
            if self.link != "live":
                self.link = "sensor"

    def command(self, msg: dict):
        op = msg.get("op")
        with self.lock:
            if op == "work":
                work = msg.get("work")
                if work in WORK_TO_ID:
                    self.work = work
                    self._send(protocol.pack_work(WORK_TO_ID[work]))
                    if work == "sentry":
                        self.armed = True
                        self.armed_since_ms = self.boot_ms or 0
                        self._send(protocol.pack_sentry(True, self.sensitivity))
            elif op == "name":
                self.name = str(msg.get("name") or "")[:40]
            elif op == "material":
                material = msg.get("material")
                if material in analyze.MATERIALS:
                    self.material = material
                    emis = analyze.MATERIALS[material][1]
                    if emis is not None:
                        self.emissivity_milli = emis
                        self._send(protocol.pack_condition(emis, True))
            elif op == "distance":
                if msg.get("distance") in analyze.DISTANCES:
                    self.distance = msg["distance"]
            elif op == "sensitivity":
                sens = int(msg.get("sensitivity", 1))
                if sens in (0, 1, 2):
                    self.sensitivity = sens
                    self.twin.sensitivity = sens
                    self._send(protocol.pack_sentry(self.armed, sens))
            elif op == "arm":
                self.armed = bool(msg.get("armed"))
                self.twin.armed = self.armed
                if self.armed and self.armed_since_ms is None:
                    self.armed_since_ms = self.boot_ms or 0
                if not self.armed:
                    self.armed_since_ms = None
                    self.sentry_event_ms = None
                self._send(protocol.pack_sentry(self.armed, self.sensitivity))
            elif op == "mask":
                cells = [int(i) for i in msg.get("cells", []) if isinstance(i, int) or str(i).isdigit()]
                cells = [i for i in cells if 0 <= int(i) < 768]
                self.mask = cells
                self.twin.mask = set(cells)
                self._send(protocol.pack_mask(protocol.mask_from_cells(cells)))
            elif op == "remember":
                self._remember_locked()
            elif op == "event":
                item = self.db.event(int(msg.get("id", 0)))
                self.selected_event = item
        self.push_text()

    def _remember_locked(self):
        now = time.time()
        if self.material == "shiny" or self.work != "memory":
            return
        if not self.name.strip() or not self.stability.steady(now) or self.stability.best is None:
            self.shake_until = now + 2
            return
        frame = protocol.ThermalFrame(
            flags=protocol.FLAG_COMPLETE,
            seq=0,
            time_ms=self.boot_ms or 0,
            ta_cdeg=self.ta_cdeg or 0,
            vdd_cv=0,
            emissivity_milli=self.emissivity_milli,
            reflected_cdeg=self.reflected_cdeg or 0,
            sentry_peak_cdeg=0,
            sentry_cells=0,
            sensitivity=self.sensitivity,
            battery_pct=255 if self.battery is None else self.battery,
            work=WORK_TO_ID[self.work],
            quiet_minutes=255,
            event_age_s=0xFFFF,
            pixels=list(self.stability.best),
        )
        self.db.remember(self.name.strip(), self.mac, frame, self.material, self.distance)
        self.saved_until = now + 3
        self.shake_until = 0

    def _send(self, payload: bytes):
        if self.demo or self.serial is None:
            return
        try:
            self.serial.write(payload)
        except Exception:
            self.link = "down"

    def push_text(self):
        with self.lock:
            sentence = self._sentence(time.time())
            now = time.time()
            if sentence.text == self.last_text and now - self.last_text_at < 1.0:
                return
            self.last_text = sentence.text
            self.last_text_at = now
            self._send(protocol.pack_text(sentence.text, sentence.emphasis))

    def ping(self):
        with self.lock:
            self._send(protocol.pack_ping())

    def note_silence(self):
        with self.lock:
            if self.link == "live" and time.time() - self.last_frame_at > 2.5:
                self.link = "wait"
                self.pixels = None


def _event_sentence(item) -> str:
    return f"有暖物經過，比背景高 {analyze.fmt_c(item['peak_cdeg'])}°C。"


class BridgeServer:
    def __init__(self, hub: Hub):
        self.hub = hub

    def serve(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((HOST, PORT))
        sock.listen(8)
        print(f"熱記憶  http://{HOST}:{PORT}", flush=True)
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
            length = int(headers.get("content-length", "0") or 0)
            body = rest
            while len(body) < length:
                body += conn.recv(length - len(body))
            self._http(conn, method, path.split("?", 1)[0], body)
        except Exception:
            import traceback
            traceback.print_exc()
            try:
                conn.close()
            except Exception:
                pass

    def _http(self, conn, method, path, body):
        if path == "/api/report.csv":
            payload = report.csv_bytes(self.hub.snapshot())
            self._reply(conn, 200, payload, "text/csv; charset=utf-8", "attachment; filename=thermal-memory.csv")
            return
        if path == "/api/report.pdf":
            html = report.report_html(self.hub.snapshot())
            pdf = report.html_to_pdf(html)
            if pdf:
                self._reply(conn, 200, pdf, "application/pdf", "attachment; filename=thermal-memory.pdf")
            else:
                self._reply(conn, 200, html.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/api/report.html":
            self._reply(conn, 200, report.report_html(self.hub.snapshot()).encode("utf-8"), "text/html; charset=utf-8")
            return
        if method == "POST" and path == "/api/command":
            self.hub.command(json.loads(body.decode("utf-8") or "{}"))
            self._reply(conn, 200, b"{}", "application/json")
            return
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        file_path = (STATIC / rel).resolve()
        if not str(file_path).startswith(str(STATIC.resolve())) or not file_path.is_file():
            self._reply(conn, 404, b"not found", "text/plain")
            return
        kind = "text/html; charset=utf-8"
        if file_path.suffix == ".css":
            kind = "text/css; charset=utf-8"
        elif file_path.suffix == ".js":
            kind = "text/javascript; charset=utf-8"
        self._reply(conn, 200, file_path.read_bytes(), kind)

    def _reply(self, conn, status, payload: bytes, content_type: str, disposition: str | None = None):
        reason = {200: "OK", 404: "Not Found"}.get(status, "OK")
        extra = f"Content-Disposition: {disposition}\r\n" if disposition else ""
        head = (
            f"HTTP/1.1 {status} {reason}\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(payload)}\r\n"
            f"{extra}"
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
        pending += conn.recv(length - len(pending))
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
            dead = []
            for conn in hub.clients:
                try:
                    ws_send(conn, payload)
                except Exception:
                    dead.append(conn)
            for conn in dead:
                hub.clients.remove(conn)
        hub.push_text()
        time.sleep(0.25)


def serial_loop(hub: Hub, port_name: str | None, baud: int):
    import serial

    parser = protocol.Parser()
    announced = None
    while True:
        name = port_name or _detect_port()
        if name != announced:
            print(f"序列埠：{name or '沒有'}", flush=True)
            announced = name
        if not name:
            hub.mark_down()
            time.sleep(1)
            continue
        try:
            link = serial.Serial()
            link.port = name
            link.baudrate = baud
            link.timeout = 0.2
            link.dtr = False
            link.rts = False
            link.open()
            link.rts = True
            time.sleep(0.05)
            link.rts = False
            time.sleep(0.3)
        except Exception as exc:
            print(f"打不開 {name}：{exc}", flush=True)
            hub.mark_down()
            time.sleep(1)
            continue
        hub.serial = link
        with hub.lock:
            if hub.link == "down":
                hub.link = "wait"
        parser = protocol.Parser()
        last_ping = 0.0
        try:
            while True:
                blob = link.read(4096)
                if blob:
                    for item in parser.feed(blob):
                        if isinstance(item, protocol.ThermalFrame):
                            hub.on_frame(item)
                        elif isinstance(item, protocol.Hello):
                            hub.on_hello(item)
                        elif isinstance(item, protocol.Settings):
                            hub.on_settings(item)
                else:
                    hub.note_silence()
                now = time.time()
                if now - last_ping > 2:
                    hub.ping()
                    last_ping = now
                if not link.is_open:
                    break
        except Exception as exc:
            print(f"序列中斷：{exc}", flush=True)
        finally:
            hub.serial = None
            hub.mark_down()
            try:
                link.close()
            except Exception:
                pass
        time.sleep(0.5)


def _detect_port():
    from serial.tools import list_ports

    ranked = []
    for port in list_ports.comports():
        text = f"{port.hwid} {port.description} {port.device}".upper()
        if "BTHENUM" in text or "BLUETOOTH" in text:
            continue
        if "0403" in text and "6001" in text:
            return port.device
        if "USB" in text and "SERIAL" in text:
            ranked.append(port.device)
    return ranked[0] if ranked else None


def demo_loop(hub: Hub):
    hub.mac = "示範"
    hub.link = "live"
    start = time.time()
    while True:
        now = time.time()
        pixels = _demo_pixels(now - start)
        with hub.lock:
            hub.link = "live"
            hub.pixels = pixels
            hub.ta_cdeg = 2500
            hub.reflected_cdeg = 2500
            hub.battery = 80
            hub.boot_ms = int((now - start) * 1000)
            hub.last_frame_at = now
            hub.stability.push(pixels, now)
            if hub.armed:
                hub.twin.sensitivity = hub.sensitivity
                hub.twin.mask = set(hub.mask)
                hub.twin.armed = True
                hit = hub.twin.step(pixels, now - start)
                if hit:
                    hub.sentry_event_ms = hub.boot_ms
                    hub.sentry_peak = hit["peak"]
                    hub.sentry_cells = hit["cells"]
                    hub.db.add_event("示範", hub.boot_ms, hit["peak"], hit["cells"], pixels)
        time.sleep(0.25)


def _demo_pixels(t: float):
    pixels = []
    cx = 16 + int(6 * math_sin(t / 4))
    cy = 12
    hot = int(t) % 25 < 4
    hx, hy = 8, 6
    for y in range(24):
        for x in range(32):
            base = 2300 + int(40 * math_sin((x + y) / 7.0 + t))
            if abs(x - cx) + abs(y - cy) < 4:
                base += 700
            if hot and abs(x - hx) <= 2 and abs(y - hy) <= 3:
                base += 450
            # A cold vertical pipe, so 漏熱 has something to mark in the demo.
            if 20 <= x <= 21 and 4 <= y <= 18:
                base -= 1400
            pixels.append(base)
    return pixels


def math_sin(value: float) -> float:
    import math

    return math.sin(value)


def main():
    parser = argparse.ArgumentParser(description="熱記憶本機橋接")
    parser.add_argument("--demo", action="store_true", help="沒有裝置時用示範畫面")
    parser.add_argument("--port", default="", help="序列埠。留空則每次重新偵測")
    parser.add_argument("--baud", type=int, default=115200)
    args = parser.parse_args()
    hub = Hub(store.Store(DATA), demo=args.demo)
    threading.Thread(target=broadcast, args=(hub,), daemon=True).start()
    if args.demo:
        print("示範畫面。這不是這台 T-Lite 的讀數，蜂鳴只在裝置韌體裡。", flush=True)
        threading.Thread(target=demo_loop, args=(hub,), daemon=True).start()
    else:
        threading.Thread(target=serial_loop, args=(hub, args.port or None, args.baud), daemon=True).start()
    BridgeServer(hub).serve()


if __name__ == "__main__":
    main()
