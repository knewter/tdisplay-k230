#!/usr/bin/env python3
"""Video background host checks (task group 2.2/2.3 of
the-background-chooser-supports-fill-solid-and-video).

Always run: the compatibility report that `tools/theme_activate.py` writes for
a recognised-suffix-but-undecodable video, driven through the real
`prepare()` (and, where a host ffmpeg exists, the real ffprobe rules).

With `--video`: also the Rust video wallpaper suites, run through cargo --
the decoder child's failure categories and stop/restart lifecycle
(`tests/video_wallpaper_module.rs`, stand-in ffmpeg/ffprobe scripts), the pause
predicate (`video_visibility::should_decode`: covered, reduced motion), the
still fallback (`appearance::fallback_still`) and a real-decoder run on a clip
this script encodes with the host ffmpeg (`K230_VIDEO_TEST_*`, the hook already
in `video_wallpaper.rs`). That run uses the HOST ffmpeg, not the board's
minimal build, so it proves the invocation and framing, not the shipped binary.

Not provable here (board task 3.3, `tools/handheld-theme-trial.py --workload
backgrounds`): the compositor's real covered signal, the live reduced-motion
setting reaching the shell, CPU/RSS and frame budgets, and what the panel shows.
"""

from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
import theme_activate as activation  # noqa: E402
from test_omarchy_theme_activation import source  # noqa: E402

CARGO = ["cargo", "test", "--offline", "--manifest-path",
         str(ROOT / "nix/rust-shell-client/Cargo.toml")]
FFMPEG, FFPROBE = shutil.which("ffmpeg"), shutil.which("ffprobe")


def encode(path: Path, codec: str, size: str = "640x360") -> Path:
    """A real 2 s clip made by the host ffmpeg; the test fails if it cannot."""
    command = [FFMPEG, "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i",
               f"testsrc2=size={size}:rate=8:duration=2", "-an", "-c:v", codec,
               "-pix_fmt", "yuv420p", str(path)]
    done = subprocess.run(command, capture_output=True, timeout=120)
    if done.returncode != 0 or not path.is_file():
        raise RuntimeError(f"host ffmpeg cannot encode {codec}: {done.stderr[-200:]!r}")
    return path


def prepare(base: Path, videos: dict[str, bytes | Path], *, overlays: dict[str, bytes] | None = None,
            choice: str | None = None):
    theme, state = base / "theme", base / "state"
    source(theme)
    for name, content in videos.items():
        target = theme / "backgrounds" / name
        if isinstance(content, Path):
            shutil.copyfile(content, target)
        else:
            target.write_bytes(content)
    overlay_dir = None
    if overlays:
        overlay_dir = base / "overlays"
        overlay_dir.mkdir()
        for name, content in overlays.items():
            (overlay_dir / name).write_bytes(content)
    return activation.prepare("clip-theme", source=theme, state_root=state,
                              user_themes=state / "no-user-themes", builtins=None,
                              tools=activation.HOST_TOOLS, background_choice=choice,
                              overlays=overlay_dir)


STUB_MP4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2" + b"\x00" * 64


def lines(report, asset):
    return [line for line in report["unavailable"] if line.startswith(f"{asset}:")]


class VideoCompatibilityReport(unittest.TestCase):
    """Recognised suffix, undecodable content: a named report line, never a failed prepare."""

    def test_undecodable_videos_are_named_and_the_theme_still_prepares(self):
        with tempfile.TemporaryDirectory() as temp:
            _generation, report = prepare(
                Path(temp),
                {"clip.webm": b"\x1aE\xdf\xa3", "garbage.mp4": b"this is not a movie at all, no boxes",
                 "short.mov": b"tiny", "good.mp4": STUB_MP4},
                overlays={"mine.mkv": b"\x1aE\xdf\xa3", "mine.mp4": b"not a movie either!!!"})
        self.assertIn("(unsupported-format)", lines(report, "backgrounds/clip.webm")[0])
        self.assertIn("(unsupported-codec)", lines(report, "backgrounds/garbage.mp4")[0])
        self.assertIn("(unsupported-codec)", lines(report, "backgrounds/short.mov")[0])
        self.assertIn("(unsupported-format)", lines(report, "backgrounds/user-mine.mkv")[0])
        self.assertIn("(unsupported-codec)", lines(report, "backgrounds/user-mine.mp4")[0])
        self.assertEqual(lines(report, "backgrounds/good.mp4"), [],
                         "a plausible ISO container is not accused without ffprobe")
        for asset in ("clip.webm", "garbage.mp4", "short.mov", "good.mp4"):
            self.assertIn(f"backgrounds/{asset}", report["backgrounds"], "still selectable")
        self.assertIn("backgrounds/portrait.png", report["backgrounds"], "paired still kept")
        self.assertTrue(all("still background is shown instead" in line
                            for asset in ("clip.webm", "garbage.mp4") for line in lines(report, f"backgrounds/{asset}")))

    def test_selecting_an_undecodable_video_still_activates_with_the_still_available(self):
        with tempfile.TemporaryDirectory() as temp:
            _generation, report = prepare(Path(temp), {"clip.webm": b"\x1aE\xdf\xa3"},
                                          choice="backgrounds/clip.webm")
        self.assertEqual(report["selected_background"], "backgrounds/clip.webm")
        self.assertTrue(lines(report, "backgrounds/clip.webm"))
        self.assertIn("backgrounds/portrait.png", report["backgrounds"])

    def test_static_theme_report_is_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            _generation, report = prepare(Path(temp), {})
        self.assertEqual([line for line in report["unavailable"] if "video" in line], [])


