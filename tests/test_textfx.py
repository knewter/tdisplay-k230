"""src/textfx.c against the Python reference (host).

Run: TTFX=<host ttfx 14ed274> UNIFONT_BDF=<unifont.bdf> python3 -I tests/test_textfx.py
(`nix build .#ttfx-host` and `nix build nixpkgs#unifont`; the BDF is
share/fonts/unifont.bdf.)

For the wipe effect over the K230 banner on the 35x38 panel grid it checks
that the C sequence reader and the C live-ANSI parser reach the same cell
grid, with the same hash as tools/textfx_frames.py, on every frame, and that
the C blitter's XRGB8888 and RGB565 surfaces hash the same as an independent
Python renderer that reads the BDF directly (not the generated table), at
checkpoint frames.  Incremental redraw of changed cells must equal a full
redraw.
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
SPEC = importlib.util.spec_from_file_location("textfx_frames", ROOT / "tools/textfx_frames.py")
TF = importlib.util.module_from_spec(SPEC)
sys.modules["textfx_frames"] = TF
SPEC.loader.exec_module(TF)

TTFX = os.environ.get("TTFX")
BDF = os.environ.get("UNIFONT_BDF")
BANNER = (ROOT / "nix/exhibition/K230.txt").read_bytes()
COLS, ROWS, FPS, SCALE = 35, 38, 30, 2
PANEL_W, PANEL_H = 568, 1232


def load_bdf(path):
    glyphs = {}
    text = open(path, encoding="utf-8").read()
    for m in re.finditer(r"STARTCHAR [^\n]*\nENCODING (\d+)\n(.*?)ENDCHAR", text, re.S):
        body = m.group(2)
        if "BBX 8 16 0 -2" not in body or "BITMAP" not in body:
            continue
        rows = body.split("BITMAP", 1)[1].split()
        if len(rows) == 16:
            glyphs[int(m.group(1))] = [int(r, 16) for r in rows]
    return glyphs


FALLBACK = [0x00, 0x00, 0x00, 0x7E, 0x42, 0x42, 0x42, 0x42, 0x42, 0x42, 0x42, 0x42, 0x42, 0x7E, 0x00, 0x00]


def render(cells, glyphs, fmt):
    """Independent renderer: returns the visible surface bytes for the panel."""
    bpp = 4 if fmt == "xrgb" else 2

    def px(r, g, b):
        if fmt == "xrgb":
            return bytes((b, g, r, 0))
        v = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
        return bytes((v & 0xFF, v >> 8))

    black = px(0, 0, 0)
    x0 = (PANEL_W - COLS * 8 * SCALE) // 2
    y0 = (PANEL_H - ROWS * 16 * SCALE) // 2
    out = bytearray()
    blank_row = black * PANEL_W
    for _ in range(y0):
        out += blank_row
    for cy in range(ROWS):
        for gy in range(16):
            line = bytearray(black * x0)
            for cx in range(COLS):
                cp, r, g, b = cells[cy * COLS + cx]
                if cp == 0x20:
                    bits = 0
                else:
                    bits = glyphs.get(cp, FALLBACK)[gy]
                on = px(r, g, b)
                for gx in range(8):
                    p = on if bits & (0x80 >> gx) else black
                    line += p * SCALE
            line += black * (PANEL_W - len(line) // bpp)
            for _ in range(SCALE):
                out += line
    for _ in range(PANEL_H - y0 - ROWS * 16 * SCALE):
        out += blank_row
    assert len(out) == PANEL_W * PANEL_H * bpp
    return bytes(out)


@unittest.skipUnless(TTFX and BDF, "set TTFX and UNIFONT_BDF")
class CTextfxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name)
        raw, cls.frames, data = TF.build_sequence(TTFX, BANNER, "wipe", 3, COLS, ROWS, FPS, None, [])
        (d / "wipe.tfxs").write_bytes(data)
        cmd = TF.ttfx_command(TTFX, "wipe", 3, COLS, ROWS, FPS, None, [])
        dump = subprocess.run(cmd, input=BANNER, capture_output=True, check=True).stdout
        (d / "wipe.dump").write_bytes(dump)
        exe = d / "harness"
        subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-O2",
                        "-I", str(ROOT / "src"), str(ROOT / "tests/textfx_harness.c"),
                        str(ROOT / "src/textfx.c"), str(ROOT / "src/textfx_font.c"),
                        "-o", str(exe)], check=True)
        cls.check = [0, 1, 40, len(cls.frames) - 1]
        out = subprocess.run([str(exe), str(d / "wipe.tfxs"), str(d / "wipe.dump"), str(SCALE),
                              ",".join(map(str, cls.check))],
                             capture_output=True, text=True).stdout
        cls.out = out
        cls.glyphs = load_bdf(BDF)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_paths_agree_on_every_frame(self):
        self.assertNotIn("MISMATCH", self.out)
        self.assertRegex(self.out, r"frames=%d .* bad=0" % len(self.frames))

    def test_cell_hashes_match_python(self):
        for line in self.out.splitlines():
            m = re.match(r"frame (\d+) cell=0x([0-9a-f]+)", line)
            if m:
                self.assertEqual(int(m.group(2), 16), TF.grid_hash(self.frames[int(m.group(1))]))

    def test_pixels_match_independent_renderer(self):
        seen = 0
        for line in self.out.splitlines():
            m = re.match(r"frame (\d+) cell=0x\w+ xrgb=0x([0-9a-f]+) rgb565=0x([0-9a-f]+)", line)
            if not m:
                continue
            k = int(m.group(1))
            self.assertEqual(int(m.group(2), 16), TF.fnv1a(render(self.frames[k], self.glyphs, "xrgb")), k)
            self.assertEqual(int(m.group(3), 16), TF.fnv1a(render(self.frames[k], self.glyphs, "565")), k)
            seen += 1
        self.assertEqual(seen, len(self.check))

    def test_last_frame_is_not_blank(self):
        self.assertTrue(any(c[0] != 0x20 for c in self.frames[-1]))


if __name__ == "__main__":
    if not (TTFX and BDF):
        print("TTFX/UNIFONT_BDF not set: the tests will be SKIPPED, not passed", file=sys.stderr)
    unittest.main(verbosity=2)
