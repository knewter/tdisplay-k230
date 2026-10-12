#!/usr/bin/env python3
"""One physical CPU0 echo/ping session (coprocessor task 3.3), with a transcript.

    flock /tmp/k230-board.lock tools/small-core-echo-session.py --out T.txt --crc32 7492e46f [--release]

Follows docs/evidence/second-core/echo-runbook.md. The payload must already
be on the boot partition as /small-core-echo.bin.

  1. `reboot` from Linux and stop U-Boot's autoboot.
  2. Record `version`, `help boot_baremetal`, `help dcache`, `dcache`
     (turned off when it reports ON), `bdinfo`.
  3. `ext4load` the payload to 0x7000000; require 0xe0 bytes and --crc32.
  4. Only with --release: `boot_baremetal 0 0x7000000 0x5000`, read the
     status line, send four requests through the slot page (value first,
     sequence last), read each response line once after `sleep 1` (one
     retry after 3 s), read the never-requested line 5 (its rsp_seq must still be 0) and the
     counters.
  5. `reset` and wait for Linux.

Exit status: 0 when every step ran and Linux came back; 2 when a check
refused the release or a response was wrong; 1 when the board was not
returned to Linux.
"""
import argparse, importlib.util, re, sys, time
from pathlib import Path

spec = importlib.util.spec_from_file_location("ums", Path(__file__).with_name("ums-session.py"))
ums = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ums)

PAGE = 0x7002000
MAGIC = 0x4f484345
# 32 MiB of DRAM well away from the payload window, read only.
EVICT = "crc32 0x10000000 0x2000000"
REQUESTS = [(1, 0x11111111), (2, 0xdeadbeef), (3, 0xffffffff), (4, 0x12345678)]


def run(s, command, timeout=30):
    """One command, then drain until quiet: this console echoes each reply
    twice, and the duplicate prompt would satisfy the next command's wait."""
    out = s.cmd_output(command, timeout)
    if out is None:
        return None
    quiet = time.time() + 0.5
    while time.time() < quiet:
        if s.pump():
            quiet = time.time() + 0.5
    return s.buf


def cells(output, address, count):
    """`count` 32-bit words starting at address, from md.l's 4-per-line dump."""
    words = []
    for line in range(address, address + 4 * count, 16):
        m = re.search(rb"%08x:((?: [0-9a-f]{8})+)" % line, output or b"")
        if not m:
            return None
        words += [int(w, 16) for w in m[1].split()]
    return words[:count]


