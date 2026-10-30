#!/usr/bin/env python3
"""Check that the stage 1 ttfx engine arena overlaps no boot-time owner.

openspec change the-boot-plays-terminal-text-effects, design D14.  Host-side;
nothing touches a board.  The arena is nix/textfx/arena.nix (address, size, the
private engine stack carved from its top).

Reads:
  * the compiled DTB, decompiled with `dtc -I dtb -O dts`: /memory and every
    /reserved-memory child (no-map or not: stage 1 must not scribble on any);
  * nix/boot-splash.nix: the splash reservation;
  * firmware/stage1/tdisplay.env: the `blinux` ext4load addresses;
  * boot file sizes (--size NAME=BYTES, or --kernel/--initrd files);
  * the live U-Boot placement from the physical-board capture in
    docs/evidence/stage1-memory-map.md 2.1/2.2 (relocation, LMB reservation,
    relocated initrd and DTB), overridable;
  * --heap-peaks FILE: "effect KiB" lines; every effect in the default list must
    peak at no more than arenaSize / arenaMarginDivisor.

Rejects (exit 1) an arena that is outside /memory, is not aligned, overlaps any
interval, is too small for the largest peak with the margin, or leaves no room
for the private stack.

Usage: check-boot-textfx-memory.py --dtb k230-tdisplay.dtb --size Image=42752512 ... [--heap-peaks FILE]
"""
import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# docs/evidence/stage1-memory-map.md 2.1 and 2.2 (physical board, docs/evidence/uboot-usb-host-coexist.txt)
LIVE = {
    "U-Boot relocated code, heap, stack, LMB reservation": (0x3FB37920, 0x40000000),
    "initrd relocated by bootm": (0x3E12F000, 0x3FB36D4F),
    "dtb relocated by bootm (fdt_high 0xa100000)": (0x0A0EB000, 0x0A100000),
}
# the kernel's CMA pool starts at 0x1e000000 on the 6.6 vendor kernel (1.7 of the same document);
# its end is placed against the relocated initrd.  Conservative here: a stage 1 arena is not
# allowed to stray into it even though Linux does not exist yet.
CMA = ("Linux CMA pool (observed on the vendor kernel)", 0x1E000000, 0x3E12F000)
OPENSBI = ("OpenSBI fw_jump and its reservations", 0x0, 0x60000)
STAGE1_LOW = ("stage-1 SPL/U-Boot/OpenSBI load region", 0x0, 0x400000)
SCRATCH = [
    ("loadaddr / CONFIG_SYS_LOAD_ADDR", 0x0C000000, 0x0C100000),
    ("force_dtb probe scratch", 0x15000000, 0x15010000),
]
KERNEL_BSS_MARGIN = 0x1000000  # Image file size + 16 MiB for .bss and relocation slack
INITRD_GROWTH = 1.25           # the initrd may grow before the next install


def nix_consts(path, keys):
    text = open(path).read()
    out = {}
    for k in keys:
        m = re.search(r'%s\s*=\s*"?(0x[0-9a-fA-F]+|\d+)"?' % k, text)
        if not m:
            sys.exit("error: %s not found in %s" % (k, path))
        out[k] = int(m.group(1), 0)
    return out


def env_loads(path):
    loads = []
    for line in open(path):
        if line.startswith("blinux="):
            for m in re.finditer(r"ext4load\s+\S+\s+\S+\s+(0x[0-9a-fA-F]+)\s+/(\S+?)(?:\s|;|$)", line):
                loads.append((m.group(2).replace("${k}", "Image").replace("${dtb}", "dtb"), int(m.group(1), 16)))
    if not loads:
        sys.exit("error: no ext4load entries in blinux of %s" % path)
    return loads


def cells(txt, ac, sc):
    vals = [int(v, 16) for v in re.findall(r"0x[0-9a-fA-F]+", txt)]
    out, step = [], ac + sc
    for i in range(0, len(vals) - step + 1, step):
        a = s = 0
        for v in vals[i:i + ac]:
            a = (a << 32) | v
        for v in vals[i + ac:i + step]:
            s = (s << 32) | v
        out.append((a, s))
    return out


def dts_memory(dts):
    mem, res = [], []
    m = re.search(r"memory@[0-9a-f]+\s*\{[^}]*?reg\s*=\s*<([^>]*)>", dts, re.S)
    if m:
        mem = [(a, a + s) for a, s in cells(m.group(1), 2, 2)]
    m = re.search(r"reserved-memory\s*\{(.*?)\n\t\};", dts, re.S)
    if m:
        body = m.group(1)
        ac = int(re.search(r"#address-cells\s*=\s*<(0x[0-9a-f]+|\d+)>", body).group(1), 0)
        sc = int(re.search(r"#size-cells\s*=\s*<(0x[0-9a-f]+|\d+)>", body).group(1), 0)
        for nm in re.finditer(r"\n\t\t(?:\w+:\s*)?([\w,.+-]+(?:@[0-9a-f]+)?)\s*\{(.*?)\n\t\t\};", body, re.S):
            reg = re.search(r"reg\s*=\s*<([^>]*)>", nm.group(2), re.S)
            if reg:
                for a, s in cells(reg.group(1), ac, sc):
                    res.append((nm.group(1), a, a + s))
    return mem, res


def hx(v):
    return "0x%08x" % v


