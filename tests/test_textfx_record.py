"""textfx/textfx_record.c: the source-id-2 payload and the per-boot selection (host)."""
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("textfx_frames", ROOT / "tools/textfx_frames.py")
TF = importlib.util.module_from_spec(spec)
sys.modules["textfx_frames"] = TF
spec.loader.exec_module(TF)
M = (1 << 64) - 1


def splitmix(z):
    z = (z + 0x9E3779B97F4A7C15) & M
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & M
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & M
    return z ^ (z >> 31)


def seed_mix(t, c, e):
    s = splitmix(t)
    s = splitmix(s ^ (((c << 17) | (c >> 47)) & M))
    s = splitmix(s ^ e)
    return s or 1


class RecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.exe = Path(cls.tmp.name) / "h"
        subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-O2", "-I", str(ROOT / "textfx"),
                        str(ROOT / "tests/textfx_record_harness.c"), str(ROOT / "textfx/textfx_record.c"),
                        "-o", str(cls.exe)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_h(self, *a, check=True):
        return subprocess.run([str(self.exe), *a], capture_output=True, text=True, check=check)

    def test_payload_layout(self):
        out = self.run_h("codec").stdout.strip()
        want = (0x0123456789ABCDEF).to_bytes(8, "little") + (35).to_bytes(2, "little") + (38).to_bytes(2, "little") \
            + (30).to_bytes(2, "little") + (3).to_bytes(2, "little") + (40).to_bytes(4, "little") \
            + (0xDEADBEEF).to_bytes(4, "little") + (0x11223344).to_bytes(4, "little") + (0x55667788).to_bytes(4, "little") \
            + (2).to_bytes(2, "little") + (1).to_bytes(2, "little") + b"wipe".ljust(24, b"\0")
        self.assertEqual(len(want), 60)
        self.assertEqual(out, want.hex())

    def test_seed_mix_matches_python_and_is_never_zero(self):
        for t, c, e in ((0, 0, 0), (123456789, 1761836400, 0), (2**63 + 5, 77, 2**40)):
            self.assertEqual(int(self.run_h("seed", str(t), str(c), str(e)).stdout, 16), seed_mix(t, c, e))
        self.assertNotEqual(int(self.run_h("seed", "0", "0", "0").stdout, 16), 0)

    def test_select_is_pure_and_in_range(self):
        for seed in (1, 3, 99, 2**63):
            a = self.run_h("select", str(seed), "8", "4").stdout
            self.assertEqual(a, self.run_h("select", str(seed), "8", "4").stdout)
            e, t = map(int, a.split())
            self.assertLess(e, 8)
            self.assertLess(t, 4)
            self.assertEqual(e, splitmix(seed) % 8)
            self.assertEqual(t, splitmix(seed ^ 0xA5A5A5A5A5A5A5A5) % 4)

    def test_the_selection_varies_across_seeds(self):
        seen = {self.run_h("select", str(seed_mix(t, 0, 0)), "8", "4").stdout for t in range(1000, 1064)}
        self.assertGreater(len(seen), 12)

    def test_texts_list_parses_to_four_entries_with_hashes(self):
        path = ROOT / "nix/textfx/texts.txt"
        raw = path.read_bytes()
        lines = self.run_h("texts", str(path)).stdout.strip().splitlines()
        want = [e for e in raw.split(b"%%\n") if e.strip()]
        self.assertEqual(len(lines), len(want))
        for line, e in zip(lines, want):
            n, h, off = line.split()
            self.assertEqual(int(n), len(e))
            self.assertEqual(int(h, 16), TF.fnv1a(e))
        self.assertGreaterEqual(len(want), 2)

    def test_texts_parse_edge_cases(self):
        for blob, count in ((b"", 0), (b"a\n", 1), (b"a\n%%\nb", 2), (b"%%\n%%\na\n%%", 1), (b"a\n%%\n\n%%\nb\n", 2)):
            p = Path(self.tmp.name) / "t.txt"
            p.write_bytes(blob)
            self.assertEqual(len(self.run_h("texts", str(p)).stdout.strip().splitlines()), count, blob)


if __name__ == "__main__":
    unittest.main(verbosity=2)
