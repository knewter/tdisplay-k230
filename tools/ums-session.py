#!/usr/bin/env python3
"""One `ums` session on the board, driven end to end, with a transcript.

    tools/ums-session.py --out docs/evidence/uboot-ums-enumerate.txt

What it does, in order, and why a dedicated driver rather than
tools/capture-boot.py: `ums` blocks until Ctrl-C, a bare byte no --send can
carry, and the interesting checks happen on the HOST while U-Boot is
blocked -- so one process has to hold the console and poll the host at the
same time.

  1. `reboot` from Linux. The CH342 console survives a warm reset
     (docs/evidence/uboot-ums-hardware.txt), so the port is kept open and a
     key is sent every 100 ms until U-Boot's 1 s `bootdelay` is caught.
  2. At `K230# `: `version`, `dm tree`, `mmc list` for the record.
  3. `ums 0 mmc 1`, then watch /dev/disk/by-id/ for a NEW whole-disk entry
     (the card reader, the console bridge and everything else present before
     the command are excluded by snapshot, not by name).
  4. When one appears: read-only host checks -- lsusb, udev properties,
     lsblk, the partition table, and a sha256 of the raw 2 MiB U-Boot slot
     for comparison against the stage 1 on the card. Nothing is written.
  5. Ctrl-C, back to `K230# `, `boot`, wait for the Linux login prompt.

Every byte the board sends is in the transcript, timestamped, as is every
host command and its output. Exit status: 0 when the gadget enumerated and
Linux came back, 3 when it did not enumerate but Linux came back, 1 when
the board was not returned to Linux (say so loudly; the board is shared).
"""
import argparse, hashlib, os, subprocess, sys, time

try:
    import serial
except ImportError:
    sys.exit("need pyserial: nix shell nixpkgs#python3Packages.pyserial")

KILL_LINE = b"\x15"
CTRL_C = b"\x03"
PROMPT = b"K230# "
LOGIN = b"nixos login"
UBOOT_SLOT = 2 * 1024 * 1024


class Session:
    def __init__(self, dev, baud, out):
        self.started = time.time()
        self.log = open(out, "wb", buffering=0)
        self.port = serial.Serial(dev, baud, timeout=0.1, exclusive=True)
        self.buf = b""

    def stamp(self):
        return f"[{time.time() - self.started:8.3f}] "

    def note(self, text):
        line = (self.stamp() + "--- " + text + " ---\n").encode()
        self.log.write(line)
        sys.stdout.write(line.decode())
        sys.stdout.flush()

    def pump(self):
        """Read whatever the board has sent; log it; keep it for matching."""
        chunk = self.port.read(65536)
        if chunk:
            self.log.write(chunk)
            sys.stdout.write(chunk.decode("utf-8", "replace"))
            sys.stdout.flush()
            self.buf = (self.buf + chunk)[-65536:]
        return chunk

    def wait_for(self, token, timeout):
        # The buffer is cleared when a command is SENT (send_line), not
        # here: clearing here would drop a prompt that arrived between the
        # send and this call, and not clearing anywhere let the previous
        # command's prompt satisfy the next match -- which is how the first
        # session (2026-09-22) declared `ums` finished 100 ms after starting
        # it, before the host had any chance to see the gadget.
        end = time.time() + timeout
        while time.time() < end:
            self.pump()
            if token in self.buf:
                return True
        return False

    def send_line(self, text, kill=True):
        if kill:
            self.port.write(KILL_LINE)
            self.port.flush()
            time.sleep(0.05)
        self.note(f"sending: {text}")
        self.buf = b""
        self.port.write(text.encode() + b"\r\n")
        self.port.flush()

    def cmd(self, text, timeout=30):
        self.send_line(text)
        if not self.wait_for(PROMPT, timeout):
            self.note(f"no prompt within {timeout}s after {text!r}")
            return False
        return True

    def host(self, argv, check=False):
        """Run a host command and put its output in the transcript."""
        self.note("host: $ " + " ".join(argv))
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=60)
            out = proc.stdout + proc.stderr
        except Exception as exc:  # noqa: BLE001
            out = f"(failed: {exc})\n"
        self.log.write(out.encode("utf-8", "replace"))
        sys.stdout.write(out)
        sys.stdout.flush()
        return out


def usb_disks():
    try:
        names = os.listdir("/dev/disk/by-id")
    except OSError:
        return set()
    return {n for n in names if n.startswith("usb-") and "-part" not in n}


def lsusb_set():
    try:
        out = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=10).stdout
    except Exception:  # noqa: BLE001
        return set()
    return {ln.split(": ", 1)[1] for ln in out.splitlines() if ": " in ln}