def check(dtb, dtc, nix_arena, nix_splash, env, sizes, peaks):
    c = nix_consts(nix_arena, ["arenaAddress", "arenaSize", "arenaMarginDivisor", "engineStackSize"])
    sp = nix_consts(nix_splash, ["framebufferAddress", "framebufferSize"])
    a0, size = c["arenaAddress"], c["arenaSize"]
    a1 = a0 + size
    stack0 = a1 - c["engineStackSize"]
    dts = subprocess.run([dtc, "-I", "dtb", "-O", "dts", dtb], check=True, capture_output=True, text=True).stdout
    mem, resv = dts_memory(dts)

    intervals = [STAGE1_LOW, OPENSBI, CMA, *SCRATCH,
                 ("splash reservation", sp["framebufferAddress"], sp["framebufferAddress"] + sp["framebufferSize"])]
    notes = []
    for name, addr in env_loads(env):
        if name not in sizes:
            notes.append("size of %s unknown (loaded at %s); pass --size" % (name, hx(addr)))
            continue
        n = sizes[name]
        if name == "Image":
            n += KERNEL_BSS_MARGIN
        if name == "initrd.uimg":
            n = int(n * INITRD_GROWTH)
        intervals.append(("%s (ext4load %s, with growth margin)" % (name, hx(addr)), addr, addr + n))
    for name, (s, e) in LIVE.items():
        intervals.append((name, s, e))
    for name, s, e in resv:
        intervals.append(("DT reserved-memory %s" % name, s, e))

    problems = []
    if not any(s <= a0 and a1 <= e for s, e in mem):
        problems.append("arena %s..%s is not inside DT /memory %s" % (hx(a0), hx(a1), [(hx(s), hx(e)) for s, e in mem]))
    if a0 % 0x10000 or size % 0x10000:
        problems.append("arena address and size must be 64 KiB aligned")
    if c["engineStackSize"] < 0x8000 or c["engineStackSize"] * 4 > size:
        problems.append("engine stack %#x is below 32 KiB (the engine needs 24 KiB) or over a quarter of the arena" % c["engineStackSize"])
    for name, s, e in intervals:
        if s < a1 and a0 < e:
            problems.append("arena overlaps %s [%s, %s)" % (name, hx(s), hx(e)))
    limit = (size - c["engineStackSize"]) // c["arenaMarginDivisor"]
    worst = ("", 0)
    for eff, kib in peaks.items():
        if kib * 1024 > worst[1]:
            worst = (eff, kib * 1024)
        if kib * 1024 > limit:
            problems.append("effect %s peaks at %d KiB, over the margin limit %d KiB (arena %d KiB / %d)" %
                            (eff, kib, limit // 1024, (size - c["engineStackSize"]) // 1024, c["arenaMarginDivisor"]))
    return dict(arena=(a0, a1), stack=(stack0, a1), mem=mem, resv=resv, intervals=intervals, notes=notes,
                problems=problems, limit=limit, worst=worst)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dtb", required=True)
    ap.add_argument("--dtc", default="dtc")
    ap.add_argument("--arena", default=os.path.join(ROOT, "nix/textfx/arena.nix"))
    ap.add_argument("--splash", default=os.path.join(ROOT, "nix/boot-splash.nix"))
    ap.add_argument("--env", default=os.path.join(ROOT, "firmware/stage1/tdisplay.env"))
    ap.add_argument("--kernel")
    ap.add_argument("--initrd")
    ap.add_argument("--size", action="append", default=[], metavar="NAME=BYTES")
    ap.add_argument("--heap-peaks", help='file of "effect KiB" lines (the default list must fit the margin)')
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    sizes = {}
    if a.kernel:
        sizes["Image"] = os.path.getsize(a.kernel)
    if a.initrd:
        sizes["initrd.uimg"] = os.path.getsize(a.initrd)
    for kv in a.size:
        k, v = kv.split("=", 1)
        sizes[k] = int(v, 0)
    peaks = {}
    if a.heap_peaks:
        for line in open(a.heap_peaks):
            p = line.split()
            if len(p) == 2 and p[1].isdigit():
                peaks[p[0]] = int(p[1])
    r = check(a.dtb, a.dtc, a.arena, a.splash, a.env, sizes, peaks)
    a0, a1 = r["arena"]
    print("ttfx stage 1 arena memory check (host-side; DTB decompiled with %s)" % a.dtc)
    print("DTB: %s" % os.path.basename(a.dtb))
    print("/memory: %s" % ", ".join("%s..%s" % (hx(s), hx(e)) for s, e in r["mem"]))
    for n, s, e in r["resv"]:
        print("reserved-memory %-28s %s..%s" % (n, hx(s), hx(e)))
    print("arena:        %s..%s (%d MiB); private engine stack %s..%s" % (hx(a0), hx(a1), (a1 - a0) >> 20, hx(r["stack"][0]), hx(r["stack"][1])))
    if peaks:
        print("heap margin:  limit %d KiB per effect; worst measured %s %d KiB over %d effects" %
              (r["limit"] // 1024, r["worst"][0], r["worst"][1] // 1024, len(peaks)))
    print("intervals checked against the arena:")
    for n, s, e in r["intervals"]:
        print("  %-62s %s..%s  %s" % (n, hx(s), hx(e), "OVERLAP" if (s < a1 and a0 < e) else "clear"))
    for n in r["notes"]:
        print("note: " + n)
    if r["problems"]:
        print("RESULT: REJECT")
        for p in r["problems"]:
            print("  - " + p)
    else:
        print("RESULT: OK (arena inside /memory, clear of every load, relocation, reservation and the CMA pool)")
    if a.json:
        print(json.dumps({"arena": [hx(a0), hx(a1)], "problems": r["problems"]}))
    return 1 if r["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