@unittest.skipUnless(FFMPEG and FFPROBE, "host ffmpeg/ffprobe not installed")
class VideoCompatibilityWithProbe(unittest.TestCase):
    """The codec/size rules, using the host ffprobe as K230_WALLPAPER_FFPROBE."""

    def test_probe_rules_match_the_decoders(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            h264 = encode(base / "h264.mp4", "libx264")
            mpeg4 = encode(base / "mpeg4.mp4", "mpeg4")
            wide = encode(base / "wide.mp4", "libx264", "2048x1152")
            with unittest.mock.patch.dict(os.environ, {"K230_WALLPAPER_FFPROBE": FFPROBE}):
                _generation, report = prepare(
                    base, {"ok.mp4": h264, "mpeg4.mp4": mpeg4, "wide.mp4": wide})
            with unittest.mock.patch.dict(os.environ, {"K230_WALLPAPER_FFPROBE": "relative-ffprobe"}):
                self.assertIsNone(activation.video_diagnostic(h264), "a relative probe path is ignored")
        self.assertEqual(lines(report, "backgrounds/ok.mp4"), [])
        self.assertIn("(unsupported-codec)", lines(report, "backgrounds/mpeg4.mp4")[0])
        self.assertIn("(unsupported-codec)", lines(report, "backgrounds/wide.mp4")[0])

    def test_a_missing_or_hanging_probe_never_fails_prepare(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            hang = base / "ffprobe-hang"
            hang.write_text("#!/bin/sh\nsleep 30\n")
            hang.chmod(0o755)
            for probe in (str(base / "absent"), str(hang)):
                with unittest.mock.patch.dict(os.environ, {"K230_WALLPAPER_FFPROBE": probe}):
                    self.assertEqual(activation.video_diagnostic(
                        self._stub(base)), "unsupported-codec")

    @staticmethod
    def _stub(base: Path) -> Path:
        path = base / "stub.mp4"
        path.write_bytes(STUB_MP4)
        return path


class BoardOnly(unittest.TestCase):
    @unittest.skip("board task 3.3: compositor cover signal -> pause -> restore, with grim captures")
    def test_covered_pause_and_restore_on_the_panel(self):
        pass

    @unittest.skip("board task 3.3: the live reduced-motion setting reaching the running shell")
    def test_reduced_motion_setting_reaches_the_shell(self):
        pass

    @unittest.skip("board task 3.3: CPU/RSS/frame budgets against the card gate")
    def test_budgets(self):
        pass


def cargo(*args, env=None):
    done = subprocess.run([*CARGO, *args, "--", "--nocapture"], capture_output=True, text=True,
                          timeout=900, env={**os.environ, **(env or {})})
    return done.returncode, done.stdout + done.stderr


class RustVideoSuites(unittest.TestCase):
    """Only selected by `--video`."""

    def passed(self, output, *names):
        for name in names:
            self.assertRegex(output, rf"test .*{name} \.\.\. ok", name)

    def test_lifecycle_failure_categories_and_pause_predicate(self):
        code, out = cargo("--test", "video_wallpaper_module")
        self.assertEqual(code, 0, out[-2000:])
        self.passed(out, "source_bounds_fail_by_name_before_any_decoder_runs",
                    "probe_failures_are_distinct_named_categories",
                    "decoder_failures_are_named_and_leave_no_child",
                    "stop_reaps_the_decoder_and_a_fresh_start_resumes_frames",
                    "output_bound_is_named_before_the_decoder_starts")
        code, out = cargo("--lib", "video_visibility")
        self.assertEqual(code, 0, out[-2000:])
        self.passed(out, "decoding_needs_motion_allowed_and_wallpaper_uncovered",
                    "missing_signal_keeps_wallpaper_visible", "freshness_boundary_expires_exactly_after_1500ms")

    def test_still_fallback(self):
        code, out = cargo("--test", "appearance_module", "video_selection_falls_back")
        self.assertEqual(code, 0, out[-2000:])
        self.passed(out, "video_selection_falls_back_to_the_first_still_and_never_to_a_video")

    @unittest.skipUnless(FFMPEG and FFPROBE, "host ffmpeg/ffprobe not installed: real decode NOT proven")
    def test_real_decoder_emits_distinct_frames_then_stops(self):
        with tempfile.TemporaryDirectory() as temp:
            clip = encode(Path(temp) / "clip.mp4", "libx264")
            code, out = cargo("--lib", "bounded_real_decoder", env={
                "K230_VIDEO_TEST_CLIP": str(clip), "K230_VIDEO_TEST_FFMPEG": FFMPEG,
                "K230_VIDEO_TEST_FFPROBE": FFPROBE})
        self.assertEqual(code, 0, out[-2000:])
        self.passed(out, "bounded_real_decoder_emits_distinct_muted_frames_when_fixture_supplied")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", action="store_true", help="also run the Rust video suites")
    args, remaining = parser.parse_known_args()
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for case in (VideoCompatibilityReport, VideoCompatibilityWithProbe, BoardOnly):
        suite.addTests(loader.loadTestsFromTestCase(case))
    if args.video:
        suite.addTests(loader.loadTestsFromTestCase(RustVideoSuites))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
