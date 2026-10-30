#!/usr/bin/env python3
"""Negative and positive tests for tools/check-boot-life-memory.py.

Builds tiny DTBs with dtc and variants of nix/boot-splash.nix, then checks
that overlapping or out-of-reservation record windows are rejected.
    python3 tests/test_check_boot_life_memory.py
"""
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tools/check-boot-life-memory.py")
NIX = open(os.path.join(ROOT, "nix/boot-splash.nix")).read()

DTS = """/dts-v1/;
/ {{
	#address-cells = <2>;
	#size-cells = <2>;
	memory@0 {{ device_type = "memory"; reg = <0x0 0x0 0x0 0x40000000>; }};
	reserved-memory {{
		#address-cells = <2>;
		#size-cells = <2>;
		ranges;
		splash_framebuffer: framebuffer@10000000 {{
			reg = <0x0 0x10000000 0x0 0x400000>;
			{nomap}
		}};
		{extra}
	}};
}};
"""


def run(tmp, nix_text, nomap="no-map;", extra="", env_extra=()):
    dts = os.path.join(tmp, "t.dts")
    dtb = os.path.join(tmp, "t.dtb")
    nix = os.path.join(tmp, "boot-splash.nix")
    open(dts, "w").write(DTS.format(nomap=nomap, extra=extra))
    subprocess.run(["dtc", "-I", "dts", "-O", "dtb", "-o", dtb, dts], check=True,
                   capture_output=True)
    open(nix, "w").write(nix_text)
    p = subprocess.run([sys.executable, TOOL, "--dtb", dtb, "--nix", nix,
                        "--size", "Image=42752512", "--size", "initrd.uimg=27328407",
                        "--size", "fw_jump_add_uboot_head.bin=270808",
                        "--size", "bootargs.txt=198", "--size", "dtb=19048", *env_extra],
                       capture_output=True, text=True)
    return p.returncode, p.stdout


def with_const(key, val):
    return re.sub(r'(%s\s*=\s*)"0x[0-9a-fA-F]+"' % key, r'\1"%s"' % val, NIX)


failures = 0


def check(name, cond, out=""):
    global failures
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        failures += 1
        print(out)


with tempfile.TemporaryDirectory() as tmp:
    rc, out = run(tmp, NIX)
    check("shipped constants accepted", rc == 0 and "RESULT: OK" in out, out)

    rc, out = run(tmp, with_const("lifeRecordOffset", "0x00100000").replace("0x102ac000", "0x10100000"))
    check("window inside the logo scanout rejected", rc == 1 and "inside the" in out, out)

    rc, out = run(tmp, with_const("lifeRecordOffset", "0x00400000").replace("0x102ac000", "0x10400000"))
    check("window outside the reservation rejected", rc == 1 and "not inside any DT reserved-memory" in out, out)

    rc, out = run(tmp, with_const("lifeRecordAddress", "0x102b0000"))
    check("absolute/offset mismatch rejected", rc == 1 and "lifeRecordAddress" in out, out)

    rc, out = run(tmp, NIX, nomap="")
    check("reservation without no-map rejected", rc == 1 and "lacks no-map" in out, out)

    rc, out = run(tmp, with_const("lifeRecordWindow", "0x00001000"))
    check("window smaller than the record rejected", rc == 1 and "smaller than" in out, out)

    # Another reserved-memory node over the window (e.g. a future carve-out).
    rc, out = run(tmp, NIX, extra="other@102ad000 { reg = <0x0 0x102ad000 0x0 0x1000>; no-map; };")
    check("overlapping DT reserved node rejected", rc == 1 and "overlaps DT reserved-memory" in out, out)

    rc, out = run(tmp, NIX, extra="harmless@20000000 { reg = <0x0 0x20000000 0x0 0x1000>; no-map; };")
    check("non-overlapping extra node accepted", rc == 0, out)

print("FAIL" if failures else "PASS", "(%d failures)" % failures)
sys.exit(1 if failures else 0)
