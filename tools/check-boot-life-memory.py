#!/usr/bin/env python3
"""Check that the Game of Life state record overlaps no boot-time owner.

openspec change the-boot-shows-a-computational-game-of-life, task 1.3.

Reads (all host-side, nothing touches a board):
  * the compiled DTB, decompiled with `dtc -I dtb -O dts`: /memory and every
    /reserved-memory child;
  * nix/boot-splash.nix: the splash reservation and the record offset/window;
  * firmware/stage1/tdisplay.env: the `blinux` ext4load addresses;
  * --kernel/--initrd/--dtb-size file sizes (or explicit --size NAME=BYTES);
  * the live U-Boot placement recorded from `bdinfo` and `bootm` on the
    board (relocation address, LMB reservation, relocated initrd and DTB),
    given as defaults that cite their source evidence file and overridable.

It prints a report and exits 1 if the record is not inside the DTB's splash
reserved-memory node, or if the record window overlaps any other interval.

Usage:
  check-boot-life-memory.py --dtb k230-tdisplay.dtb \
      --kernel Image --initrd initrd.uimg [--dtc dtc] [--json]
"""
import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Live U-Boot placement, from the physical board (read-only observations).
# docs/evidence/stage1-memory-map.md sections 2.1 and 2.2, captured in
# docs/evidence/uboot-usb-host-coexist.txt.
LIVE = {
    "uboot-relocated (relocaddr..malloc top)": (0x3FB37920, 0x40000000),
    "initrd-relocated by bootm": (0x3E12F000, 0x3FB36D4F),
    "dtb-relocated by bootm": (0x0A0EB000, 0x0A0FF682),
}
# Where the SPL/U-Boot proper themselves load (SPL puts U-Boot proper low;
# OpenSBI is loaded by blinux at 0x8000000).  U-Boot proper's link address is
# not in this repository's configs beyond the stage-1 firmware; its live
# footprint is the relocated range above.  The pre-relocation image sits in
# the first 4 MiB, which is the vendor stage-1 region.
STAGE1_LOW = ("stage-1 SPL/U-Boot/OpenSBI load region", 0x0, 0x400000)


def parse_nix_constants(path):
    text = open(path).read()
    consts = {}
    for key in ("framebufferAddress", "framebufferSize", "lifeRecordOffset",
                "lifeRecordAddress", "lifeRecordWindow"):
        m = re.search(r'%s\s*=\s*"(0x[0-9a-fA-F]+)"' % key, text)
        if not m:
            sys.exit("error: %s not found in %s" % (key, path))
        consts[key] = int(m.group(1), 16)
    return consts


def parse_env_loads(path):
    """(name, addr) for each `ext4load ... 0xADDR /file` in the blinux line."""
    loads = []
    for line in open(path):
        if line.startswith("blinux="):
            for m in re.finditer(r"ext4load\s+\S+\s+\S+\s+(0x[0-9a-fA-F]+)\s+/(\S+?)(?:\s|;|$)", line):
                loads.append((m.group(2).replace("${k}", "Image").replace("${dtb}", "dtb"),
                              int(m.group(1), 16)))
    if not loads:
        sys.exit("error: no ext4load entries in blinux of %s" % path)
    return loads


def decompile_dtb(dtb, dtc):
    return subprocess.run([dtc, "-I", "dtb", "-O", "dts", dtb], check=True,
                          capture_output=True, text=True).stdout


def parse_reg_cells(txt, ac, sc):
    vals = [int(v, 16) for v in re.findall(r"0x[0-9a-fA-F]+", txt)]
    out = []
    step = ac + sc
    for i in range(0, len(vals) - step + 1, step):
        addr = 0
        for v in vals[i:i + ac]:
            addr = (addr << 32) | v
        size = 0
        for v in vals[i + ac:i + step]:
            size = (size << 32) | v
        out.append((addr, size))
    return out


def dts_memory(dts):
    """Return (memory ranges, reserved-memory [(name, start, end)])."""
    mem = []
    m = re.search(r"memory@[0-9a-f]+\s*\{[^}]*?reg\s*=\s*<([^>]*)>", dts, re.S)
    if m:
        mem = [(a, a + s) for a, s in parse_reg_cells(m.group(1), 2, 2)]
    res = []
    m = re.search(r"reserved-memory\s*\{(.*?)\n\t\};", dts, re.S)
    if m:
        body = m.group(1)
        ac = int(re.search(r"#address-cells\s*=\s*<(0x[0-9a-f]+|\d+)>", body).group(1), 0)
        sc = int(re.search(r"#size-cells\s*=\s*<(0x[0-9a-f]+|\d+)>", body).group(1), 0)
        for nm in re.finditer(r"\n\t\t(?:\w+:\s*)?([\w,.+-]+(?:@[0-9a-f]+)?)\s*\{(.*?)\n\t\t\};", body, re.S):
            reg = re.search(r"reg\s*=\s*<([^>]*)>", nm.group(2), re.S)
            if reg:
                for a, s in parse_reg_cells(reg.group(1), ac, sc):
                    res.append((nm.group(1), a, a + s, "no-map" in nm.group(2)))
    return mem, res


def file_size(path):
    return os.path.getsize(path)


