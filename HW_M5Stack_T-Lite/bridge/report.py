"""CSV, a one-page print file, and a PDF when Edge or Chrome can print it."""

from __future__ import annotations

import base64
import shutil
import struct
import subprocess
import tempfile
import zlib
from pathlib import Path

from analyze import MATERIALS, cell_phrase, fmt_c

SCALE = 8
COOL = (239, 230, 214)
WARM = (107, 36, 16)
PAPER = (246, 241, 232)
MARK = (154, 52, 18)


def colorize(value: int, lo: int, hi: int):
    span = hi - lo
    t = 0.5 if span <= 0 else (value - lo) / span
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return tuple(int(a + (b - a) * t) for a, b in zip(COOL, WARM))


def thermal_png(pixels, marks=None, mask=None, lo=None, hi=None) -> bytes:
    marks = set(marks or [])
    mask = set(mask or [])
    if pixels:
        lo = min(pixels) if lo is None else lo
        hi = max(pixels) if hi is None else hi
    else:
        lo, hi = 0, 1
    width, height = 32 * SCALE, 24 * SCALE
    rgb = bytearray(width * height * 3)
    for i, value in enumerate(pixels):
        x, y = i % 32, i // 32
        color = colorize(value, lo, hi)
        if i in mask:
            color = tuple((c + p) // 2 for c, p in zip(color, PAPER))
        for dy in range(SCALE):
            for dx in range(SCALE):
                o = ((y * SCALE + dy) * width + (x * SCALE + dx)) * 3
                rgb[o : o + 3] = bytes(color)
    for i in marks:
        x, y = i % 32, i // 32
        _stroke(rgb, width, x, y, i, marks)
    return _png(width, height, rgb)


def _stroke(rgb, width, x, y, index, marks):
    def put(px, py):
        if 0 <= px < 32 * SCALE and 0 <= py < 24 * SCALE:
            o = (py * width + px) * 3
            rgb[o : o + 3] = bytes(MARK)

    if (index - 32) not in marks:
        for dx in range(SCALE):
            put(x * SCALE + dx, y * SCALE)
    if (index + 32) not in marks:
        for dx in range(SCALE):
            put(x * SCALE + dx, y * SCALE + SCALE - 1)
    if index % 32 == 0 or (index - 1) not in marks:
        for dy in range(SCALE):
            put(x * SCALE, y * SCALE + dy)
    if index % 32 == 31 or (index + 1) not in marks:
        for dy in range(SCALE):
            put(x * SCALE + SCALE - 1, y * SCALE + dy)


def _png(width, height, rgb: bytearray) -> bytes:
    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)
        raw.extend(rgb[y * stride : (y + 1) * stride])

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")


def csv_bytes(state: dict) -> bytes:
    pixels = state.get("pixels") or []
    material = MATERIALS.get(state.get("material"), ("", None))[0]
    emis = state.get("emissivity_milli")
    lines = [
        "欄位,值",
        f"句子,{_csv(state.get('sentence') or '')}",
        f"數字,{_csv(state.get('number') or '')}",
        f"單位,{_csv(state.get('unit') or '')}",
        f"材料,{material}",
        f"發射率,{'' if emis is None else emis / 1000:.3f}",
        f"反射溫度_C,{'' if state.get('reflected_cdeg') is None else fmt_c(state['reflected_cdeg'])}",
        f"距離,{_csv(cell_phrase(state.get('distance') or 'hand'))}",
        f"裝置,{_csv(state.get('mac') or '')}",
        "聲明,篩查用，非計量追溯",
        f"環境溫度_C,{'' if state.get('ta_cdeg') is None else fmt_c(state['ta_cdeg'])}",
    ]
    lines.append("像素_0.01C," + ",".join(str(int(v)) for v in pixels))
    return ("\ufeff" + "\n".join(lines) + "\n").encode("utf-8")


def _csv(text: str) -> str:
    if any(ch in text for ch in ",\"\n"):
        return '"' + text.replace('"', '""') + '"'
    return text


def report_html(state: dict) -> str:
    pixels = state.get("pixels") or [0] * 768
    png = thermal_png(pixels, state.get("marks"), state.get("mask"))
    image = base64.b64encode(png).decode("ascii")
    material_name, emis = MATERIALS.get(state.get("material"), ("", None))
    emis_text = "沒有可靠的發射率" if emis is None else f"{emis / 1000:.2f}"
    reflected = state.get("reflected_cdeg")
    reflected_text = "等於感測器環境溫度" if reflected is None else f"{fmt_c(reflected)}°C"
    number = state.get("number") or ""
    unit = state.get("unit") or ""
    number_html = f"{number} {unit}".strip() or "—"
    mac = state.get("mac") or "尚未讀到"
    small = "、".join(
        [
            material_name,
            f"發射率 {emis_text}",
            f"反射溫度 {reflected_text}",
            cell_phrase(state.get("distance") or "hand"),
            f"裝置 {mac}",
            "篩查用，非計量追溯",
        ]
    )
    sentence = state.get("sentence") or ""
    return f"""<!DOCTYPE html>
<html lang="zh-Hant"><head><meta charset="utf-8"><title>熱記憶</title>
<style>
  body {{ margin: 24px; background: #f6f1e8; color: #1c1915; font-family: "Microsoft JhengHei", "PingFang TC", sans-serif; }}
  h1 {{ font-size: 28px; font-weight: 600; margin: 0 0 12px; }}
  .num {{ font-size: 56px; margin: 0 0 16px; }}
  img {{ width: 420px; height: auto; image-rendering: pixelated; }}
  p {{ font-size: 14px; line-height: 1.5; max-width: 420px; }}
</style></head>
<body>
  <h1>{_html(sentence)}</h1>
  <p class="num">{_html(number_html)}</p>
  <img alt="顯示放大 · 32×24" src="data:image/png;base64,{image}">
  <p>顯示放大 · 32×24</p>
  <p>{_html(small)}</p>
</body></html>"""


def _html(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def find_browser() -> str | None:
    candidates = [
        shutil.which("msedge"),
        shutil.which("chrome"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    ]
    for path in candidates:
        if path and Path(path).exists():
            return path
    return None


def html_to_pdf(html: str) -> bytes | None:
    browser = find_browser()
    if not browser:
        return None
    with tempfile.TemporaryDirectory() as folder:
        src = Path(folder) / "report.html"
        dst = Path(folder) / "report.pdf"
        src.write_text(html, encoding="utf-8")
        try:
            subprocess.run(
                [
                    browser,
                    "--headless=new",
                    "--disable-gpu",
                    "--no-first-run",
                    f"--user-data-dir={folder}/profile",
                    f"--print-to-pdf={dst}",
                    src.as_uri(),
                ],
                check=False,
                timeout=30,
                capture_output=True,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if dst.exists() and dst.stat().st_size > 0:
            return dst.read_bytes()
    return None
