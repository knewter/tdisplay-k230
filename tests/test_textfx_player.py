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
import shutil
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
                        "-I", str(ROOT / "textfx"), str(ROOT / "nix/textfx/textfx-play.c"),
                        str(ROOT / "textfx/textfx.c"), str(ROOT / "textfx/textfx_font.c"), str(ROOT / "textfx/textfx_record.c"),
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
    def payload(seed, cols, rows, fps, last, cell_hash, engine, text_hash, text_id, effect, flags=0, orientation=0):
        return (seed.to_bytes(8, "little") + cols.to_bytes(2, "little") + rows.to_bytes(2, "little")
                + fps.to_bytes(2, "little") + flags.to_bytes(2, "little") + last.to_bytes(4, "little")
                + cell_hash.to_bytes(4, "little") + engine.to_bytes(4, "little") + text_hash.to_bytes(4, "little")
                + text_id.to_bytes(2, "little") + orientation.to_bytes(2, "little") + effect.encode().ljust(24, b"\0"))

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

    def test_landscape_option_draws_the_turned_picture(self):
        last = 137
        _, frames, _ = TF.build_sequence(TTFX, T.BANNER, "wipe", 3, 77, 17, FPS, None, [])
        p, _ = self.run_player("--no-pace", "--orientation", "landscape", "--hash-frames", str(len(frames) - 1))
        got = self.hashes(p.stdout)[len(frames) - 1]
        self.assertEqual(got[0], TF.grid_hash(frames[-1]))
        self.assertEqual(got[1], TF.fnv1a(T.render(frames[-1], self.glyphs, "xrgb", True)))

    def test_record_orientation_selects_landscape_and_its_grid(self):
        text = self.banner.read_bytes()
        _, frames, _ = TF.build_sequence(TTFX, text, "wipe", 3, 77, 17, FPS, None, [])
        pay = self.payload(3, 77, 17, FPS, 20, TF.grid_hash(frames[20]), 0, TF.fnv1a(text), 0xFFFF, "wipe", orientation=1)
        last = len(frames) - 1
        p = self.record_run(pay, "--hash-frames", str(last), texts=False)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("continuing after frame 20", p.stderr)
        self.assertEqual(self.hashes(p.stdout)[last][1], TF.fnv1a(T.render(frames[last], self.glyphs, "xrgb", True)))

    def test_an_orientation_that_differs_from_the_record_plays_from_the_start_in_that_orientation(self):
        text = self.banner.read_bytes()
        _, fp, _ = TF.build_sequence(TTFX, text, "wipe", 3, 35, 38, FPS, None, [])
        _, fl, _ = TF.build_sequence(TTFX, text, "wipe", 3, 77, 17, FPS, None, [])
        pay = self.payload(3, 35, 38, FPS, 20, TF.grid_hash(fp[20]), 0, TF.fnv1a(text), 0xFFFF, "wipe", orientation=0)
        p = self.record_run(pay, "--orientation", "landscape", "--hash-frames", "0,%d" % (len(fl) - 1), texts=False)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("the record says portrait: not continuing", p.stderr)
        got = self.hashes(p.stdout)
        self.assertEqual(got[0][0], TF.grid_hash(fl[0]))
        self.assertEqual(got[len(fl) - 1][1], TF.fnv1a(T.render(fl[-1], self.glyphs, "xrgb", True)))

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


@unittest.skipUnless(TTFX and BDF and os.environ.get("TTFX_NOSTD_SRC"), "set TTFX_NOSTD_SRC")
class LinkedEngineTests(unittest.TestCase):
    """The player with the no_std engine linked in (no child) equals the std child, frame for frame."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name)
        work = d / "boot"
        shutil.copytree(ROOT / "nix/ttfx-boot", work, ignore=shutil.ignore_patterns("ttfx", "target", "default.nix"))
        (work / "ttfx").symlink_to(os.environ["TTFX_NOSTD_SRC"])
        subprocess.run(["cargo", "rustc", "--release", "--lib", "--crate-type", "staticlib", "--no-default-features",
                        "--features", "hosted,all-effects", "--target-dir", str(d / "t")], cwd=work, check=True,
                       capture_output=True)
        cls.exe = d / "play-lib"
        subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-O2", "-DTEXTFX_NO_DRM", "-DTEXTFX_ENGINE_LIB",
                        "-I", str(ROOT / "textfx"), "-I", str(ROOT / "nix/ttfx-boot"), str(ROOT / "nix/textfx/textfx-play.c"),
                        str(ROOT / "textfx/textfx.c"), str(ROOT / "textfx/textfx_font.c"), str(ROOT / "textfx/textfx_record.c"),
                        str(d / "t/release/libk230_ttfx_boot.a"), "-lgcc_s", "-lutil", "-lrt", "-lpthread", "-lm", "-ldl", "-lc",
                        "-o", str(cls.exe)], check=True)
        cls.banner = ROOT / "nix/exhibition/K230.txt"
        cls.texts = ROOT / "nix/textfx/texts.txt"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_it(self, *a):
        return subprocess.run([str(self.exe), *a], capture_output=True, text=True, timeout=300)

    def test_every_effect_matches_the_child_engine(self):
        for effect in (TF.EFFECTS if os.environ.get("FULL") == "1" else ["wipe", "beams", "decrypt", "matrix", "rings"]):
            outs = []
            for engine in ("lib", "child"):
                out = Path(self.tmp.name) / f"{engine}.xrgb"
                p = self.run_it("--engine", engine, "--ttfx", TTFX, "--effect", effect, "--seed", "3", "--banner", str(self.banner),
                                "--output-file", str(out), "--no-pace")
                self.assertEqual(p.returncode, 0, p.stderr)
                outs.append((p.stdout.split("final ")[1].split(" cell")[0], out.read_bytes()))
            self.assertEqual(outs[0], outs[1], effect)

    def test_record_continuation_with_the_linked_engine(self):
        text = [e for e in self.texts.read_bytes().split(b"%%\n") if e.strip()][1]
        _, frames, _ = TF.build_sequence(TTFX, text, "middleout", 9, COLS, ROWS, FPS, None, [])
        last = len(frames) - 1
        pay = PlayerTests.payload(9, COLS, ROWS, FPS, 30, TF.grid_hash(frames[30]), 7, TF.fnv1a(text), 1, "middleout")
        rec = Path(self.tmp.name) / "r.bin"
        rec.write_bytes(pay)
        p = self.run_it("--engine", "lib", "--record-payload", str(rec), "--texts", str(self.texts), "--engine-id", "7",
                        "--output-file", str(Path(self.tmp.name) / "c.xrgb"), "--no-pace", "--hash-frames", str(last))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("continuing after frame 30", p.stderr)
        self.assertIn("cell=0x%08x" % TF.grid_hash(frames[last]), p.stdout)

    def test_unknown_effect_is_an_error_not_a_crash(self):
        p = self.run_it("--engine", "lib", "--effect", "nosuchfx", "--seed", "1", "--banner", str(self.banner),
                        "--output-file", str(Path(self.tmp.name) / "x.xrgb"), "--no-pace")
        self.assertEqual(p.returncode, 1)
        self.assertIn("engine refused", p.stderr)


if __name__ == "__main__":
    if not (TTFX and BDF):
        print("TTFX/UNIFONT_BDF not set: the tests will be SKIPPED, not passed", file=sys.stderr)
    unittest.main(verbosity=2)
