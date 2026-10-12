#!/usr/bin/env python3
"""One physical CPU0 heartbeat session, driven end to end, with a transcript.

    flock /tmp/k230-board.lock tools/small-core-heartbeat-session.py --out T.txt [--release]

Follows docs/evidence/second-core/heartbeat-runbook.md. The payload must
already be on the boot partition as /small-core-heartbeat.bin.

  1. `reboot` from Linux and stop U-Boot's autoboot (as tools/ums-session.py).
  2. Record `version`, `help boot_baremetal`, `bdinfo`, `mmc_boot_dev_num`.
  3. `ext4load` the payload to 0x7000000; require 80 bytes at that address
     and the expected CRC32 (`--crc32`).
  4. Only with --release: `boot_baremetal 0 0x7000000 0x5000`, then read
     the three output pages once each, at least one second apart, then a
     prompt-liveness echo. Without --release nothing is released.
  5. `reset` (never `boot`: it loads bootargs.txt over the payload) and wait
     for Linux.

Exit status: 0 when every step ran and Linux came back; 2 when a check
refused the release; 1 when the board was not returned to Linux.
"""
import argparse, importlib.util, re, sys, time
from pathlib import Path

spec = importlib.util.spec_from_file_location("ums", Path(__file__).with_name("ums-session.py"))
ums = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ums)

LOAD = 0x7000000
SIZE = 80
WINDOW = 0x5000
PAGES = ((0x7002000, 6), (0x7003000, 2), (0x7004000, 2))


def words(output, address):
    """32-bit cells of one `md.l` line starting at address."""
    m = re.search(rb"%08x:((?: [0-9a-f]{8})+)" % address, output or b"")
    return [int(w, 16) for w in m[1].split()] if m else None


def bdinfo_conflicts(output):
    """Named U-Boot regions from bdinfo that intersect the payload window."""
    found = []
    for key in (b"relocaddr", b"sp start", b"FB base", b"Early malloc usage"):
        m = re.search(key + rb"\s*=\s*0x([0-9a-f]+)", output or b"")
        if m and LOAD <= int(m[1], 16) < LOAD + WINDOW:
            found.append(key.decode())
    return found


def back_in_linux(s, timeout):
    """The serial console shows a login prompt or an autologin root shell."""
    end = time.time() + timeout
    while time.time() < end:
        s.pump()
        if ums.LOGIN in s.buf or b"root@nixos" in s.buf:
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", default="/dev/ttyACM0")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--out", required=True)
    ap.add_argument("--crc32", required=True, help="expected crc32 of the payload, hex")
    ap.add_argument("--release", action="store_true")
    ap.add_argument("--hammer", type=float, default=12.0)
    ap.add_argument("--gap", type=float, default=1.2, help="seconds before each page read (runbook: at least 1)")
    args = ap.parse_args()

    s = ums.Session(args.dev, args.baud, args.out)
    status = 1
    try:
        s.note("small-core heartbeat session start" + (f" (release, gap {args.gap}s)" if args.release else " (dry run)"))
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
                s.note("board is in Linux; nothing was done at U-Boot")
                status = 2
            return

        s.cmd("version")
        helped = s.cmd_output("help boot_baremetal")
        bd = s.cmd_output("bdinfo")
        s.cmd("printenv mmc_boot_dev_num")
        s.cmd("ext4load mmc 1:1 0x7000000 /small-core-heartbeat.bin")
        env = s.cmd_output("printenv fileaddr filesize")
        crc = s.cmd_output("crc32 0x7000000 0x50")

        refusals = []
        if not helped or b"Unknown command" in helped:
            refusals.append("boot_baremetal unavailable")
        if bdinfo_conflicts(bd):
            refusals.append("bdinfo region in window: " + ", ".join(bdinfo_conflicts(bd)))
        if not env or not re.search(rb"fileaddr=0?x?7000000", env) or not re.search(rb"filesize=0*50\b", env):
            refusals.append("fileaddr/filesize differ")
        if not crc or args.crc32.lower().removeprefix("0x").encode() not in crc:
            refusals.append("crc32 differs")
        if refusals:
            s.note("RELEASE REFUSED: " + "; ".join(refusals))
            status_on_return = 2
        else:
            s.note("pre-release checks PASS")
            status_on_return = 0

        if args.release and not refusals:
            s.note("releasing physical CPU0")
            s.cmd("boot_baremetal 0 0x7000000 0x5000", timeout=30)
            counters = []
            for address, count in PAGES:
                time.sleep(args.gap)
                out = s.cmd_output(f"md.l 0x{address:x} {count}")
                cells = words(out, address)
                if cells:
                    counter = cells[0] | (cells[1] << 32)
                    counters.append(counter)
                    extra = ""
                    if len(cells) >= 6:
                        extra = f" mhartid=0x{cells[2] | (cells[3] << 32):x} misa=0x{cells[4] | (cells[5] << 32):x}"
                    s.note(f"page 0x{address:x}: counter={counter}{extra}")
                else:
                    s.note(f"page 0x{address:x}: unreadable")
            alive = s.cmd("echo CPU1_UBOOT_PROMPT_ALIVE")
            rising = len(counters) == 3 and counters[0] < counters[1] < counters[2]
            s.note(f"HEARTBEAT VERDICT: {'PASS' if rising and alive else 'FAIL'} counters={counters} prompt={'alive' if alive else 'lost'}")
            if not (rising and alive):
                status_on_return = 2

        s.send_line("reset")
        if back_in_linux(s, 240):
            s.note("Linux login prompt is back")
            status = status_on_return
        else:
            s.note("LINUX DID NOT COME BACK -- board needs recovery")
    finally:
        s.note(f"session end, status {status}")
        s.port.close()
    sys.exit(status)


if __name__ == "__main__":
    main()
