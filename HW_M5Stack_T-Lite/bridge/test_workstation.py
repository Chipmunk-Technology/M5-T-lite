import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import analyze
import protocol
import report
import store
from server import Hub


def frame(pixels, **kwargs):
    base = dict(
        flags=protocol.FLAG_COMPLETE,
        seq=1,
        time_ms=1000,
        ta_cdeg=2500,
        vdd_cv=330,
        emissivity_milli=950,
        reflected_cdeg=2500,
        sentry_peak_cdeg=0,
        sentry_cells=0,
        sensitivity=1,
        battery_pct=80,
        work=0,
        quiet_minutes=255,
        event_age_s=0xFFFF,
        pixels=pixels,
    )
    base.update(kwargs)
    return protocol.ThermalFrame(**base)


class ProtocolTest(unittest.TestCase):
    def test_frame_roundtrip_with_noise(self):
        pixels = [2000 + (i % 17) for i in range(768)]
        raw = b"\x00\xff" + protocol.pack_frame(frame(pixels, flags=protocol.FLAG_COMPLETE | protocol.FLAG_BUTTON))
        parser = protocol.Parser()
        items = parser.feed(raw[:20]) + parser.feed(raw[20:])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].pixels, pixels)
        self.assertTrue(items[0].button)

    def test_hello_and_settings(self):
        ee = bytes([i % 256 for i in range(832 * 2)])
        hello = protocol.parse_hello(protocol.pack_hello(bytes.fromhex("c88541688770"), ee))
        self.assertEqual(hello.mac, "c8:85:41:68:87:70")
        self.assertEqual(hello.ee, ee)
        mask = protocol.mask_from_cells([0, 9, 767])
        settings = protocol.parse_settings(protocol.pack_settings(True, 2, 2, mask))
        self.assertEqual(protocol.cells_from_mask(settings.mask), [0, 9, 767])
        self.assertTrue(settings.armed)
        self.assertEqual(settings.sensitivity, 2)

    def test_command_crc(self):
        blob = protocol.pack_text("守候中。", True)
        self.assertEqual(blob[:4], b"TL0C")
        self.assertEqual(protocol.crc16(blob[:-2]), int.from_bytes(blob[-2:], "little"))


class AnalyzeTest(unittest.TestCase):
    def test_shake_and_compare(self):
        live = [3000] * 768
        live[10] = 4200
        previous = [3000] * 768
        sentence = analyze.memory_sentence("左接點", live, previous, False, "hand", True, False, False)
        self.assertIn("比上次高", sentence.text)
        self.assertEqual(sentence.number, "12")
        self.assertTrue(sentence.emphasis)
        shaky = analyze.memory_sentence("左接點", live, previous, False, "hand", False, True, False)
        self.assertEqual(shaky.text, "請握穩。")
        shiny = analyze.memory_sentence("左接點", live, previous, True, "hand", True, False, False)
        self.assertEqual(shiny.text, "這個表面讀數不可靠。")
        self.assertEqual(shiny.number, "")
        closer = analyze.memory_sentence("窗縫", live, None, False, "room", True, False, False)
        self.assertEqual(closer.text, "再靠近。這一格蓋住的範圍太大。")

    def test_steady_window(self):
        stable = analyze.Stability()
        pixels = [2500] * 768
        stable.push(pixels, 0)
        stable.push(pixels, 0.5)
        self.assertFalse(stable.steady(1.0))
        stable.push(pixels, 2.6)
        self.assertTrue(stable.steady(2.6))
        jumped = [4000] * 768
        stable.push(jumped, 3.0)
        self.assertTrue(stable.moving())
        self.assertFalse(stable.steady(5.0))

    def test_leak_quiet_and_pipe(self):
        flat = [2500] * 768
        sentence, marks = analyze.leak_sentence(flat, "room")
        self.assertEqual(sentence.text, "現在溫差不夠。")
        self.assertEqual(marks, [])
        pixels = [2500] * 768
        for y in range(4, 19):
            for x in (20, 21):
                pixels[y * 32 + x] = 1000
        sentence, marks = analyze.leak_sentence(pixels, "room")
        self.assertIn("可能", sentence.text)
        self.assertGreaterEqual(len(marks), 4)
        self.assertIn("18 公分", sentence.small)

    def test_cell_sizes(self):
        self.assertIn("4.5 毫米", analyze.cell_phrase("near"))
        self.assertIn("2.7 公分", analyze.cell_phrase("hand"))

    def test_sentry_quiet_then_fire(self):
        twin = analyze.SentryTwin(sensitivity=1, armed=True)
        base = [2000] * 768
        self.assertIsNone(twin.step(base, 0))
        hot = base[:]
        hot[0] = 2000 + 400
        self.assertIsNone(twin.step(hot, 0.25))
        self.assertIsNone(twin.step(hot, 0.50))
        hit = twin.step(hot, 0.75)
        self.assertIsNotNone(hit)
        self.assertGreaterEqual(hit["peak"], 300)
        self.assertIsNone(twin.step(hot, 1.0))


class StoreTest(unittest.TestCase):
    def test_remember_and_report(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        db = store.Store(Path(folder.name) / "t.sqlite")
        self.addCleanup(db.close)
        hub = Hub(db, demo=True)
        hub.link = "live"
        hub.name = "左接點"
        pixels = [2100] * 768
        hub.stability.push(pixels, 0)
        hub.stability.push(pixels, 1)
        hub.stability.push(pixels, 2.2)
        hub.pixels = pixels
        hub.command({"op": "remember"})
        saved = db.previous("左接點")
        self.assertIsNotNone(saved)
        self.assertEqual(saved["pixels"][0], 2100)
        view = hub.snapshot()
        self.assertIn("已記住左接點", view["sentence"])
        blob = report.csv_bytes(view)
        self.assertIn("篩查用，非計量追溯".encode("utf-8"), blob)
        self.assertTrue(report.thermal_png(pixels).startswith(b"\x89PNG"))


if __name__ == "__main__":
    unittest.main()
