"""Count warm blobs in a 32×24 frame. This does not identify anyone."""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field

WIDTH = 32
HEIGHT = 24
PIXELS = WIDTH * HEIGHT

CELL_FRACTION = 2.0 * math.tan(math.radians(55.0)) / WIDTH

DISTANCES = {
    "near": ("貼近", 0.05),
    "hand": ("一手距離", 0.30),
    "room": ("房間", 2.0),
}

# Heat above background (°C/100), rise versus the lagged frame, consecutive samples.
GATES = {0: (200, 60, 2), 1: (300, 80, 3), 2: (500, 150, 3)}
MIN_CELLS = {"hand": 12, "room": 4}

TAU_S = 30.0
TAU_LEARN_S = 1.0
LEARN_S = 3.0
# Factory firmware updates one checkerboard subpage per read. Compare with a
# frame old enough that both halves have been refreshed.
MOTION_LAG_S = 0.45
RESET_GAP_S = 2.0
HISTORY_S = 2.0


def cell_phrase(distance_key: str) -> str:
    mm = CELL_FRACTION * DISTANCES[distance_key][1] * 1000.0
    if mm < 10:
        size = f"{mm:.1f} 毫米"
    else:
        cm = mm / 10.0
        size = f"{round(cm)} 公分" if cm >= 10 else f"{cm:.1f} 公分"
    return f"{DISTANCES[distance_key][0]}。這一格大約 {size}寬"


def _neighbors(index: int):
    x = index % WIDTH
    y = index // WIDTH
    if y > 0:
        yield index - WIDTH
    if y < HEIGHT - 1:
        yield index + WIDTH
    if x > 0:
        yield index - 1
    if x < WIDTH - 1:
        yield index + 1


def components(foreground: list[bool]) -> list[list[int]]:
    seen = [False] * PIXELS
    found = []
    for start, on in enumerate(foreground):
        if not on or seen[start]:
            continue
        stack = [start]
        seen[start] = True
        cells = []
        while stack:
            index = stack.pop()
            cells.append(index)
            for nxt in _neighbors(index):
                if foreground[nxt] and not seen[nxt]:
                    seen[nxt] = True
                    stack.append(nxt)
        found.append(cells)
    return found


@dataclass
class Presence:
    text: str
    number: str
    unit: str
    small: str
    status: str
    marks: list[int] = field(default_factory=list)
    count: int = 0


class Counter:
    def __init__(self):
        self.reset()

    def reset(self):
        self.background = None
        self.hot_run = [0] * PIXELS
        self.seen_motion = [0] * PIXELS
        self.prev_blobs: list[set[int]] = []
        self.history = deque()
        self.learn_until = None
        self.last_t = None

    def step(self, pixels, now: float, mask, sensitivity: int, distance: str) -> Presence:
        if len(pixels) != PIXELS:
            raise ValueError("frame must be 768 cells")
        small = cell_phrase(distance if distance in DISTANCES else "room")
        if distance == "near":
            self._track(pixels, now, mask, sensitivity, "room", count_blobs=False)
            return Presence(
                "再退開。這一格蓋住的範圍太小。",
                "",
                "",
                small,
                "near",
            )
        counted = self._track(pixels, now, mask, sensitivity, distance, count_blobs=True)
        note = "這是暖塊，靠在一起會合成一個。篩查用，非計量追溯。"
        if mask:
            note = "這些格子不算。" + note
        if self.learn_until is not None and now < self.learn_until:
            return Presence(
                "正在看這個空間平常的溫度。",
                "",
                "",
                small + "。開始時已經在畫面裡的人，要動一下才算。",
                "learn",
            )
        if not counted:
            return Presence(
                "視野裡現在沒有夠大的暖塊。",
                "0",
                "人",
                small + "。" + note,
                "empty",
            )
        count = len(counted)
        marks = [cell for blob in counted for cell in blob]
        return Presence(
            f"視野裡大約 {count} 人。",
            str(count),
            "人",
            small + "。" + note,
            "count",
            marks,
            count,
        )

    def _track(self, pixels, now: float, mask, sensitivity: int, distance: str, count_blobs: bool):
        heat, motion, need = GATES.get(sensitivity, GATES[1])
        ignored = set(mask)
        minimum = MIN_CELLS.get(distance, MIN_CELLS["room"])
        if self.last_t is not None and now - self.last_t > RESET_GAP_S:
            self.reset()
        if self.background is None:
            self.background = list(pixels)
            self.learn_until = now + LEARN_S
            self.last_t = now
            self.history.append((now, list(pixels)))
            return []
        dt = min(RESET_GAP_S, max(0.0, now - self.last_t))
        self.last_t = now
        lagged = self._lagged(now)
        learning = now < self.learn_until
        foreground = [False] * PIXELS
        for i, temp in enumerate(pixels):
            if i in ignored:
                self.hot_run[i] = 0
                self.seen_motion[i] = 0
                continue
            delta = temp - self.background[i]
            if delta >= heat:
                self.hot_run[i] = min(250, self.hot_run[i] + 1)
            else:
                self.hot_run[i] = 0
                self.seen_motion[i] = 0
            if lagged is not None and temp - lagged[i] >= motion:
                self.seen_motion[i] = 1
            if self.hot_run[i] >= need:
                foreground[i] = True
        counted = []
        if count_blobs and not learning:
            for cells in components(foreground):
                if len(cells) < minimum:
                    continue
                blob = set(cells)
                moved = any(self.seen_motion[i] for i in cells)
                held = any(blob & old for old in self.prev_blobs)
                if moved or held:
                    counted.append(cells)
        frozen = {cell for blob in counted for cell in blob}
        tau = TAU_LEARN_S if learning else TAU_S
        alpha = 0.0 if tau <= 0 else min(0.5, 1.0 - math.exp(-dt / tau))
        if alpha:
            for i, temp in enumerate(pixels):
                if i in frozen:
                    continue
                self.background[i] += alpha * (temp - self.background[i])
        self.prev_blobs = [set(blob) for blob in counted] if not learning else []
        self.history.append((now, list(pixels)))
        while self.history and now - self.history[0][0] > HISTORY_S:
            self.history.popleft()
        return counted

    def _lagged(self, now: float):
        chosen = None
        for stamp, frame in self.history:
            if now - stamp >= MOTION_LAG_S:
                chosen = frame
            else:
                break
        return chosen


