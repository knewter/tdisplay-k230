"""tools/check-boot-textfx-memory.py: accepts the shipped arena, rejects overlaps (host, synthetic DTBs)."""
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/check-boot-textfx-memory.py"
DTS = """/dts-v1/;
/ { #address-cells = <2>; #size-cells = <2>;
  memory@0 { device_type = "memory"; reg = <0x0 0x0 0x0 0x40000000>; };
  reserved-memory { #address-cells = <2>; #size-cells = <2>; ranges;
    framebuffer@10000000 { reg = <0x0 0x10000000 0x0 0x400000>; no-map; };
%s
  };
};
"""
SIZES = ["--size", "Image=42752512", "--size", "initrd.uimg=27328407", "--size", "fw_jump_add_uboot_head.bin=270808",
         "--size", "bootargs.txt=198", "--size", "dtb=19308"]


def arena(addr, size, stack="0x00010000", div=2):
    return ('{\n  arenaAddress = "%s";\n  arenaSize = "%s";\n  arenaMarginDivisor = %d;\n  engineStackSize = "%s";\n}\n'
            % (addr, size, div, stack))


class ArenaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def dtb(self, extra=""):
        src = self.dir / "t.dts"
        src.write_text(DTS % extra)
        out = self.dir / "t.dtb"
        subprocess.run(["dtc", "-I", "dts", "-O", "dtb", "-o", str(out), str(src)], check=True, capture_output=True)
        return out

    def run_tool(self, arena_text=None, extra="", peaks=None):
        cmd = ["python3", "-I", str(TOOL), "--dtb", str(self.dtb(extra)), *SIZES]
        if arena_text is not None:
            f = self.dir / "arena.nix"
            f.write_text(arena_text)
            cmd += ["--arena", str(f)]
        if peaks is not None:
            p = self.dir / "peaks.txt"
            p.write_text(peaks)
            cmd += ["--heap-peaks", str(p)]
        return subprocess.run(cmd, capture_output=True, text=True)

    def test_shipped_arena_is_accepted_with_the_measured_peaks(self):
        r = self.run_tool(peaks=(ROOT / "docs/evidence/boot-text-effects/nostd-heap-peaks.txt").read_text())
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("RESULT: OK", r.stdout)

    def test_arena_inside_the_splash_reservation_is_rejected(self):
        r = self.run_tool(arena("0x10100000", "0x00200000"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("splash reservation", r.stdout)

    def test_arena_over_the_loaded_initrd_is_rejected(self):
        r = self.run_tool(arena("0x09000000", "0x02000000"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("initrd.uimg", r.stdout)

    def test_arena_over_the_growth_margin_of_the_initrd_is_rejected(self):
        r = self.run_tool(arena("0x0aa10000", "0x00800000"))  # clear of today's initrd, inside +25%
        self.assertEqual(r.returncode, 1)

    def test_arena_in_the_cma_pool_is_rejected(self):
        r = self.run_tool(arena("0x1e000000", "0x02000000"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("CMA", r.stdout)

    def test_arena_outside_memory_is_rejected(self):
        r = self.run_tool(arena("0x40000000", "0x02000000"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("not inside DT /memory", r.stdout)

    def test_arena_over_another_reserved_node_is_rejected(self):
        node = "    other@18400000 { reg = <0x0 0x18400000 0x0 0x100000>; no-map; };\n"
        r = self.run_tool(extra=node)
        self.assertEqual(r.returncode, 1)
        self.assertIn("other@18400000", r.stdout)

    def test_an_unrelated_reserved_node_is_accepted(self):
        node = "    other@19f00000 { reg = <0x0 0x1b000000 0x0 0x100000>; no-map; };\n"
        self.assertEqual(self.run_tool(extra=node).returncode, 0)

    def test_an_effect_over_the_margin_is_rejected(self):
        r = self.run_tool(peaks="rings 13430\nhuge 17000\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("effect huge", r.stdout)

    def test_unaligned_arena_and_tiny_stack_are_rejected(self):
        self.assertEqual(self.run_tool(arena("0x18000100", "0x02000000")).returncode, 1)
        self.assertEqual(self.run_tool(arena("0x18000000", "0x02000000", stack="0x00001000")).returncode, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
