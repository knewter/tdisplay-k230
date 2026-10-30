"""nix/textfx/textfx-play.c (the live player) in its file-backed mode (host).

Run: TTFX=<host ttfx> UNIFONT_BDF=<unifont.bdf> python3 -I tests/test_textfx_player.py

Covers: the child's argument vector equals tools/textfx_frames.py's; surface
hashes at chosen frames equal an independent Python render; a continuation
with the right cell hash reaches the same final surface as a full run and does
not draw the skipped frames; a wrong hash refuses and replays from frame 0;
pacing follows the frame rate; a broken child is an error, not a crash.
The DRM path is not exercised here (board process test, tasks 3.2/3.3).
"""
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


TF = load("textfx_frames", "tools/textfx_frames.py")
T = load("test_textfx", "tests/test_textfx.py")
TTFX, BDF = os.environ.get("TTFX"), os.environ.get("UNIFONT_BDF")
COLS, ROWS, FPS = 35, 38, 30


@unittest.skipUnless(TTFX and BDF, "set TTFX and UNIFONT_BDF")
class PlayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.tmp.name)
        cls.exe = cls.dir / "textfx-play"
        subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-O2", "-DTEXTFX_NO_DRM",
                        "-I", str(ROOT / "src"), str(ROOT / "nix/textfx/textfx-play.c"),
                        str(ROOT / "src/textfx.c"), str(ROOT / "src/textfx_font.c"), str(ROOT / "src/textfx_record.c"),
                        "-o", str(cls.exe)], check=True)
        _, cls.frames, _ = TF.build_sequence(TTFX, T.BANNER, "wipe", 3, COLS, ROWS, FPS, None, [])
        cls.glyphs = T.load_bdf(BDF)
        cls.banner = ROOT / "nix/exhibition/K230.txt"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_player(self, *extra, ttfx=None, effect="wipe", check=True):
        out = self.dir / "surface.xrgb"
        cmd = [str(self.exe), "--ttfx", ttfx or TTFX, "--banner", str(self.banner),
               "--effect", effect, "--seed", "3", "--output-file", str(out), *extra]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if check:
            self.assertEqual(p.returncode, 0, p.stderr)
        return p, out

    @staticmethod
    def hashes(stdout):
        d = {}
        for m in re.finditer(r"hash frame (\d+) cell=0x(\w+) surface=0x(\w+)", stdout):
            d[int(m.group(1))] = (int(m.group(2), 16), int(m.group(3), 16))
        return d

    def test_argument_vector_matches_the_python_tool(self):
        p, _ = self.run_player("--print-command", check=False)
        want = " ".join(TF.ttfx_command(TTFX, "wipe", 3, COLS, ROWS, FPS, None, []))
        self.assertEqual(p.stdout.strip(), want)

    def test_surface_hashes_match_independent_renderer(self):
        last = len(self.frames) - 1
        p, _ = self.run_player("--no-pace", "--hash-frames", f"0,1,40,{last}")
        got = self.hashes(p.stdout)
        self.assertEqual(sorted(got), [0, 1, 40, last])
        for k, (cell, surf) in got.items():
            self.assertEqual(cell, TF.grid_hash(self.frames[k]))
            self.assertEqual(surf, TF.fnv1a(T.render(self.frames[k], self.glyphs, "xrgb")), k)

    def test_continuation_reaches_the_same_final_surface(self):
        last = len(self.frames) - 1
        full, out_full = self.run_player("--no-pace", "--hash-frames", str(last))
        data_full = out_full.read_bytes()
        h40 = TF.grid_hash(self.frames[40])
        cont, out_cont = self.run_player("--no-pace", "--skip", "40", "--expect-hash", hex(h40),
                                         "--hash-frames", f"41,{last}")
        self.assertIn("hash 0x%08x verified" % h40, cont.stderr)
        self.assertEqual(out_cont.read_bytes(), data_full)
        self.assertEqual(self.hashes(cont.stdout)[last], self.hashes(full.stdout)[last])
        # frames 0..40 were consumed silently: only the later ones were presented
        presented = int(re.search(r"presented=(\d+)", cont.stderr).group(1))
        self.assertLessEqual(presented, last - 40 + 1)

    def test_wrong_hash_refuses_and_replays_from_the_start(self):
        last = len(self.frames) - 1
        p, out = self.run_player("--no-pace", "--skip", "40", "--expect-hash", "0xdeadbeef",
                                 "--hash-frames", f"0,{last}")
        self.assertIn("continuation refused", p.stderr)
        got = self.hashes(p.stdout)
        self.assertEqual(sorted(got), [0, last])
        self.assertEqual(got[0][0], TF.grid_hash(self.frames[0]))
        self.assertEqual(got[last][1], TF.fnv1a(T.render(self.frames[last], self.glyphs, "xrgb")))

    def test_pacing_follows_the_frame_rate(self):
        p, _ = self.run_player("--max-frames", "30")
        wall = int(re.search(r"wall_ms=(\d+)", p.stderr).group(1))
        self.assertGreater(wall, 850)   # 30 frames at 30 fps is one second
        self.assertLess(wall, 1400)

    # ---- a hand-off record instead of arguments ----
    @staticmethod
    def payload(seed, cols, rows, fps, last, cell_hash, engine, text_hash, text_id, effect, flags=0):
        return (seed.to_bytes(8, "little") + cols.to_bytes(2, "little") + rows.to_bytes(2, "little")
                + fps.to_bytes(2, "little") + flags.to_bytes(2, "little") + last.to_bytes(4, "little")
                + cell_hash.to_bytes(4, "little") + engine.to_bytes(4, "little") + text_hash.to_bytes(4, "little")
                + text_id.to_bytes(2, "little") + (0).to_bytes(2, "little") + effect.encode().ljust(24, b"\0"))

    def record_run(self, payload, *extra, texts=True):
        rec = self.dir / "record.bin"
        rec.write_bytes(payload)
        cmd = [str(self.exe), "--ttfx", TTFX, "--record-payload", str(rec), "--output-file", str(self.dir / "r.xrgb"),
               "--no-pace"]
        if texts:
            cmd += ["--texts", str(ROOT / "nix/textfx/texts.txt")]
        else:
            cmd += ["--banner", str(self.banner)]
        p = subprocess.run(cmd + list(extra), capture_output=True, text=True, timeout=120)
        return p

    def listed_text(self, i):
        return [e for e in (ROOT / "nix/textfx/texts.txt").read_bytes().split(b"%%\n") if e.strip()][i]

    def test_record_continues_a_run_with_a_listed_text(self):
        text = self.listed_text(1)  # "T-DISPLAY K230"
        _, frames, _ = TF.build_sequence(TTFX, text, "wipe", 5, COLS, ROWS, FPS, None, [])
        last = len(frames) - 1
        pay = self.payload(5, COLS, ROWS, FPS, 20, TF.grid_hash(frames[20]), 0x1234, TF.fnv1a(text), 1, "wipe")
        p = self.record_run(pay, "--hash-frames", str(last), "--engine-id", "0x1234")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("continuing after frame 20", p.stderr)
        got = self.hashes(p.stdout)[last]
        self.assertEqual(got[0], TF.grid_hash(frames[last]))
        self.assertEqual(got[1], TF.fnv1a(T.render(frames[last], self.glyphs, "xrgb")))

    def test_record_with_a_text_hash_that_does_not_match_is_not_continued(self):
        text = self.listed_text(1)
        _, frames, _ = TF.build_sequence(TTFX, text, "wipe", 5, COLS, ROWS, FPS, None, [])
        pay = self.payload(5, COLS, ROWS, FPS, 20, TF.grid_hash(frames[20]), 0x1234, 0xBAD0BAD0, 1, "wipe")
        p = self.record_run(pay)
        self.assertIn("does not match the record's text hash: not continuing", p.stderr)
        self.assertEqual(p.returncode, 1)  # no other text was offered, so there is nothing to play

    def test_record_from_another_engine_plays_from_frame_zero(self):
        text = self.listed_text(1)
        _, frames, _ = TF.build_sequence(TTFX, text, "wipe", 5, COLS, ROWS, FPS, None, [])
        pay = self.payload(5, COLS, ROWS, FPS, 20, TF.grid_hash(frames[20]), 0x1111, TF.fnv1a(text), 1, "wipe")
        p = self.record_run(pay, "--engine-id", "0x2222", "--hash-frames", "0")
        self.assertIn("not continuing", p.stderr)
        self.assertIn(0, self.hashes(p.stdout))
        self.assertEqual(self.hashes(p.stdout)[0][0], TF.grid_hash(frames[0]))

    def test_record_with_an_environment_text_uses_the_given_file(self):
        text = self.banner.read_bytes()
        _, frames, _ = TF.build_sequence(TTFX, text, "wipe", 3, COLS, ROWS, FPS, None, [])
        pay = self.payload(3, COLS, ROWS, FPS, 10, TF.grid_hash(frames[10]), 0, TF.fnv1a(text), 0xFFFF, "wipe")
        p = self.record_run(pay, "--hash-frames", "11", texts=False)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("continuing after frame 10", p.stderr)
        self.assertEqual(self.hashes(p.stdout)[11][0], TF.grid_hash(frames[11]))

    def test_a_malformed_record_is_refused(self):
        p = self.record_run(b"short")
        self.assertEqual(p.returncode, 1)
        self.assertIn("not a text-effects record", p.stderr)

    def test_a_broken_child_is_an_error(self):
        fake = self.dir / "fake-ttfx"
        fake.write_text("#!/bin/sh\nprintf 'not a frame\\n'\n")
        fake.chmod(0o755)
        p, _ = self.run_player("--no-pace", ttfx=str(fake), check=False)
        self.assertEqual(p.returncode, 1)
        self.assertIn("malformed", p.stderr)

    def test_a_failing_child_is_an_error(self):
        p, _ = self.run_player("--no-pace", effect="nosucheffect", check=False)
        self.assertNotEqual(p.returncode, 0)


if __name__ == "__main__":
    if not (TTFX and BDF):
        print("TTFX/UNIFONT_BDF not set: the tests will be SKIPPED, not passed", file=sys.stderr)
    unittest.main(verbosity=2)
