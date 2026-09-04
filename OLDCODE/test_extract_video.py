"""Tests for frame-accurate Extract Video in get_png_video 12a.py."""

import importlib.util
import os
import shutil
import subprocess
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

SCRIPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "get_png_video 12a.py")


def _load_player_module():
    spec = importlib.util.spec_from_file_location("get_png_video_12a", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load_player_module()


class DummyVar:
    def __init__(self, value=""):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


class DummyRoot:
    def update(self):
        pass


class HeadlessPlayer(mod.VideoPlayer):
    """VideoPlayer methods without Tk/VLC GUI initialization."""

    def __init__(
        self,
        video_path,
        start="00:00:000",
        end="00:01:000",
        speed="1.0",
        duration_ms=8000,
        fps=30.0,
        rotate="No Rotation",
        dumb=False,
    ):
        self.video_path = video_path
        self.fps = fps
        self.video_duration = duration_ms
        self.playback_speed = float(speed)
        self.custom_speed_var = DummyVar(speed)
        self.start_time_var = DummyVar(start)
        self.end_time_var = DummyVar(end)
        self.auto_extract_start_var = DummyVar("00:00:000")
        self.auto_extract_stop_var = DummyVar("01:00:000")
        self.rotate_video_var = DummyVar(rotate)
        self.dumb_video_var = DummyVar(dumb)
        self.status_var = DummyVar("")
        self.root = DummyRoot()


def _run(args):
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


def _ffprobe_value(path, entries, stream=False):
    args = [
        "ffprobe",
        "-hide_banner",
        "-v",
        "error",
        "-count_frames",
        "-select_streams",
        "v:0",
        "-show_entries",
        entries,
        "-of",
        "default=nw=1:nk=1",
        path,
    ]
    result = _run(args)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or "ffprobe failed")
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return lines


def _video_packet_flags(path):
    result = _run(
        [
            "ffprobe",
            "-hide_banner",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "packet=flags",
            "-of",
            "csv=p=0",
            path,
        ]
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or "ffprobe packets failed")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


class TimeConversionTests(unittest.TestCase):
    def setUp(self):
        self.player = HeadlessPlayer("unused.mp4")

    def test_gui_clip_times_match_ffmpeg(self):
        start_ms = self.player.time_hires_to_ms("08:43:006")
        end_ms = self.player.time_hires_to_ms("08:47:522")
        self.assertEqual(start_ms, 523006)
        self.assertEqual(end_ms, 527522)
        self.assertEqual(end_ms - start_ms, 4516)
        self.assertEqual(self.player.time_hires_to_ffmpeg("08:43:006"), "00:08:43.006")
        self.assertEqual(
            self.player.time_hires_to_ffmpeg(self.player.ms_to_time_hires(4516)),
            "00:00:04.516",
        )

    def test_ms_round_trip(self):
        self.assertEqual(self.player.ms_to_time_hires(523006), "08:43:006")
        self.assertEqual(self.player.ms_to_time_hires(527522), "08:47:522")
        self.assertEqual(self.player.time_hires_to_ms("00:04:516"), 4516)


class TabLayoutTests(unittest.TestCase):
    """3-tab layout: widgets exist and tab switch does not drop shared vars."""

    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = mod.VideoPlayer(self.root)
        if self.app.update_id is not None:
            self.root.after_cancel(self.app.update_id)
            self.app.update_id = None

    def tearDown(self):
        if getattr(self.app, "update_id", None):
            try:
                self.root.after_cancel(self.app.update_id)
            except tk.TclError:
                pass
        try:
            self.app.vlc_player.stop()
            self.app.vlc_player.release()
            self.app.vlc_instance.release()
        except Exception:
            pass
        self.root.destroy()

    def test_three_tabs_exist(self):
        self.assertEqual(
            set(self.app.tab_panels.keys()),
            {"home", "extract_video", "extract_png"},
        )
        self.assertEqual(set(self.app.tab_buttons.keys()), set(self.app.tab_panels.keys()))

    def test_tab_switch_keeps_start_end_and_commands(self):
        self.app.start_time_var.set("00:01:250")
        self.app.end_time_var.set("00:02:500")
        self.app._show_tab("extract_video")
        self.assertEqual(self.app.start_time_var.get(), "00:01:250")
        self.assertEqual(self.app.end_time_var.get(), "00:02:500")
        self.app._show_tab("extract_png")
        self.app._show_tab("home")
        self.assertEqual(self.app.start_time_var.get(), "00:01:250")
        self.assertEqual(self.app.end_time_var.get(), "00:02:500")

    def test_all_original_controls_still_present(self):
        for attr in (
            "open_btn",
            "play_btn",
            "pause_btn",
            "stop_btn",
            "fast_bwd_btn",
            "fast_fwd_btn",
            "ab_play_btn",
            "time_entry",
            "start_time_btn",
            "end_time_btn",
            "get_video_time_btn",
            "get_video_time_btn_png",
            "custom_speed_entry",
            "extract_video_btn",
            "rotate_video_combo",
            "clear_mp4_btn",
            "auto_extract_start_entry",
            "auto_extract_stop_entry",
            "interval_entry",
            "extract_btn",
            "auto_extract_btn",
            "create_pdf_btn",
            "clear_btn",
            "video_label",
            "slider",
            "status_bar",
            "speed_label",
            "frame_res_label",
        ):
            self.assertTrue(hasattr(self.app, attr), f"missing {attr}")
            self.assertIsNotNone(getattr(self.app, attr))

    def test_png_tab_has_get_video_time_between_every_and_extract(self):
        png_children = list(self.app.extract_png_panel.pack_slaves())
        self.assertIn(self.app.get_video_time_btn_png, png_children)
        self.assertEqual(self.app.get_video_time_btn_png.cget("text"), "⏱ Get Video Time")
        every_i = png_children.index(self.app.interval_entry)
        gvt_i = png_children.index(self.app.get_video_time_btn_png)
        extract_i = png_children.index(self.app.extract_btn)
        self.assertEqual(gvt_i, every_i + 1)
        self.assertEqual(extract_i, gvt_i + 1)