def sha256_range(path, offset, length):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        fh.seek(offset)
        remaining = length
        while remaining:
            chunk = fh.read(min(1 << 20, remaining))
            if not chunk:
                break
            h.update(chunk)
            remaining -= len(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", default="/dev/ttyACM0")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--out", required=True)
    ap.add_argument("--wait-host", type=float, default=300.0,
                    help="seconds to wait for the gadget to appear on the host")
    ap.add_argument("--hammer", type=float, default=20.0)
    ap.add_argument("--slot-len", type=int, default=0,
                    help="bytes to hash at the 2 MiB U-Boot slot (0: skip)")
    args = ap.parse_args()

    s = Session(args.dev, args.baud, args.out)
    status = 1
    try:
        s.note("ums session start")
        disks_before = usb_disks()
        usb_before = lsusb_set()
        s.note("host by-id usb disks before: " + (", ".join(sorted(disks_before)) or "(none)"))
        s.host(["lsusb"])

        # 1. Reboot and catch the countdown.
        s.port.write(b"\r\n"); s.port.flush(); time.sleep(0.3); s.pump()
        s.send_line("reboot", kill=False)
        s.note(f"hammering a key every 100 ms for {args.hammer}s to stop autoboot")
        end = time.time() + args.hammer
        while time.time() < end:
            try:
                s.port.write(b" \x08"); s.port.flush()
            except Exception as exc:  # noqa: BLE001
                s.note(f"port write failed while hammering: {exc}")
                break
            s.pump()
            time.sleep(0.1)
        s.buf = b""
        s.port.write(b"\r\n"); s.port.flush()
        if not s.wait_for(PROMPT, 30):
            s.note("no K230# prompt after the reboot; checking whether Linux came back instead")
            if s.wait_for(LOGIN, 120) or s.wait_for(b"root@nixos", 5):
                s.note("board is in Linux; nothing was done at U-Boot")
                status = 3
            return

        # 2. For the record.
        s.cmd("version")
        s.cmd("dm tree")
        s.cmd("mmc list")

        # 3. ums, and watch the host.
        s.send_line("ums 0 mmc 1")
        s.note(f"watching /dev/disk/by-id for a new usb-* whole disk, up to {args.wait_host}s")
        new = set()
        end = time.time() + args.wait_host
        last_report = 0.0
        while time.time() < end:
            s.pump()
            if PROMPT in s.buf:
                s.note("U-Boot returned to its prompt on its own: ums did not stay up")
                break
            new = usb_disks() - disks_before
            if new:
                break
            if time.time() - last_report > 15:
                last_report = time.time()
                s.note(f"still waiting; new lsusb entries so far: {sorted(lsusb_set() - usb_before) or 'none'}")
            time.sleep(0.5)

        if new:
            s.note("NEW usb disk(s) on the host: " + ", ".join(sorted(new)))
            time.sleep(3)  # let udev finish the partition nodes
            s.pump()
            s.note("new lsusb entries: " + "; ".join(sorted(lsusb_set() - usb_before)))
            s.host(["lsusb"])
            for name in sorted(new):
                byid = f"/dev/disk/by-id/{name}"
                dev = os.path.realpath(byid)
                s.note(f"{byid} -> {dev}")
                s.host(["ls", "-l", "/dev/disk/by-id/"])
                s.host(["udevadm", "info", "--query=property", "--name", dev])
                s.host(["lsblk", "-o", "NAME,SIZE,TRAN,MODEL,VENDOR,SERIAL,TYPE,FSTYPE,LABEL,MOUNTPOINT", dev])
                s.host(["lsblk", "-b", "-o", "NAME,SIZE", dev])
                s.host(["lsblk", "-f", dev])
                s.host(["sh", "-c", f"mount | grep '^{dev}' || echo '(nothing from {dev} is mounted)'"])
                s.host(["cat", f"/sys/class/block/{os.path.basename(dev)}/size"])
                if args.slot_len:
                    s.note(f"sha256 of {args.slot_len} bytes at the 2 MiB U-Boot slot of {dev} (read-only)")
                    try:
                        digest = sha256_range(dev, UBOOT_SLOT, args.slot_len)
                        s.note(f"sha256 = {digest}")
                    except OSError as exc:
                        s.note(f"could not read {dev} unprivileged: {exc}")
            status = 0
        else:
            s.note("no new usb disk appeared on the host")
            s.host(["lsusb"])
            status = 3

        # 4. Out of ums.
        s.note("sending Ctrl-C to leave ums")
        s.buf = b""
        s.port.write(CTRL_C); s.port.flush()
        if not s.wait_for(PROMPT, 20):
            s.port.write(b"\r\n"); s.port.flush()
            s.wait_for(PROMPT, 10)
        gone_at = None
        for _ in range(20):
            if not (usb_disks() - disks_before):
                gone_at = time.time()
                break
            time.sleep(0.5)
        s.note("host: gadget disk " + ("gone after Ctrl-C" if gone_at else "STILL PRESENT 10 s after Ctrl-C"))

        # 5. Back to Linux.
        s.send_line("boot")
        if s.wait_for(LOGIN, 180):
            s.note("Linux login prompt reached; the board is back in Linux")
        else:
            s.note("Linux login prompt NOT seen within 180 s -- the board may not be in Linux")
            status = 1
    finally:
        s.note(f"ums session end, status {status}")
        s.port.close()
        s.log.close()
        sys.exit(status)


if __name__ == "__main__":
    main()
