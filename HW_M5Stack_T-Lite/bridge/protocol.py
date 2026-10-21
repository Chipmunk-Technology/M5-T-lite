"""Binary USB contract shared with firmware/tlite-workstation.

Little-endian. CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF) over every
byte before the CRC. Workstation baud is 460800. Flash backup stays 115200.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

PIXELS = 768
MASK_BYTES = 96
FRAME_HEADER = 36
FRAME_LEN = FRAME_HEADER + PIXELS * 2 + 2
HELLO_EE = 832
HELLO_LEN = 13 + HELLO_EE * 2 + 2
SETTINGS_LEN = 8 + MASK_BYTES + 2

FLAG_COMPLETE = 0x01
FLAG_SUBPAGE = 0x02
FLAG_EVENT = 0x04
FLAG_BUTTON = 0x08
FLAG_ARMED = 0x10
FLAG_STEADY = 0x20
FLAG_STORED = 0x40

CMD_SET_SENTRY = 1
CMD_SET_MASK = 2
CMD_SET_COND = 3
CMD_SET_TEXT = 4
CMD_SET_WORK = 5
CMD_PING = 6

WORK_MEMORY = 0
WORK_LEAK = 1
WORK_SENTRY = 2


def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def _with_crc(body: bytes) -> bytes:
    return body + struct.pack("<H", crc16(body))


def pack_command(cmd: int, payload: bytes = b"") -> bytes:
    body = struct.pack("<4sBBH", b"TL0C", 1, cmd, len(payload)) + payload
    return _with_crc(body)


def pack_sentry(armed: bool, sensitivity: int) -> bytes:
    return pack_command(CMD_SET_SENTRY, bytes((1 if armed else 0, sensitivity & 0xFF)))


def pack_mask(mask: bytes) -> bytes:
    if len(mask) != MASK_BYTES:
        raise ValueError("mask must be 96 bytes")
    return pack_command(CMD_SET_MASK, mask)


def pack_condition(emissivity_milli: int, use_ta: bool = True) -> bytes:
    return pack_command(CMD_SET_COND, struct.pack("<HB", emissivity_milli, 1 if use_ta else 0))


def pack_text(sentence: str, emphasis: bool = False) -> bytes:
    raw = sentence.encode("utf-8")[:140]
    return pack_command(CMD_SET_TEXT, bytes((1 if emphasis else 0,)) + raw)


def pack_work(work: int) -> bytes:
    return pack_command(CMD_SET_WORK, bytes((work,)))


def pack_ping() -> bytes:
    return pack_command(CMD_PING, b"")


def pack_frame(frame: ThermalFrame) -> bytes:
    body = bytearray(FRAME_HEADER + PIXELS * 2)
    body[0:4] = b"TL01"
    struct.pack_into("<BBHII", body, 4, 1, frame.flags, FRAME_HEADER, frame.seq & 0xFFFFFFFF, frame.time_ms & 0xFFFFFFFF)
    struct.pack_into(
        "<hhHhhH",
        body,
        16,
        frame.ta_cdeg,
        frame.vdd_cv,
        frame.emissivity_milli,
        frame.reflected_cdeg,
        frame.sentry_peak_cdeg,
        frame.sentry_cells,
    )
    struct.pack_into(
        "<BBBBHH",
        body,
        28,
        frame.sensitivity,
        frame.battery_pct,
        frame.work,
        frame.quiet_minutes,
        frame.event_age_s,
        0,
    )
    struct.pack_into("<" + "h" * PIXELS, body, FRAME_HEADER, *[int(v) for v in frame.pixels])
    return _with_crc(bytes(body))


def pack_hello(mac: bytes, ee: bytes) -> bytes:
    body = bytearray(13 + HELLO_EE * 2)
    body[0:4] = b"TL0H"
    body[4] = 1
    body[5:11] = mac
    struct.pack_into("<H", body, 11, HELLO_EE)
    body[13:] = ee
    return _with_crc(bytes(body))


def pack_settings(armed: bool, sensitivity: int, work: int, mask: bytes) -> bytes:
    body = bytearray(8 + MASK_BYTES)
    body[0:4] = b"TL0M"
    body[4] = 1
    body[5] = 1 if armed else 0
    body[6] = sensitivity
    body[7] = work
    body[8:104] = mask
    return _with_crc(bytes(body))


def mask_from_cells(cells) -> bytes:
    raw = bytearray(MASK_BYTES)
    for index in cells:
        if 0 <= index < PIXELS:
            raw[index >> 3] |= 1 << (index & 7)
    return bytes(raw)


def cells_from_mask(mask: bytes):
    cells = []
    for index in range(PIXELS):
        if mask[index >> 3] & (1 << (index & 7)):
            cells.append(index)
    return cells


@dataclass
class ThermalFrame:
    flags: int
    seq: int
    time_ms: int
    ta_cdeg: int
    vdd_cv: int
    emissivity_milli: int
    reflected_cdeg: int
    sentry_peak_cdeg: int
    sentry_cells: int
    sensitivity: int
    battery_pct: int
    work: int
    quiet_minutes: int
    event_age_s: int
    pixels: list = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return bool(self.flags & FLAG_COMPLETE)

    @property
    def event(self) -> bool:
        return bool(self.flags & FLAG_EVENT)

    @property
    def button(self) -> bool:
        return bool(self.flags & FLAG_BUTTON)

    @property
    def armed(self) -> bool:
        return bool(self.flags & FLAG_ARMED)

    @property
    def stored(self) -> bool:
        return bool(self.flags & FLAG_STORED)


@dataclass
class Hello:
    mac: str
    ee: bytes


@dataclass
class Settings:
    armed: bool
    sensitivity: int
    work: int
    mask: bytes


def _mac(raw: bytes) -> str:
    return ":".join(f"{b:02x}" for b in raw)


def parse_frame(body: bytes) -> ThermalFrame:
    if len(body) != FRAME_LEN or body[:4] != b"TL01":
        raise ValueError("not a frame")
    if crc16(body[:-2]) != struct.unpack_from("<H", body, FRAME_LEN - 2)[0]:
        raise ValueError("bad frame crc")
    version, flags, header, seq, time_ms = struct.unpack_from("<BBHII", body, 4)
    if version != 1 or header != FRAME_HEADER:
        raise ValueError("unexpected frame header")
    ta, vdd, emis, refl, peak, cells = struct.unpack_from("<hhHhhH", body, 16)
    sens, bat, work, quiet, age, _reserved = struct.unpack_from("<BBBBHH", body, 28)
    pixels = list(struct.unpack_from("<" + "h" * PIXELS, body, FRAME_HEADER))
    return ThermalFrame(
        flags, seq, time_ms, ta, vdd, emis, refl, peak, cells, sens, bat, work, quiet, age, pixels
    )


def parse_hello(body: bytes) -> Hello:
    if len(body) != HELLO_LEN or body[:4] != b"TL0H":
        raise ValueError("not a hello")
    if crc16(body[:-2]) != struct.unpack_from("<H", body, HELLO_LEN - 2)[0]:
        raise ValueError("bad hello crc")
    words = struct.unpack_from("<H", body, 11)[0]
    if words != HELLO_EE:
        raise ValueError("unexpected eeprom length")
    return Hello(_mac(body[5:11]), body[13 : 13 + HELLO_EE * 2])


def parse_settings(body: bytes) -> Settings:
    if len(body) != SETTINGS_LEN or body[:4] != b"TL0M":
        raise ValueError("not settings")
    if crc16(body[:-2]) != struct.unpack_from("<H", body, SETTINGS_LEN - 2)[0]:
        raise ValueError("bad settings crc")
    return Settings(bool(body[5]), body[6], body[7], bytes(body[8:104]))


class Parser:
    """Resync on magic. Drops a byte when the CRC does not match."""

    def __init__(self):
        self.buf = bytearray()

    def feed(self, data: bytes):
        self.buf.extend(data)
        found = []
        while True:
            item = self._pop()
            if item is None:
                break
            found.append(item)
        if len(self.buf) > 65536:
            del self.buf[:-8]
        return found

    def _pop(self):
        magics = (b"TL01", b"TL0H", b"TL0M")
        start = -1
        kind = None
        for i in range(len(self.buf) - 3):
            token = bytes(self.buf[i : i + 4])
            if token in magics:
                start = i
                kind = token
                break
        if start < 0:
            if len(self.buf) > 3:
                del self.buf[:-3]
            return None
        if start:
            del self.buf[:start]
        need = {b"TL01": FRAME_LEN, b"TL0H": HELLO_LEN, b"TL0M": SETTINGS_LEN}[kind]
        if len(self.buf) < need:
            return None
        blob = bytes(self.buf[:need])
        try:
            if kind == b"TL01":
                item = parse_frame(blob)
            elif kind == b"TL0H":
                item = parse_hello(blob)
            else:
                item = parse_settings(blob)
        except ValueError:
            del self.buf[0]
            return self._pop()
        del self.buf[:need]
        return item
