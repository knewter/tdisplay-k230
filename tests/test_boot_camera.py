"""Recorder file/metadata/error protocol with synthetic ioctl buffers only."""
import json
import os
import signal
from pathlib import Path
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BootCamera(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory()
        cls.binary = Path(cls.build.name) / "capture"
        subprocess.run([
            "cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
            str(ROOT / "tools/capture-boot-camera.c"),
            str(ROOT / "tests/boot_camera_ioctl_fixture.c"),
            "-Wl,--wrap=ioctl", "-o", str(cls.binary),
        ], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.device = self.root / "synthetic-camera"
        self.device.write_bytes(b"\xff\xd8\xff\xd9" + bytes(1048572) + b"ABCD" + bytes(1048572))
        self.output = self.root / "capture"
        self.cleanup = self.root / "cleanup.log"

    def run_capture(self, scenario="normal", frames=3):
        result = subprocess.run([
            str(self.binary), str(self.device), str(self.output), "5", "1", str(frames),
        ], env=dict(os.environ, CAMERA_SCENARIO=scenario, CAMERA_CLEANUP_LOG=str(self.cleanup)),
            capture_output=True, text=True, timeout=10)
        metadata = self.output / "frames.jsonl"
        records = [json.loads(line) for line in metadata.read_text().splitlines()] if metadata.exists() else []
        return result, records

    def assert_cleanup(self):
        self.assertEqual(self.cleanup.read_text().splitlines(), ["stream_off", "release_buffers"])

    def test_raw_frames_timestamps_and_no_alignment_claim(self):
        result, records = self.run_capture()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output.joinpath("frames.mjpeg").read_bytes(), b"\xff\xd8\xff\xd9ABCD\xff\xd8\xff\xd9")
        self.assertEqual([r["offset"] for r in records[1:-1]], [0, 4, 8])
        self.assertEqual([r["camera_timestamp_ns"] for r in records[1:-1]], [10033333000, 10066666000, 10099999000])
        self.assertEqual(records[0]["width"], 1280)
        for r in records[1:-1]:
            self.assertEqual(r["camera_clock"], "monotonic")
            self.assertEqual(r["timestamp_source"], "start_of_exposure")
            self.assertLessEqual(r["host_dq_before_ns"], r["host_dq_after_ns"])
        self.assertTrue(records[-1]["capture_complete"])
        self.assertFalse(records[-1]["kernel_video_alignment_qualified"])
        self.assertFalse(records[0]["kernel_video_alignment_qualified"])
        self.assert_cleanup()

    def test_unknown_clock_is_preserved_without_relabeling(self):
        result, records = self.run_capture("unknown")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(records[1]["camera_clock"], "unknown")
        self.assertEqual(records[1]["timestamp_source"], "end_of_frame")
        self.assertFalse(records[-1]["kernel_video_alignment_qualified"])

    def test_missing_sequence_is_retained_and_capture_incomplete(self):
        result, records = self.run_capture("gap")
        self.assertEqual(result.returncode, 2)
        self.assertTrue(records[2]["sequence_gap"])
        self.assertEqual(records[-1]["sequence_gaps"], 1)
        self.assertFalse(records[-1]["capture_complete"])
        self.assert_cleanup()

    def test_sequence_wrap_is_contiguous(self):
        result, records = self.run_capture("wrap")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([r["sequence"] for r in records[1:-1]], [4294967295, 0, 1])
        self.assertEqual(records[-1]["sequence_gaps"], 0)

    def test_bad_buffers_do_not_read_or_write_outside_mapping(self):
        for scenario in ("index", "size", "timeval"):
            with self.subTest(scenario=scenario):
                self.output = self.root / scenario
                self.cleanup.unlink(missing_ok=True)
                result, records = self.run_capture(scenario)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(records[-1]["reason"], "invalid_buffer")
                self.assertFalse(records[-1]["capture_complete"])
                self.assertEqual(self.output.joinpath("frames.mjpeg").stat().st_size, 0)
                self.assert_cleanup()

    def test_error_flag_and_timestamp_regression_are_not_success(self):
        for scenario, flag in (("buffer_error", "buffer_error"), ("regression", "timestamp_regression"),
                               ("clock_change", "clock_flags_changed"), ("future", "timestamp_invalid")):
            with self.subTest(scenario=scenario):
                self.output = self.root / scenario
                result, records = self.run_capture(scenario)
                self.assertEqual(result.returncode, 2)
                self.assertTrue(any(r.get(flag) for r in records))
                self.assertFalse(records[-1]["capture_complete"])

    def test_byte_cap_preserves_partial_capture_and_releases_stream(self):
        result, records = self.run_capture("cap")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(records[-1]["reason"], "byte_limit")
        self.assertEqual(records[-1]["frames"], 1)
        self.assertEqual(self.output.joinpath("frames.mjpeg").stat().st_size, 700000)
        self.assert_cleanup()

    def test_requeue_failure_is_not_success_after_one_frame(self):
        result, records = self.run_capture("requeue")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(records[-1]["reason"], "VIDIOC_QBUF")
        self.assertFalse(records[-1]["capture_complete"])
        self.assert_cleanup()

    def test_existing_capture_is_never_overwritten(self):
        self.output.mkdir()
        marker = self.output / "frames.mjpeg"
        marker.write_bytes(b"KEEP")
        result, records = self.run_capture()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(marker.read_bytes(), b"KEEP")
        self.assertEqual(records, [])
        self.assertEqual(self.cleanup.read_text().splitlines(), ["release_buffers"])

    def test_other_format_is_rejected_without_changing_it(self):
        result, records = self.run_capture("format")
        self.assertEqual(result.returncode, 2)
        self.assertIn("must already be configured for MJPEG", result.stderr)
        self.assertFalse(self.output.exists())
        self.assertEqual(records, [])

    def test_invalid_limits_do_not_open_camera_or_create_output(self):
        for value in ("0", "601", "-1", "2x", "nan"):
            result = subprocess.run([str(self.binary), "/no-camera", str(self.output), value, "1"], capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(self.output.exists())

    def test_sigterm_preserves_partial_records_and_releases_camera(self):
        process = subprocess.Popen([
            str(self.binary), str(self.device), str(self.output), "5", "1", "100",
        ], env=dict(os.environ, CAMERA_SCENARIO="wait_signal", CAMERA_CLEANUP_LOG=str(self.cleanup)),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(lambda: process.kill() if process.poll() is None else None)
        deadline = time.monotonic() + 3
        metadata = self.output / "frames.jsonl"
        while time.monotonic() < deadline:
            if metadata.exists() and '"kind":"frame"' in metadata.read_text():
                break
            time.sleep(0.01)
        else:
            self.fail("fixture did not deliver its first frame")
        process.send_signal(signal.SIGTERM)
        _, error = process.communicate(timeout=3)
        self.assertEqual(process.returncode, 143, error.decode())
        summary = json.loads(metadata.read_text().splitlines()[-1])
        self.assertEqual(summary["reason"], "interrupted")
        self.assertEqual(summary["frames"], 1)
        self.assertFalse(summary["capture_complete"])
        self.assert_cleanup()


if __name__ == "__main__":
    unittest.main()
