"""tools/textfx_frames.py against the pinned ttfx (host).

Run: TTFX=<path to a host build of ttfx 14ed274> python3 -I tests/test_textfx_frames.py
(`nix build .#ttfx-host` gives one.)  The golden values below pin the
--parity-dump format and the effects' output for ttfx 14ed274; a ttfx bump that
changes either fails here instead of changing the boot animation.
"""
import hashlib
import importlib.util
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("textfx_frames", ROOT / "tools/textfx_frames.py")
TF = importlib.util.module_from_spec(SPEC)
sys.modules["textfx_frames"] = TF
SPEC.loader.exec_module(TF)

TTFX = os.environ.get("TTFX")
BANNER = (ROOT / "nix/exhibition/K230.txt").read_bytes()
COLS, ROWS, FPS = 35, 38, 30

# ttfx 14ed274, K230 banner, 35x38 grid, 30 fps, effect defaults.
GOLDEN = {
    # (effect, seed): (frames, sha256 of the concatenated frame bytes,
    #                  cell hash of the last frame, sequence sha256)
    ("wipe", 3): (138, "0cac956c2d5a30e239f1b1e77dd147e4aee5098921c7829adbe87c57f70ddcd2",
                  0x4EB5F4AB,
                  "7187872e4f499d6c22ddb65995847a312bcf4ee32b421966d709b7bd51cc2b98"),
}


def build(effect, seed):
    return TF.build_sequence(TTFX, BANNER, effect, seed, COLS, ROWS, FPS, None, [])


class SyntheticTests(unittest.TestCase):
    """No ttfx needed: the parser and the container."""

    def test_fnv1a_vectors(self):
        self.assertEqual(TF.fnv1a(b""), 0x811C9DC5)
        self.assertEqual(TF.fnv1a(b"a"), 0xE40C292C)
        self.assertEqual(TF.fnv1a(b"foobar"), 0xBF9CF968)

    def test_split_and_parse(self):
        frame = b"\x1b[38;2;1;2;3m\xe2\x96\x88\x1b[0m \n \x1b[38;2;4;5;6m#\x1b[0m"
        stream = b"%d\n" % len(frame) + frame + b"\n"
        (got,) = TF.split_dump(stream)
        cells = TF.parse_frame(got, 2, 2)
        self.assertEqual(cells, [(0x2588, 1, 2, 3), TF.BLANK, TF.BLANK, (0x23, 4, 5, 6)])

    def test_rejects_unknown_sgr_and_wide_and_ragged(self):
        for bad, cols in ((b"\x1b[1mx\x1b[0m", 1), ("中".encode(), 1), (b"ab", 3)):
            with self.assertRaises(TF.TfxError):
                TF.parse_frame(bad, cols, 1)

    def test_truncated_dump(self):
        with self.assertRaises(TF.TfxError):
            TF.split_dump(b"10\nabc\n")

    def test_roundtrip_and_checksum(self):
        a = [TF.BLANK, (65, 9, 8, 7), TF.BLANK, TF.BLANK]
        b = [TF.BLANK, (65, 9, 8, 7), (66, 1, 1, 1), TF.BLANK]
        data = TF.encode_sequence([a, b, b], 2, 2, 30, 7, 5)
        head, frames = TF.decode_sequence(data)
        self.assertEqual(frames, [a, b, b])
        self.assertEqual((head["cols"], head["rows"], head["fps"], head["seed"]), (2, 2, 30, 7))
        bad = bytearray(data)
        bad[-1] ^= 1
        with self.assertRaises(TF.TfxError):
            TF.decode_sequence(bytes(bad))


@unittest.skipUnless(TTFX, "set TTFX to a host build of ttfx")
class PinnedTtfxTests(unittest.TestCase):
    def test_same_seed_same_bytes_other_seed_differs(self):
        _, _, d1 = build("wipe", 3)
        _, _, d2 = build("wipe", 3)
        _, _, d3 = build("wipe", 4)
        self.assertEqual(hashlib.sha256(d1).digest(), hashlib.sha256(d2).digest())
        self.assertNotEqual(hashlib.sha256(d1).digest(), hashlib.sha256(d3).digest())

    def test_golden(self):
        for (effect, seed), (n, dump_sha, last, seq_sha) in GOLDEN.items():
            raw, frames, data = build(effect, seed)
            self.assertEqual(len(frames), n)
            self.assertEqual(hashlib.sha256(b"".join(raw)).hexdigest(), dump_sha)
            self.assertEqual(TF.grid_hash(frames[-1]), last)
            self.assertEqual(hashlib.sha256(data).hexdigest(), seq_sha)

    def test_sequence_decodes_to_the_same_frames(self):
        _, frames, data = build("wipe", 3)
        head, again = TF.decode_sequence(data)
        self.assertEqual(again, frames)
        self.assertEqual(head["frames"], len(frames))

    def test_every_effect_parses(self):
        for effect in TF.EFFECTS:
            raw = TF.run_ttfx(TTFX, BANNER, effect, 3, COLS, ROWS, FPS, 40, [])
            for f in raw:
                TF.parse_frame(f, COLS, ROWS)


if __name__ == "__main__":
    if not TTFX:
        print("TTFX is not set: the pinned-ttfx tests will be SKIPPED, not passed", file=sys.stderr)
    unittest.main(verbosity=2)
