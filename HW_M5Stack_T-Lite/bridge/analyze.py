"""Sentences, steadiness, and leak marks. The device still decides the beep."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

PIXELS = 768
WIDTH = 32
HEIGHT = 24

# One horizontal cell is about 8.9% of the distance (110° FOV, 32 columns).
CELL_FRACTION = 2.0 * math.tan(math.radians(55.0)) / WIDTH

DISTANCES = {
    "near": ("貼近", 0.05),
    "hand": ("一手距離", 0.30),
    "room": ("房間", 2.0),
}

MATERIALS = {
    "plastic": ("塑膠", 950),
    "painted": ("塗裝金屬", 920),
    "pcb": ("電路板", 950),
    "water": ("水", 960),
    "shiny": ("光亮金屬", None),
}

# Motion gate for 「請握穩」. Design value, not a measured noise floor.
STEADY_MAD_CDEG = 40
STEADY_SECONDS = 2.0
LEAK_CDEG = 1000
LEAK_MIN_CELLS = 4


def fmt_c(cdeg: int) -> str:
    value = cdeg / 100.0
    rounded = round(value)
    if abs(value - rounded) < 0.05:
        return str(int(rounded))
    return f"{value:.1f}"


def cell_phrase(distance_key: str) -> str:
    mm = CELL_FRACTION * DISTANCES[distance_key][1] * 1000.0
    if mm < 10:
        size = f"{mm:.1f} 毫米"
    else:
        cm = mm / 10.0
        size = f"{round(cm)} 公分" if cm >= 10 else f"{cm:.1f} 公分"
    return f"{DISTANCES[distance_key][0]}。這一格大約 {size}寬"


def peak(pixels) -> int:
    return max(pixels) if pixels else 0


@dataclass
class Sentence:
    text: str
    number: str
    unit: str
    emphasis: bool = False
    small: str = ""
    status: str = "live"


class Stability:
    def __init__(self):
        self.prev = None
        self.calm_since = None
        self.best = None
        self.best_mad = 10**9
        self.mad = 0.0

    def push(self, pixels, now: float):
        if self.prev is not None:
            mad = sum(abs(a - b) for a, b in zip(pixels, self.prev)) / len(pixels)
            self.mad = mad
            if mad > STEADY_MAD_CDEG:
                self.calm_since = None
                self.best = None
                self.best_mad = 10**9
            else:
                if self.calm_since is None:
                    self.calm_since = now
                if mad < self.best_mad:
                    self.best_mad = mad
                    self.best = list(pixels)
        self.prev = list(pixels)

    def steady(self, now: float) -> bool:
        return (
            self.calm_since is not None
            and now - self.calm_since >= STEADY_SECONDS
            and self.best is not None
        )

    def moving(self) -> bool:
        return self.prev is not None and self.mad > STEADY_MAD_CDEG


def memory_sentence(name: str, live, previous, shiny: bool, distance_key: str, steady: bool, moving: bool, just_saved: bool) -> Sentence:
    small = cell_phrase(distance_key)
    if shiny:
        return Sentence("這個表面讀數不可靠。", "", "", False, "篩查用，非計量追溯", "shiny")
    if just_saved and name:
        return Sentence(f"已記住{name}。", "", "", False, small, "saved")
    if moving:
        return Sentence("請握穩。", "", "", False, small, "shake")
    if distance_key == "room" and previous is None:
        return Sentence("再靠近。這一格蓋住的範圍太大。", "", "", False, small, "closer")
    if not name:
        return Sentence("對準要記住的地方。", "", "", False, small, "need-name")
    now_peak = peak(live)
    if previous is None:
        return Sentence(f"已看到{name}，最高 {fmt_c(now_peak)}°C。", fmt_c(now_peak), "°C", False, small, "seen")
    delta = now_peak - peak(previous)
    if abs(delta) < 50:
        return Sentence(f"{name}和上次差不多。", "0", "°C", False, small, "same")
    hotter = delta > 0
    word = "高" if hotter else "低"
    shown = abs(delta)
    return Sentence(
        f"{name}比上次{word} {fmt_c(shown)}°C。",
        fmt_c(shown),
        "°C",
        hotter,
        small,
        "hotter" if hotter else "cooler",
    )


def _neighbors(index: int):
    x, y = index % WIDTH, index // WIDTH
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            xx, yy = x + dx, y + dy
            if 0 <= xx < WIDTH and 0 <= yy < HEIGHT:
                yield yy * WIDTH + xx


def _local_delta(pixels, index: int) -> int:
    # A wide window, so a two-pixel pipe is compared with the wall around it
    # rather than with itself.
    x, y = index % WIDTH, index // WIDTH
    around = []
    for yy in range(max(0, y - 5), min(HEIGHT, y + 6)):
        for xx in range(max(0, x - 5), min(WIDTH, x + 6)):
            if xx == x and yy == y:
                continue
            around.append(pixels[yy * WIDTH + xx])
    if not around:
        return 0
    around.sort()
    median = around[len(around) // 2]
    return pixels[index] - median


def leak_marks(pixels):
    strong = []
    for i in range(PIXELS):
        if abs(_local_delta(pixels, i)) >= LEAK_CDEG:
            strong.append(i)
    if not strong:
        return None
    remaining = set(strong)
    best = None
    while remaining:
        start = remaining.pop()
        stack = [start]
        comp = [start]
        while stack:
            cur = stack.pop()
            for nxt in _neighbors(cur):
                if nxt in remaining:
                    remaining.remove(nxt)
                    stack.append(nxt)
                    comp.append(nxt)
        if len(comp) < LEAK_MIN_CELLS:
            continue
        mean = sum(_local_delta(pixels, i) for i in comp) / len(comp)
        if abs(mean) < LEAK_CDEG:
            continue
        if best is None or abs(mean) > abs(best[0]):
            best = (mean, comp)
    if best is None:
        return None
    mean, comp = best
    xs = [i % WIDTH for i in comp]
    ys = [i // WIDTH for i in comp]
    w = max(xs) - min(xs) + 1
    h = max(ys) - min(ys) + 1
    thin = min(w, h) <= 3 and max(w, h) / max(1, min(w, h)) >= 2.5
    touches_edge = min(xs) == 0 or max(xs) == WIDTH - 1 or min(ys) == 0 or max(ys) == HEIGHT - 1
    kind = "pipe" if thin and not touches_edge else "seam"
    return {"delta": int(round(mean)), "cells": comp, "kind": kind}


def leak_sentence(pixels, distance_key: str) -> tuple:
    small = cell_phrase(distance_key)
    found = leak_marks(pixels)
    if not found:
        return Sentence("現在溫差不夠。", "", "", False, small, "leak-quiet"), []
    shown = abs(found["delta"])
    colder = found["delta"] < 0
    if found["kind"] == "pipe":
        word = "較冷" if colder else "較熱"
        text = f"牆後可能有一段{word}的管路。"
        small = "可能。" + small
        status = "pipe"
    else:
        word = "低" if colder else "高"
        text = f"這條縫比牆面{word} {fmt_c(shown)}°C。"
        status = "seam"
    return Sentence(text, fmt_c(shown), "°C", not colder, small, status), found["cells"]


@dataclass
class SentryView:
    armed: bool = False
    sensitivity: int = 1
    last_event_ms: int | None = None
    last_peak: int = 0
    last_cells: int = 0
    host_now_ms: int = 0


def sentry_sentence(view: SentryView, now_ms: int) -> Sentence:
    if not view.armed:
        return Sentence("守候中。", "", "", False, "還沒開始守候。", "sentry-off")
    if view.last_event_ms is None:
        minutes = max(0, (now_ms - view.host_now_ms) // 60000) if view.host_now_ms else 0
        if minutes <= 0:
            return Sentence("守候中。", "", "", False, "這些設定留在裝置上。", "sentry")
        return Sentence("守候中。", str(minutes), "分鐘", False, "這些設定留在裝置上。", "sentry")
    age_s = max(0, (now_ms - view.last_event_ms) // 1000)
    small = f"比背景高 {fmt_c(view.last_peak)}°C，{view.last_cells} 格。"
    if age_s < 60:
        return Sentence("剛剛有暖物經過。", "", "", True, small, "passed")
    minutes = max(1, age_s // 60)
    return Sentence(f"{minutes} 分鐘前有暖物經過。", str(minutes), "分鐘", True, small, "passed")


# Device sentry constants, duplicated so the demo page can show the same gates.
SENTRY_TAU_S = 30.0
SENTRY_FAST_TAU_S = 3.0
SENTRY_QUIET_S = 10.0
SENTRY_GATES = {0: (200, 2), 1: (300, 3), 2: (500, 3)}


@dataclass
class SentryTwin:
    """Same thresholds as the firmware. Used by the demo and by tests, not by the beep."""

    sensitivity: int = 1
    mask: set = field(default_factory=set)
    armed: bool = True
    background: list | None = None
    run: list = field(default_factory=lambda: [0] * PIXELS)
    fast: list = field(default_factory=lambda: [0] * PIXELS)
    last_t: float | None = None
    quiet_until: float = 0.0
    last_event: dict | None = None

    def step(self, pixels, now: float):
        gate, need = SENTRY_GATES.get(self.sensitivity, SENTRY_GATES[1])
        if self.background is None:
            self.background = list(pixels)
            self.last_t = now
            return None
        dt = 0.25 if self.last_t is None else min(2.0, max(0.0, now - self.last_t))
        self.last_t = now
        fired = []
        peak_delta = 0
        for i, temp in enumerate(pixels):
            tau = SENTRY_FAST_TAU_S if self.fast[i] else SENTRY_TAU_S
            alpha = min(0.5, max(0.0, 1.0 - math.exp(-dt / tau)))
            delta = int(round(temp - self.background[i]))
            self.background[i] += alpha * (temp - self.background[i])
            if i not in self.mask and delta >= gate:
                self.run[i] = min(250, self.run[i] + 1)
            else:
                self.run[i] = 0
            if self.run[i] >= need:
                fired.append(i)
                peak_delta = max(peak_delta, delta)
            if self.fast[i] and now >= self.quiet_until:
                self.fast[i] = 0
        if self.armed and now >= self.quiet_until and fired:
            self.quiet_until = now + SENTRY_QUIET_S
            self.last_event = {"peak": peak_delta, "cells": len(fired), "at": now}
            for i in fired:
                self.fast[i] = 1
                self.run[i] = 0
            return self.last_event
        return None