class AutoExtractWindowTests(unittest.TestCase):
    """Auto extract uses start + stop + Every (stop is absolute, not a duration)."""

    def setUp(self):
        self.player = HeadlessPlayer("unused.mp4", duration_ms=10_000)

    def test_stop_is_absolute_not_duration(self):
        window = self.player._resolve_auto_extract_window(
            "00:00:500", "00:01:000", "00:00:100"
        )
        self.assertTrue(window["ok"])
        self.assertEqual(window["start_ms"], 500)
        self.assertEqual(window["end_ms"], 1000)
        self.assertEqual(window["interval_ms"], 100)
        self.assertFalse(window["capped"])
        self.assertEqual(window["end_ms"] - window["start_ms"], 500)

    def test_start_stop_every_full_minute(self):
        window = self.player._resolve_auto_extract_window(
            "00:00:000", "00:01:000", "00:00:100"
        )
        self.assertTrue(window["ok"])
        self.assertEqual(window["start_ms"], 0)
        self.assertEqual(window["end_ms"], 1000)
        self.assertEqual(window["interval_ms"], 100)
        self.assertEqual(int((window["end_ms"] - window["start_ms"]) / window["interval_ms"]) + 1, 11)

    def test_stop_capped_at_video_end(self):
        window = self.player._resolve_auto_extract_window(
            "00:08:000", "01:00:000", "00:00:100"
        )
        self.assertTrue(window["ok"])
        self.assertEqual(window["start_ms"], 8000)
        self.assertEqual(window["end_ms"], 10_000)
        self.assertTrue(window["capped"])
        self.assertEqual(window["stop_ms"], 60_000)

    def test_stop_before_start_is_invalid(self):
        window = self.player._resolve_auto_extract_window(
            "00:05:000", "00:04:000", "00:00:100"
        )
        self.assertFalse(window["ok"])
        self.assertEqual(window["error_title"], "Invalid Range")

    def test_stop_equal_start_is_invalid(self):
        window = self.player._resolve_auto_extract_window(
            "00:05:000", "00:05:000", "00:00:100"
        )
        self.assertFalse(window["ok"])
        self.assertEqual(window["error_title"], "Invalid Range")

    def test_start_past_video_end_is_invalid(self):
        window = self.player._resolve_auto_extract_window(
            "00:10:000", "00:12:000", "00:00:100"
        )
        self.assertFalse(window["ok"])
        self.assertEqual(window["error_title"], "Invalid Start Time")

    def test_invalid_stop_format(self):
        window = self.player._resolve_auto_extract_window(
            "00:00:000", "not-a-time", "00:00:100"
        )
        self.assertFalse(window["ok"])
        self.assertEqual(window["error_title"], "Invalid Stop Time")

    def test_invalid_interval(self):
        window = self.player._resolve_auto_extract_window(
            "00:00:000", "00:01:000", "00:00:000"
        )
        self.assertFalse(window["ok"])
        self.assertEqual(window["error_title"], "Invalid Interval")

    def test_copy_time_fills_auto_extract_from_start_end(self):
        self.player.start_time_var.set("00:03:500")
        self.player.end_time_var.set("00:05:700")
        self.player.copy_start_end_to_auto_extract()
        self.assertEqual(self.player.auto_extract_start_var.get(), "00:03:500")
        self.assertEqual(self.player.auto_extract_stop_var.get(), "00:05:700")
        self.assertIn("00:03:500", self.player.status_var.get())
        self.assertIn("00:05:700", self.player.status_var.get())

    def test_old_duration_math_is_not_used(self):
        # Previously end = start + duration field. With stop, 00:02:000 means
        # stop at 2s, not extract for 2s from start.
        window = self.player._resolve_auto_extract_window(
            "00:03:000", "00:05:000", "00:00:250"
        )
        self.assertTrue(window["ok"])
        self.assertEqual(window["end_ms"], 5000)
        self.assertNotEqual(window["end_ms"], 3000 + 5000)