def fmt_spot(cdeg: int) -> str:
    return f"{cdeg / 100.0:.1f}"


def spot_reading(pixels, device_highest, mask) -> Presence:
    """The same hottest point the factory screen marks. Surface temperature only."""
    if len(pixels) != PIXELS:
        raise ValueError("frame must be 768 cells")
    ignored = {i for i in mask if 0 <= i < PIXELS}
    candidates = [i for i in range(PIXELS) if i not in ignored] or list(range(PIXELS))
    if device_highest is not None and not ignored:
        spot = min(candidates, key=lambda i: (abs(pixels[i] - device_highest), -pixels[i]))
        shown = int(device_highest)
    else:
        spot = max(candidates, key=lambda i: pixels[i])
        shown = pixels[spot]
    small = "十字對準的就是裝置上的最高溫。這是表面溫度，不是體溫計。"
    if ignored:
        small = "這些格子不算。" + small
    return Presence(
        f"最熱的一點是 {fmt_spot(shown)}°C。",
        fmt_spot(shown),
        "°C",
        small,
        "spot",
        [spot],
    )


# 0 is strict, 100 is sensitive. The page slider starts where a person walking past can beep.
DEFAULT_SENSITIVITY = 70
DEFAULT_INTERVAL_MS = 4000
MAX_INTERVAL_MS = 10000
FLOW_LAG_S = 0.9
FLOW_RELEASE_S = 1.5


def clamp_sensitivity(value) -> int:
    try:
        level = int(value)
    except (TypeError, ValueError):
        return DEFAULT_SENSITIVITY
    return max(0, min(100, level))


def clamp_interval(value) -> int:
    try:
        level = int(value)
    except (TypeError, ValueError):
        return DEFAULT_INTERVAL_MS
    return max(0, min(MAX_INTERVAL_MS, level))


def flow_limits(sensitivity: int):
    t = clamp_sensitivity(sensitivity) / 100.0
    return {
        "heat": int(round(350 - 250 * t)),
        "shift": 7.0 - 5.0 * t,
        "overlap": 0.35 + 0.55 * t,
        "margin": int(round(220 - 100 * t)),
        "min_cells": 8 - int(5 * t),
        "confirm": 1 if t >= 0.5 else 2,
    }


def _warm_blob(pixels, ignored, margin, min_cells):
    usable = [pixels[index] for index in range(PIXELS) if index not in ignored]
    if not usable:
        return None
    ordered = sorted(usable)
    floor = ordered[len(ordered) // 2] + margin
    foreground = [index not in ignored and pixels[index] >= floor for index in range(PIXELS)]
    blobs = components(foreground)
    if not blobs:
        return None
    cells = max(blobs, key=len)
    if len(cells) < min_cells:
        return None
    sx = sum(index % WIDTH for index in cells)
    sy = sum(index // WIDTH for index in cells)
    peak = max(pixels[index] for index in cells)
    return sx / len(cells), sy / len(cells), peak, set(cells)


class Flow:
    def __init__(self):
        self.history = deque()
        self.last_buzz = None
        self.held = False
        self.streak = 0
        self.clear_since = None

    def step(
        self,
        pixels,
        now: float,
        mask,
        sensitivity: int = DEFAULT_SENSITIVITY,
        interval_ms: int = DEFAULT_INTERVAL_MS,
    ) -> bool:
        limits = flow_limits(sensitivity)
        interval_s = clamp_interval(interval_ms) / 1000.0
        release_s = min(FLOW_RELEASE_S, interval_s)
        self.history.append((now, list(pixels)))
        while self.history and now - self.history[0][0] > HISTORY_S:
            self.history.popleft()
        lagged = None
        for stamp, frame in self.history:
            if now - stamp >= FLOW_LAG_S:
                lagged = frame
            else:
                break
        both = False
        if lagged is not None:
            ignored = {i for i in mask if 0 <= i < PIXELS}
            now_blob = _warm_blob(pixels, ignored, limits["margin"], limits["min_cells"])
            old_blob = _warm_blob(lagged, ignored, limits["margin"], limits["min_cells"])
            if now_blob is not None and old_blob is not None:
                dx = now_blob[0] - old_blob[0]
                dy = now_blob[1] - old_blob[1]
                shared = len(now_blob[3] & old_blob[3])
                overlap = shared / min(len(now_blob[3]), len(old_blob[3]))
                heat = abs(now_blob[2] - old_blob[2]) >= limits["heat"]
                flow = math.hypot(dx, dy) >= limits["shift"] and overlap <= limits["overlap"]
                both = heat and flow
        if not both:
            self.streak = 0
            if release_s <= 0:
                self.held = False
                self.clear_since = None
                return False
            if self.clear_since is None:
                self.clear_since = now
            elif now - self.clear_since >= release_s:
                self.held = False
            return False
        self.clear_since = None
        self.streak += 1
        if self.held or self.streak < limits["confirm"]:
            return False
        if self.last_buzz is not None and now - self.last_buzz < interval_s:
            return False
        self.held = True
        self.last_buzz = now
        return True
