"""The no_std ttfx engine against the std ttfx, byte for byte (host + QEMU user).

Run:
  TTFX=<ttfx binary built from the same revision> \
  TTFX_NOSTD_SRC=<nix build .#ttfx-nostd-src> \
  [FW=1 RISCV_CC=<riscv64 gcc>] [FULL=1] python3 -I tests/test_ttfx_nostd.py

Builds nix/ttfx-boot's `dump` example with the nostd feature on the host and
compares its frames with `ttfx --parity-dump` for the same effect, text, seed and
canvas.  With FW=1 it also builds the freestanding riscv64imac staticlib
(rustup target riscv64imac-unknown-none-elf), links nix/ttfx-boot/bench/bench.c with
it and runs the resulting soft-float executable under qemu-riscv64-static: the
machine code that would go into U-Boot, compared with the std output.
FULL=1 covers all 37 effects and two seeds and texts; the default is a quick subset.
"""
import importlib.util
import os
import shutil
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

TTFX = os.environ.get("TTFX")
SRC = os.environ.get("TTFX_NOSTD_SRC")
FW = os.environ.get("FW") == "1"
FULL = os.environ.get("FULL") == "1"
BANNER = ROOT / "nix/exhibition/K230.txt"
SECOND = "TDISPLAY\nK230\n"
QUICK = ["wipe", "beams", "decrypt", "middleout", "expand", "errorcorrect", "matrix", "rings"]
EFFECTS = TF.EFFECTS if FULL else QUICK
SEEDS = (3, 11) if FULL else (3,)
CANVAS = (35, 38, 30)


def std_dump(effect, seed, text):
    cmd = TF.ttfx_command(TTFX, effect, seed, CANVAS[0], CANVAS[1], CANVAS[2], None, [])
    return subprocess.run(cmd, input=text, capture_output=True, check=True).stdout


@unittest.skipUnless(TTFX and SRC, "set TTFX and TTFX_NOSTD_SRC")
class NostdParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.work = Path(cls.tmp.name) / "boot"
        shutil.copytree(ROOT / "nix/ttfx-boot", cls.work, ignore=shutil.ignore_patterns("ttfx", "target", "default.nix"))
        (cls.work / "ttfx").symlink_to(SRC)
        subprocess.run(["cargo", "build", "--release", "--examples", "--target-dir", str(Path(cls.tmp.name) / "t")],
                       cwd=cls.work, check=True, capture_output=True)
        cls.dump = Path(cls.tmp.name) / "t/release/examples/dump"
        cls.texts = {"banner": BANNER.read_bytes(), "second": SECOND.encode()}
        for name, data in cls.texts.items():
            (Path(cls.tmp.name) / f"{name}.txt").write_bytes(data)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def nostd_dump(self, effect, seed, name):
        p = subprocess.run([str(self.dump), effect, str(Path(self.tmp.name) / f"{name}.txt"), str(seed),
                            *map(str, CANVAS)], capture_output=True, check=True)
        return p.stdout

    def test_frames_equal_the_std_engine(self):
        for name in (("banner", "second") if FULL else ("banner",)):
            for effect in EFFECTS:
                for seed in SEEDS:
                    with self.subTest(effect=effect, seed=seed, text=name):
                        self.assertEqual(self.nostd_dump(effect, seed, name), std_dump(effect, seed, self.texts[name]))

    def test_unknown_effect_is_an_error(self):
        p = subprocess.run([str(self.dump), "nosuchfx", str(Path(self.tmp.name) / "banner.txt"), "1", "10", "10", "30"],
                           capture_output=True)
        self.assertNotEqual(p.returncode, 0)

    def test_effect_names_match_the_cli(self):
        out = subprocess.run([TTFX, "--help"], capture_output=True, text=True).stdout
        for effect in TF.EFFECTS:
            self.assertIn(effect, out)


@unittest.skipUnless(TTFX and SRC and FW and os.environ.get("RISCV_CC"), "set FW=1 and RISCV_CC")
class FirmwareParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        work = Path(cls.tmp.name) / "boot"
        shutil.copytree(ROOT / "nix/ttfx-boot", work, ignore=shutil.ignore_patterns("ttfx", "target", "default.nix"))
        (work / "ttfx").symlink_to(SRC)
        env = dict(os.environ, RUSTFLAGS="-C relocation-model=pic")
        subprocess.run(["cargo", "rustc", "--release", "--lib", "--crate-type", "staticlib", "--target", "riscv64imac-unknown-none-elf",
                        "--no-default-features", "--features", "fw,all-effects",
                        "--target-dir", str(Path(cls.tmp.name) / "t")], cwd=work, check=True, capture_output=True, env=env)
        lib = Path(cls.tmp.name) / "t/riscv64imac-unknown-none-elf/release/libk230_ttfx_boot.a"
        cls.exe = Path(cls.tmp.name) / "bench"
        subprocess.run([os.environ["RISCV_CC"], "-O2", "-ffreestanding", "-nostdlib", "-static", "-march=rv64imac",
                        "-mabi=lp64", "-fno-builtin", "-Wl,--gc-sections", "-o", str(cls.exe),
                        str(ROOT / "nix/ttfx-boot/bench/bench.c"), str(lib)], check=True)
        cls.banner = BANNER.read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_bare_metal_object_code_equals_std(self):
        for effect in EFFECTS:
            raw = TF.split_dump(std_dump(effect, 3, self.banner))
            want = "%s frames=%d bytes=%d fnv=0x%08x" % (effect, len(raw), sum(map(len, raw)), TF.fnv1a(b"".join(raw)))
            p = subprocess.run(["qemu-riscv64-static", str(self.exe), effect, "3", *map(str, CANVAS), str(BANNER)],
                               capture_output=True, text=True, timeout=900)
            self.assertEqual(p.stdout.strip().rsplit(" ms=", 1)[0], want, p.stderr)


if __name__ == "__main__":
    if not (TTFX and SRC):
        print("TTFX/TTFX_NOSTD_SRC not set: the tests will be SKIPPED, not passed", file=sys.stderr)
    unittest.main(verbosity=2)
