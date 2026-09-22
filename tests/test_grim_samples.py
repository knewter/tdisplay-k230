import json
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
ENCODER = ROOT / "tools" / "encode-grim-samples.py"


class GrimSamplesTests(unittest.TestCase):
    def test_dry_run_uses_measured_intervals(self):
        with tempfile.TemporaryDirectory() as temp:
            sample = pathlib.Path(temp) / "samples"
            sample.mkdir()
            for index in range(1, 4):
                (sample / f"frame-{index:06d}.png").write_bytes(b"synthetic")
            (sample / "frames.tsv").write_text(
                "index\tstart_monotonic_seconds\tend_monotonic_seconds\tfile\n"
                "1\t100.00\t100.03\tframe-000001.png\n"
                "2\t100.51\t100.55\tframe-000002.png\n"
                "3\t101.27\t101.31\tframe-000003.png\n"
            )
            output = pathlib.Path(temp) / "feature.mp4"
            subprocess.run(
                [str(ENCODER), str(sample), "--output", str(output), "--description", "synthetic", "--dry-run"],
                check=True,
                text=True,
                capture_output=True,
            )
            manifest = json.loads(output.with_suffix(".json").read_text())
            self.assertEqual([frame["display_duration_seconds"] for frame in manifest["frames"]], [0.51, 0.76, 0.04])
            self.assertEqual(manifest["capture_source"]["kind"], "sampled-wayland-screencopy-png")
            self.assertIn("does not demonstrate smoothness", manifest["evidence_note"])
            concat = output.with_suffix(".concat.txt").read_text()
            self.assertIn("duration 0.510000", concat)
            self.assertIn("duration 0.760000", concat)
            self.assertIn("duration 0.040000", concat)


if __name__ == "__main__":
    unittest.main()
