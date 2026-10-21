"""Counter and factory JSON parsing. No device required."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import count
import server


def room(temp=2200):
    return [temp] * count.PIXELS


def paint(pixels, x, y, w, h, temp):
    out = list(pixels)
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            out[yy * count.WIDTH + xx] = temp
    return out


def feed(counter, pixels, t0, steps, dt=0.25, mask=(), sensitivity=1, distance="room"):
    view = None
    for i in range(steps):
        view = counter.step(pixels, t0 + i * dt, mask, sensitivity, distance)
    return view


class CountTest(unittest.TestCase):
    def test_empty_room_stays_zero(self):
        counter = count.Counter()
        view = feed(counter, room(), 0.0, 20)
        self.assertEqual(view.status, "empty")
        self.assertEqual(view.count, 0)
        self.assertEqual(view.number, "0")

    def test_person_already_there_is_not_counted_until_they_move(self):
        stayed = paint(room(), 6, 8, 3, 5, 3200)
        counter = count.Counter()
        view = feed(counter, stayed, 0.0, 20)
        self.assertEqual(view.count, 0)

    def test_walk_in_then_stand_still(self):
        counter = count.Counter()
        feed(counter, room(), 0.0, 13)
        arrived = paint(room(), 6, 8, 3, 5, 3200)
        view = feed(counter, arrived, 3.0, 4)
        self.assertEqual(view.count, 1)
        self.assertEqual(view.text, "視野裡大約 1 人。")
        view = feed(counter, arrived, 4.0, 10)
        self.assertEqual(view.count, 1)
        self.assertTrue(view.marks)

    def test_two_separate_blobs_and_one_merged_blob(self):
        counter = count.Counter()
        feed(counter, room(), 0.0, 13)
        two = paint(room(), 2, 4, 3, 5, 3200)
        two = paint(two, 24, 16, 3, 4, 3300)
        view = feed(counter, two, 3.0, 4)
        self.assertEqual(view.count, 2)
        merged = paint(room(), 8, 10, 8, 3, 3200)
        counter = count.Counter()
        feed(counter, room(), 0.0, 13)
        view = feed(counter, merged, 3.0, 4)
        self.assertEqual(view.count, 1)

    def test_masked_heater_is_ignored(self):
        counter = count.Counter()
        feed(counter, room(), 0.0, 13)
        hot = paint(room(), 4, 4, 4, 4, 4000)
        mask = [yy * 32 + xx for yy in range(4, 8) for xx in range(4, 8)]
        view = feed(counter, hot, 3.0, 6, mask=mask)
        self.assertEqual(view.count, 0)
        self.assertIn("這些格子不算。", view.small)

    def test_slow_heater_does_not_become_a_person(self):
        counter = count.Counter()
        feed(counter, room(), 0.0, 13)
        view = None
        for i in range(80):
            temp = 2200 + i * 20
            view = counter.step(paint(room(), 10, 10, 4, 4, temp), 3.0 + i * 0.25, [], 1, "room")
        self.assertEqual(view.count, 0)

    def test_near_distance_refuses_a_count(self):
        counter = count.Counter()
        hot = paint(room(), 6, 8, 6, 6, 3400)
        view = feed(counter, hot, 0.0, 20, distance="near")
        self.assertEqual(view.status, "near")
        self.assertEqual(view.number, "")
        self.assertIn("再退開", view.text)

    def test_gap_restarts_learning(self):
        counter = count.Counter()
        feed(counter, room(), 0.0, 16)
        view = counter.step(room(), 20.0, [], 1, "room")
        self.assertEqual(view.status, "learn")


class SpotTest(unittest.TestCase):
    def test_number_is_the_device_highest_point(self):
        pixels = room(2200)
        pixels[8 * 32 + 10] = 3456
        view = count.spot_reading(pixels, 3450, [])
        self.assertEqual(view.number, "34.5")
        self.assertEqual(view.unit, "°C")
        self.assertEqual(view.marks, [8 * 32 + 10])
        self.assertIn("表面溫度", view.small)

    def test_mask_skips_a_hotter_heater(self):
        pixels = room(2200)
        pixels[2 * 32 + 2] = 5000
        pixels[12 * 32 + 16] = 3300
        view = count.spot_reading(pixels, 5000, [2 * 32 + 2])
        self.assertEqual(view.marks, [12 * 32 + 16])
        self.assertEqual(view.number, "33.0")


def warm_patch(x, y, temp):
    pixels = room(2200)
    for dy in range(4):
        for dx in range(4):
            pixels[(y + dy) * 32 + (x + dx)] = temp
    return pixels


class FlowTest(unittest.TestCase):
    def test_beeps_only_when_the_warm_patch_moves_and_changes_heat(self):
        flow = count.Flow()
        flow.step(warm_patch(2, 4, 3000), 0.0, [])
        self.assertTrue(flow.step(warm_patch(8, 4, 3300), 1.0, []))
        self.assertFalse(flow.step(warm_patch(14, 4, 3600), 1.4, []))

    def test_interval_blocks_a_second_beep_until_it_elapses(self):
        blocked = count.Flow()
        blocked.step(warm_patch(2, 4, 3000), 0.0, [], 70, 5000)
        self.assertTrue(blocked.step(warm_patch(10, 4, 3400), 1.0, [], 70, 5000))
        blocked.step(warm_patch(10, 4, 3400), 2.0, [], 70, 5000)
        blocked.step(warm_patch(10, 4, 3400), 3.6, [], 70, 5000)
        self.assertFalse(blocked.step(warm_patch(2, 4, 2800), 4.6, [], 70, 5000))
        ready = count.Flow()
        ready.step(warm_patch(2, 4, 3000), 0.0, [], 70, 0)
        self.assertTrue(ready.step(warm_patch(10, 4, 3400), 1.0, [], 70, 0))
        ready.step(warm_patch(10, 4, 3400), 2.0, [], 70, 0)
        self.assertTrue(ready.step(warm_patch(2, 4, 2800), 3.0, [], 70, 0))

    def test_low_sensitivity_waits_for_a_larger_gesture(self):
        loose = count.Flow()
        loose.step(warm_patch(4, 4, 3000), 0.0, [], 100)
        self.assertTrue(loose.step(warm_patch(7, 4, 3200), 1.0, [], 100))
        tight = count.Flow()
        tight.step(warm_patch(4, 4, 3000), 0.0, [], 0)
        self.assertFalse(tight.step(warm_patch(7, 4, 3200), 1.0, [], 0))
        self.assertFalse(tight.step(warm_patch(9, 4, 3400), 2.0, [], 0))

    def test_heat_alone_or_motion_alone_stays_quiet(self):
        heat_only = count.Flow()
        heat_only.step(warm_patch(2, 4, 3000), 0.0, [])
        self.assertFalse(heat_only.step(warm_patch(2, 4, 3600), 1.0, []))
        self.assertFalse(heat_only.step(warm_patch(2, 4, 3900), 2.0, []))
        motion_only = count.Flow()
        motion_only.step(warm_patch(2, 4, 3000), 0.0, [])
        self.assertFalse(motion_only.step(warm_patch(10, 4, 3000), 1.0, []))
        self.assertFalse(motion_only.step(warm_patch(18, 4, 3000), 2.0, []))

    def test_a_small_shift_does_not_count_as_flow(self):
        flow = count.Flow()
        flow.step(warm_patch(8, 6, 3200), 0.0, [])
        self.assertFalse(flow.step(warm_patch(10, 6, 3600), 1.0, []))
        self.assertFalse(flow.step(warm_patch(11, 7, 3700), 2.0, []))

    def test_noise_and_whole_frame_drift_do_not_trigger(self):
        flow = count.Flow()
        base = room(2200)
        flow.step(base, 0.0, [])
        noisy = list(base)
        noisy[0] = 2800
        self.assertFalse(flow.step(noisy, 1.0, []))
        drifted = [temp + 300 for temp in base]
        self.assertFalse(flow.step(drifted, 2.0, []))


class FrameTest(unittest.TestCase):
    def test_parse_frame_uses_temperatures_only(self):
        payload = {
            "pwd": "do-not-keep",
            "center": 22.0,
            "frame": [21.5] * 768,
        }
        pixels = server.parse_frame(payload)
        self.assertEqual(len(pixels), 768)
        self.assertEqual(pixels[0], 2150)
        self.assertNotIn("do-not-keep", "".join(str(p) for p in pixels))

    def test_parse_frame_rejects_a_short_or_bad_frame(self):
        self.assertIsNone(server.parse_frame({"frame": [1, 2, 3]}))
        self.assertIsNone(server.parse_frame({"frame": [float("nan")] * 768}))
        self.assertIsNone(server.parse_frame({"pwd": "x"}))

    def test_device_url_points_at_json_and_drops_secrets(self):
        self.assertEqual(server.device_url("192.168.1.20"), "http://192.168.1.20/json")
        self.assertEqual(
            server.device_url("http://t-lite-8870.local/stream"),
            "http://t-lite-8870.local/json",
        )
        self.assertIsNone(server.device_url("http://user:secret@192.168.1.20/json"))
        self.assertIsNone(server.device_url("file:///tmp/frame.json"))


class MeasureTest(unittest.TestCase):
    def test_ten_readings_over_36_7_ask_for_a_long_alarm(self):
        session = server.Session()
        session.start(0.0, 36.0, "2026-10-21", "14:00:00")
        alarm = None
        for index in range(1, 10):
            alarm = session.tick(float(index), 37.0, "2026-10-21", f"14:00:0{index}")
        self.assertEqual(len(session.rows), 10)
        self.assertEqual(session.rows[0]["time"], "14:00:00")
        self.assertEqual(session.rows[-1]["time"], "14:00:09")
        self.assertEqual(alarm, "long")
        self.assertTrue(session.fever)
        self.assertGreater(session.average, 36.7)

    def test_average_at_36_7_beeps_three_times(self):
        session = server.Session()
        session.start(0.0, 36.7, "2026-10-21", "14:00:00")
        alarm = None
        for index in range(1, 10):
            alarm = session.tick(float(index), 36.7, "2026-10-21", f"14:00:0{index}")
        self.assertEqual(alarm, "triple")
        self.assertFalse(session.fever)
        self.assertEqual(session.average, 36.7)

    def test_a_sample_waits_one_second(self):
        session = server.Session()
        session.start(0.0, 30.0, "2026-10-21", "14:00:00")
        self.assertIsNone(session.tick(0.4, 31.0, "2026-10-21", "14:00:00"))
        self.assertEqual(len(session.rows), 1)
        session.tick(1.0, 31.0, "2026-10-21", "14:00:01")
        self.assertEqual(session.rows[1]["temp"], 31.0)
        self.assertEqual(session.rows[1]["time"], "14:00:01")


if __name__ == "__main__":
    unittest.main()