class FfmpegCommandTests(unittest.TestCase):
    def test_optional_vf_args(self):
        player = HeadlessPlayer("unused.mp4")
        self.assertEqual(player._optional_vf_args(None), [])
        self.assertEqual(player._optional_vf_args("transpose=1"), ["-filter:v", "transpose=1"])

    def test_1x_trim_uses_input_seek(self):
        player = HeadlessPlayer("C:\\videos\\lesson.mp4")
        args = player._ffmpeg_trim_input("00:08:43.006", "00:00:04.516", False)
        self.assertEqual(
            args,
            ["-ss", "00:08:43.006", "-i", "C:\\videos\\lesson.mp4", "-t", "00:00:04.516"],
        )

    def test_filtered_trim_uses_output_seek(self):
        player = HeadlessPlayer("C:\\videos\\lesson.mp4")
        args = player._ffmpeg_trim_input("00:08:43.006", "00:00:04.516", True)
        self.assertEqual(
            args,
            ["-i", "C:\\videos\\lesson.mp4", "-ss", "00:08:43.006", "-t", "00:00:04.516"],
        )

    def test_1x_extract_reencodes_instead_of_stream_copy(self):
        player = HeadlessPlayer(
            os.path.join(tempfile.gettempdir(), "lesson.mp4"),
            start="08:43:006",
            end="08:47:522",
            duration_ms=1_830_518,
        )
        captured = []

        def fake_run(args, label):
            captured.append((list(args), label))
            return True, None

        player._run_ffmpeg = fake_run
        with patch.object(mod, "messagebox"):
            player.extract_video()

        self.assertTrue(captured)
        first_args = captured[0][0]
        self.assertIn("-nostdin", first_args)
        self.assertIn("libx264", first_args)
        self.assertIn("-c:a", first_args)
        self.assertEqual(first_args[first_args.index("-c:a") + 1], "aac")
        for i, token in enumerate(first_args[:-1]):
            if token in ("-c", "-c:a", "-c:v") and first_args[i + 1] == "copy":
                self.fail("1.0x extract must not stream-copy audio or video")
        self.assertNotIn("-filter:v", first_args)
        self.assertEqual(first_args[first_args.index("-ss") + 1], "00:08:43.006")
        self.assertLess(first_args.index("-ss"), first_args.index("-i"))

    def test_speed_extract_adds_fps_filter(self):
        player = HeadlessPlayer(
            os.path.join(tempfile.gettempdir(), "lesson.mp4"),
            start="00:01:000",
            end="00:02:000",
            speed="0.5",
            duration_ms=10_000,
            fps=30.0,
        )
        captured = []

        def fake_run(args, label):
            captured.append(list(args))
            return True, None

        player._run_ffmpeg = fake_run
        with patch.object(mod, "messagebox"):
            player.extract_video()

        self.assertTrue(captured)
        self.assertIn("-filter:v", captured[0])
        vf = captured[0][captured[0].index("-filter:v") + 1]
        self.assertTrue(vf.startswith("fps="))
        self.assertLess(captured[0].index("-i"), captured[0].index("-ss"))


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg/ffprobe not on PATH")
class AccurateExtractIntegrationTests(unittest.TestCase):
    def test_extract_between_keyframes_keeps_requested_duration(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "gop_src.mp4")
            make = _run(
                [
                    "ffmpeg",
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc=duration=8:size=160x120:rate=30",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:duration=8",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-g",
                    "60",
                    "-keyint_min",
                    "60",
                    "-sc_threshold",
                    "0",
                    "-c:a",
                    "aac",
                    "-shortest",
                    src,
                ]
            )
            self.assertEqual(make.returncode, 0, make.stderr)

            player = HeadlessPlayer(
                src,
                start="00:03:500",
                end="00:05:700",
                duration_ms=8000,
                fps=30.0,
            )
            with patch.object(mod, "messagebox"):
                player.extract_video()

            out = os.path.join(tmp, "mp4", "gop_src_00_03_500_00_05_700_speed1x_av.mp4")
            self.assertTrue(os.path.isfile(out), "extract did not write expected output")

            duration = float(_ffprobe_value(out, "format=duration")[0])
            self.assertAlmostEqual(duration, 2.2, delta=0.15)

            stream_vals = _ffprobe_value(out, "stream=nb_frames,nb_read_frames")
            nb_frames = int(float(stream_vals[0]))
            nb_read = int(float(stream_vals[1]))
            self.assertGreater(nb_read, 0)
            self.assertEqual(nb_frames, nb_read)

            discard = sum(1 for flags in _video_packet_flags(out) if "D" in flags)
            self.assertEqual(discard, 0)


if __name__ == "__main__":
    unittest.main()
