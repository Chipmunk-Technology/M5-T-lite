"""SQLite for named thermal memories, sentry events, and the sensor EEPROM copy."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS device (
    mac TEXT PRIMARY KEY,
    ee BLOB NOT NULL,
    seen_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS asset (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);
CREATE TABLE IF NOT EXISTS frame (
    id INTEGER PRIMARY KEY,
    asset_id INTEGER NOT NULL,
    mac TEXT,
    taken_at TEXT NOT NULL,
    seq INTEGER,
    time_ms INTEGER,
    ta_cdeg INTEGER,
    vdd_cv INTEGER,
    emissivity_milli INTEGER,
    reflected_cdeg INTEGER,
    material TEXT,
    distance TEXT,
    peak_cdeg INTEGER,
    pixels BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS event (
    id INTEGER PRIMARY KEY,
    mac TEXT,
    time_ms INTEGER,
    taken_at TEXT NOT NULL,
    peak_cdeg INTEGER,
    cells INTEGER,
    pixels BLOB NOT NULL,
    UNIQUE(mac, time_ms)
);
"""


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.executescript(SCHEMA)

    def close(self):
        self.conn.close()

    def save_eeprom(self, mac: str, ee: bytes):
        self.conn.execute(
            "INSERT INTO device(mac, ee, seen_at) VALUES(?, ?, ?) "
            "ON CONFLICT(mac) DO UPDATE SET ee=excluded.ee, seen_at=excluded.seen_at",
            (mac, ee, _now()),
        )
        self.conn.commit()

    def remember(self, name: str, mac: str, frame, material: str, distance: str) -> int:
        cur = self.conn.execute("INSERT OR IGNORE INTO asset(name) VALUES(?)", (name,))
        if cur.lastrowid:
            asset_id = cur.lastrowid
        else:
            asset_id = self.conn.execute("SELECT id FROM asset WHERE name=?", (name,)).fetchone()[0]
        peak = max(frame.pixels)
        blob = _blob(frame.pixels)
        row = self.conn.execute(
            "INSERT INTO frame(asset_id, mac, taken_at, seq, time_ms, ta_cdeg, vdd_cv, "
            "emissivity_milli, reflected_cdeg, material, distance, peak_cdeg, pixels) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                asset_id,
                mac,
                _now(),
                frame.seq,
                frame.time_ms,
                frame.ta_cdeg,
                frame.vdd_cv,
                frame.emissivity_milli,
                frame.reflected_cdeg,
                material,
                distance,
                peak,
                blob,
            ),
        )
        self.conn.commit()
        return row.lastrowid

    def previous(self, name: str):
        row = self.conn.execute(
            "SELECT pixels, peak_cdeg, material, distance, emissivity_milli, reflected_cdeg, "
            "ta_cdeg, mac, taken_at FROM frame f JOIN asset a ON a.id=f.asset_id "
            "WHERE a.name=? ORDER BY f.id DESC LIMIT 1",
            (name,),
        ).fetchone()
        if not row:
            return None
        pixels = list(_unblob(row[0]))
        return {
            "pixels": pixels,
            "peak": row[1],
            "material": row[2],
            "distance": row[3],
            "emissivity_milli": row[4],
            "reflected_cdeg": row[5],
            "ta_cdeg": row[6],
            "mac": row[7],
            "taken_at": row[8],
        }

    def add_event(self, mac: str, time_ms: int, peak: int, cells: int, pixels) -> bool:
        try:
            self.conn.execute(
                "INSERT INTO event(mac, time_ms, taken_at, peak_cdeg, cells, pixels) VALUES(?, ?, ?, ?, ?, ?)",
                (mac, time_ms, _now(), peak, cells, _blob(pixels)),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def events(self, limit: int = 30):
        rows = self.conn.execute(
            "SELECT id, taken_at, time_ms, peak_cdeg, cells, pixels FROM event ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {
                "id": row[0],
                "taken_at": row[1],
                "time_ms": row[2],
                "peak_cdeg": row[3],
                "cells": row[4],
                "pixels": list(_unblob(row[5])),
            }
            for row in rows
        ]

    def event(self, event_id: int):
        row = self.conn.execute(
            "SELECT id, taken_at, time_ms, peak_cdeg, cells, pixels FROM event WHERE id=?",
            (event_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "taken_at": row[1],
            "time_ms": row[2],
            "peak_cdeg": row[3],
            "cells": row[4],
            "pixels": list(_unblob(row[5])),
        }


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _blob(pixels) -> bytes:
    import struct

    return struct.pack("<" + "h" * len(pixels), *[int(v) for v in pixels])


def _unblob(blob: bytes):
    import struct

    count = len(blob) // 2
    return struct.unpack("<" + "h" * count, blob)
