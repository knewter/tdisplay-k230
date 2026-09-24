"""Wallpaper status is private, identity-bound, and requires actual frame progress."""
from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from theme_background_status import expected_fingerprint, progress, read_status  # noqa: E402


class StatusFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.generation = "a" * 24
        self.report = self.root / "report.json"
        self.report.write_text(json.dumps({"generation": self.generation,
                                           "backgrounds": ["backgrounds/clip.mp4"],
                                           "selected_background": "backgrounds/clip.mp4"}))
        self.status = self.root / "k230-wallpaper-status.json"
        self.value = {"schema": 1, "generation": self.generation,
                      "background_fingerprint": "7a9593f1f18a98154a1aefd8",
                      "decoder_pid": 123, "state": "playing", "error_category": None,
                      "frames_decoded": 2, "frames_submitted": 2,
                      "frame_callbacks": 2, "last_decoded_monotonic_ms": 10,
                      "last_submitted_monotonic_ms": 11,
                      "last_callback_monotonic_ms": 12}
        self.write()

    def write(self):
        self.status.write_text(json.dumps(self.value))
        self.status.chmod(0o600)

    def test_exact_source_fingerprint_and_frame_progress(self):
        fingerprint = expected_fingerprint(self.generation, self.report)
        self.assertEqual(fingerprint, "7a9593f1f18a98154a1aefd8")
        before = read_status(self.status, self.generation, fingerprint)
        for name in ("frames_decoded", "frames_submitted", "frame_callbacks"):
            self.value[name] += 3
        for name in ("last_decoded_monotonic_ms", "last_submitted_monotonic_ms",
                     "last_callback_monotonic_ms"):
            self.value[name] += 200
        self.write()
        after = read_status(self.status, self.generation, fingerprint)
        self.assertEqual(progress(before, after), {"frames_decoded": 3,
                                                   "frames_submitted": 3,
                                                   "frame_callbacks": 3})

    def test_private_file_and_identity_are_required(self):
        self.status.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "private"):
            read_status(self.status, self.generation, self.value["background_fingerprint"])
        self.status.chmod(0o600)
        self.value["generation"] = "b" * 24
        self.write()
        with self.assertRaisesRegex(ValueError, "identity"):
            read_status(self.status, self.generation, self.value["background_fingerprint"])
        self.status.unlink()
        self.status.symlink_to(self.report)
        with self.assertRaises(OSError):
            read_status(self.status, self.generation, self.value["background_fingerprint"])

    def test_restart_stall_and_error_are_not_video_proof(self):
        before = read_status(self.status, self.generation, self.value["background_fingerprint"])
        after = dict(before, decoder_pid=124, frames_decoded=5, frames_submitted=5,
                     frame_callbacks=5, last_decoded_monotonic_ms=20,
                     last_submitted_monotonic_ms=21, last_callback_monotonic_ms=22)
        with self.assertRaisesRegex(ValueError, "identity"):
            progress(before, after)
        after["decoder_pid"] = 123
        after["frame_callbacks"] = 2
        with self.assertRaisesRegex(ValueError, "did not advance"):
            progress(before, after)
        self.value["state"] = "paused-reduced-motion"
        self.write()
        with self.assertRaisesRegex(ValueError, "not playing"):
            read_status(self.status, self.generation, self.value["background_fingerprint"])


if __name__ == "__main__":
    unittest.main()