def back_in_linux(s, timeout):
    end = time.time() + timeout
    while time.time() < end:
        s.pump()
        if ums.LOGIN in s.buf or b"root@nixos" in s.buf:
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", default="/dev/ttyACM0")
    ap.add_argument("--out", required=True)
    ap.add_argument("--crc32", required=True)
    ap.add_argument("--release", action="store_true")
    ap.add_argument("--hammer", type=float, default=12.0)
    ap.add_argument("--evict", action="store_true",
                    help="U-Boot has no dcache command: after each request write and before each read, "
                         "read 32 MiB of unrelated DRAM (crc32) so CPU1's caches write back and drop the slot page")
    args = ap.parse_args()

    s = ums.Session(args.dev, 115200, args.out)
    status = 1
    try:
        s.note("small-core echo session start" + (" (release)" if args.release else " (dry run)"))
        s.port.write(b"\r\n"); s.port.flush(); time.sleep(0.3); s.pump()
        s.send_line("reboot", kill=False)
        end = time.time() + args.hammer
        while time.time() < end:
            s.port.write(b" \x08"); s.port.flush(); s.pump(); time.sleep(0.1)
        s.buf = b""
        s.port.write(b"\r\n"); s.port.flush()
        if not s.wait_for(ums.PROMPT, 30):
            s.note("no K230# prompt; checking for Linux")
            if back_in_linux(s, 120):
                status = 2
            return

        run(s, "version")
        helped = run(s, "help boot_baremetal")
        run(s, "help dcache")
        dc = run(s, "dcache")
        if dc and re.search(rb"dcache is ON|Data \(writethrough\) Cache is ON|cache is ON", dc, re.I):
            run(s, "dcache off")
            dc = run(s, "dcache")
        s.note("dcache state: " + (re.sub(rb"\s+", b" ", dc or b"").decode(errors="replace")[-80:]))
        run(s, "bdinfo")
        run(s, "ext4load mmc 1:1 0x7000000 /small-core-echo.bin")
        env = run(s, "printenv fileaddr filesize")
        crc = run(s, "crc32 0x7000000 0xe0")

        refusals = []
        if not helped or b"Unknown command" in helped:
            refusals.append("boot_baremetal unavailable")
        if not env or not re.search(rb"fileaddr=0?x?7000000", env) or not re.search(rb"filesize=0*e0\b", env):
            refusals.append("fileaddr/filesize differ")
        if not crc or args.crc32.lower().removeprefix("0x").encode() not in crc:
            refusals.append("crc32 differs")
        s.note("RELEASE REFUSED: " + "; ".join(refusals) if refusals else "pre-release checks PASS")
        verdict = 2 if refusals else 0

        def evict():
            if args.evict:
                run(s, EVICT, 60)

        if args.release and not refusals:
            s.note("releasing physical CPU0")
            run(s, "boot_baremetal 0 0x7000000 0x5000", 30)
            time.sleep(1)
            evict()
            st = cells(run(s, f"md.l 0x{PAGE + 0x40:x} 12"), PAGE + 0x40, 12)
            ok = bool(st) and st[6] == MAGIC and st[2] == 0 and st[3] == 0
            if st:
                s.note(f"status: heartbeat={st[0] | st[1] << 32} mhartid=0x{st[2] | st[3] << 32:x} "
                       f"misa=0x{st[4] | st[5] << 32:x} magic=0x{st[6]:08x} served={st[7]} last_seq={st[8]}")
            results = []
            for seq, value in REQUESTS:
                run(s, f"mw.l 0x{PAGE + 4:x} 0x{value:08x} 1")
                run(s, f"mw.l 0x{PAGE:x} 0x{seq:x} 1")
                evict()
                want = [seq, (value + 1) & 0xffffffff, ~value & 0xffffffff, seq]
                line = PAGE + 0x100 + 0x40 * (seq & 7)
                got = None
                for wait in (1, 3):
                    time.sleep(wait)
                    evict()
                    got = cells(run(s, f"md.l 0x{line:x} 4"), line, 4)
                    if got == want:
                        break
                good = got == want
                results.append(good)
                s.note(f"request seq={seq} value=0x{value:08x}: got {['%08x' % w for w in got] if got else None} "
                       f"want {['%08x' % w for w in want]} -> {'OK' if good else 'WRONG'}")
            evict()
            neg = cells(run(s, f"md.l 0x{PAGE + 0x240:x} 4"), PAGE + 0x240, 4)
            fin = cells(run(s, f"md.l 0x{PAGE + 0x58:x} 3"), PAGE + 0x58, 3)
            # CPU0 zeroes only each response line's rsp_seq word at start
            # (small-core-echo.S); the other words of a never-answered line
            # are whatever DRAM held, so "not answered" is rsp_seq == 0.
            neg_ok = bool(neg) and neg[0] == 0
            fin_ok = fin == [MAGIC, 4, 4]
            alive = run(s, "echo CPU1_UBOOT_PROMPT_ALIVE") is not None
            s.note(f"negative control line 5: {neg} -> {'OK' if neg_ok else 'WRONG'}; counters {fin} -> {'OK' if fin_ok else 'WRONG'}")
            passed = ok and all(results) and neg_ok and fin_ok and alive
            s.note(f"ECHO VERDICT: {'PASS' if passed else 'FAIL'} status={'OK' if ok else 'WRONG'} "
                   f"responses={sum(results)}/4 prompt={'alive' if alive else 'lost'}")
            if not passed:
                verdict = 2

        s.send_line("reset")
        s.wait_for(b"U-Boot SPL", 60)
        s.buf = b""
        if back_in_linux(s, 240):
            s.note("Linux login prompt is back")
            status = verdict
        else:
            s.note("LINUX DID NOT COME BACK -- board needs recovery")
    finally:
        s.note(f"session end, status {status}")
        s.port.close()
    sys.exit(status)


if __name__ == "__main__":
    main()