def hx(v):
    return "0x%08x" % v


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dtb", required=True, help="compiled device tree blob")
    ap.add_argument("--dtc", default="dtc")
    ap.add_argument("--nix", default=os.path.join(ROOT, "nix/boot-splash.nix"))
    ap.add_argument("--env", default=os.path.join(ROOT, "firmware/stage1/tdisplay.env"))
    ap.add_argument("--kernel", help="Image file (size is checked at its load address)")
    ap.add_argument("--initrd", help="initrd.uimg file")
    ap.add_argument("--size", action="append", default=[], metavar="NAME=BYTES",
                    help="override a boot file size, e.g. Image=43802624")
    ap.add_argument("--json", action="store_true", help="also print the report as JSON")
    a = ap.parse_args()

    consts = parse_nix_constants(a.nix)
    fb = consts["framebufferAddress"]
    fb_end = fb + consts["framebufferSize"]
    rec = fb + consts["lifeRecordOffset"]
    rec_end = rec + consts["lifeRecordWindow"]
    logo_bytes = 568 * 1232 * 4
    logo_end = fb + logo_bytes

    dts = decompile_dtb(a.dtb, a.dtc)
    mem, resv = dts_memory(dts)

    sizes = {}
    if a.kernel:
        sizes["Image"] = file_size(a.kernel)
    if a.initrd:
        sizes["initrd.uimg"] = file_size(a.initrd)
    for kv in a.size:
        k, v = kv.split("=", 1)
        sizes[k] = int(v, 0)

    loads = parse_env_loads(a.env)
    intervals = [STAGE1_LOW]
    notes = []
    for name, addr in loads:
        if name in sizes:
            intervals.append(("%s (ext4load %s)" % (name, hx(addr)), addr, addr + sizes[name]))
        elif name.endswith(".bin") or name == "bootargs.txt":
            # firmware blob and bootargs: small; bound them by a documented cap
            cap = 0x400000 if name.startswith("fw_jump") else 0x1000
            intervals.append(("%s (ext4load %s, size capped %s)" % (name, hx(addr), hx(cap)),
                              addr, addr + cap))
        else:
            notes.append("size of %s unknown (loaded at %s); pass --kernel/--initrd/--size" % (name, hx(addr)))
    for name, (s, e) in LIVE.items():
        intervals.append((name, s, e))
    for name, s, e, nomap in resv:
        if s != fb:
            intervals.append(("DT reserved-memory %s" % name, s, e))

    problems = []
    if consts["lifeRecordAddress"] != rec:
        problems.append("lifeRecordAddress %s != framebufferAddress + lifeRecordOffset %s" %
                        (hx(consts["lifeRecordAddress"]), hx(rec)))
    if consts["lifeRecordWindow"] < 5584:
        problems.append("lifeRecordWindow %d is smaller than the 5584-byte record" %
                        consts["lifeRecordWindow"])
    if not any(s <= fb and fb_end <= e for s, e in mem):
        problems.append("splash reservation %s..%s is not inside DT /memory %s" %
                        (hx(fb), hx(fb_end), [(hx(s), hx(e)) for s, e in mem]))
    splash_nodes = [(n, s, e, nm) for n, s, e, nm in resv if s <= rec and rec_end <= e]
    if not splash_nodes:
        problems.append("record window %s..%s is not inside any DT reserved-memory node" %
                        (hx(rec), hx(rec_end)))
    elif not splash_nodes[0][3]:
        problems.append("reserved-memory %s lacks no-map" % splash_nodes[0][0])
    if rec < logo_end:
        problems.append("record window starts at %s, inside the %s logo scanout (ends %s)" %
                        (hx(rec), logo_bytes, hx(logo_end)))
    if rec % 0x1000:
        problems.append("record window is not 4 KiB aligned")
    for name, s, e in intervals:
        if s < rec_end and rec < e:
            problems.append("record window overlaps %s [%s, %s)" % (name, hx(s), hx(e)))

    report = {
        "dtb": os.path.basename(a.dtb),
        "memory": [[hx(s), hx(e)] for s, e in mem],
        "reserved_memory": [{"name": n, "start": hx(s), "end": hx(e), "no_map": nm}
                            for n, s, e, nm in resv],
        "scanout": [hx(fb), hx(logo_end)],
        "record_window": [hx(rec), hx(rec_end)],
        "intervals_checked": [{"name": n, "start": hx(s), "end": hx(e)} for n, s, e in intervals],
        "notes": notes,
        "problems": problems,
    }
    print("Game of Life record memory check (host-side; DTB decompiled with %s)" % a.dtc)
    print("DTB: %s" % a.dtb)
    print("/memory: %s" % ", ".join("%s..%s" % (hx(s), hx(e)) for s, e in mem))
    for n, s, e, nm in resv:
        print("reserved-memory %-28s %s..%s%s" % (n, hx(s), hx(e), " no-map" if nm else ""))
    print("splash scanout (568x1232x4):   %s..%s" % (hx(fb), hx(logo_end)))
    print("life record window:            %s..%s (record %d bytes of %d)" %
          (hx(rec), hx(rec_end), 5584, consts["lifeRecordWindow"]))
    print("intervals checked against the window:")
    for n, s, e in intervals:
        mark = "OVERLAP" if (s < rec_end and rec < e) else "clear"
        print("  %-60s %s..%s  %s" % (n, hx(s), hx(e), mark))
    for n in notes:
        print("note: " + n)
    if problems:
        print("RESULT: REJECT")
        for p in problems:
            print("  - " + p)
    else:
        print("RESULT: OK (window inside the no-map splash reservation, after the scanout, clear of every interval)")
    if a.json:
        print(json.dumps(report, indent=2))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
