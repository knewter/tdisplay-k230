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
    ap.add_argument("--cmp", default=None, metavar="IMAGE",
                    help="after the gadget appears, compare the whole card image "
                         "region (the IMAGE's length, from offset 0) against the "
                         "gadget disk, read-only, and record dd's throughput. "
                         "The console keeps being read while it runs")
    ap.add_argument("--flash", default=None, metavar="IMAGE",
                    help="after the gadget appears, WRITE IMAGE to it with the "
                         "project's own tools/flash.sh (by-id path, its "
                         "print-and-confirm step answered by this tool), time "
                         "it, then reset the board and verify the boot: login "
                         "prompt, the board hashing its own stage-1 slots, the "
                         "DSI PHY line. Only with explicit authorisation")
    ap.add_argument("--regs", action="store_true",
                    help="dump usbotg0's DWC2 OTG/device registers with md.l "
                         "before ums and again right after Ctrl-C. GOTGCTL "
                         "bit 19 is B_SESSION_VALID (dwc2_udc_otg_regs.h:91): "
                         "whether the PHY sees VBUS from the cable. DCTL bit 1 "
                         "is soft-disconnect: whether D+ was ever pulled up")
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

        def regs(tag):
            if not args.regs:
                return
            s.note(f"usbotg0 registers, {tag}: GOTGCTL GOTGINT GAHBCFG GUSBCFG GRSTCTL GINTSTS GINTMSK GRXSTSR @0x91500000, then DCFG DCTL DSTS @0x91500800")
            s.cmd("md.l 0x91500000 8")
            s.cmd("md.l 0x91500800 3")

        regs("before ums (core untouched by the gadget driver yet)")

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
            # The speed the HOST negotiated, from sysfs, for every USB device
            # carrying the gadget's vendor id -- to compare with what the
            # board's DSTS said. And the kernel's own account of the attach.
            s.host(["sh", "-c",
                    "for d in /sys/bus/usb/devices/*; do "
                    "[ -f $d/idVendor ] || continue; "
                    "v=$(cat $d/idVendor); p=$(cat $d/idProduct); "
                    "[ \"$v\" = 29f1 ] || continue; "
                    "echo \"$(basename $d): $v:$p speed=$(cat $d/speed) Mb/s version=$(cat $d/version) "
                    "manufacturer=$(cat $d/manufacturer 2>/dev/null) product=$(cat $d/product 2>/dev/null) serial=$(cat $d/serial 2>/dev/null)\"; done"])
            s.host(["sh", "-c", "journalctl -k --since -10min --no-pager 2>/dev/null | grep -i -E 'usb [0-9]+-[0-9.]+|usb-storage|scsi|sd [a-z]' | tail -25"])
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
            if args.cmp and len(new) == 1:
                byid = f"/dev/disk/by-id/{sorted(new)[0]}"
                size = os.path.getsize(args.cmp)
                # Three regions, because the card is NOT expected to equal the
                # image at 3 MiB: U-Boot's k230_set_dtb saves the environment
                # (board/canaan/common/k230_board_common.c) into the env slots
                # at 3 MiB and 3.2 MiB on every boot, so the first cmp of the
                # whole image stopped at byte 3145729 after 0.4 s. Compare
                # everything before, show the env difference as text, then
                # compare everything after -- which is where the bytes and the
                # throughput are.
                ENV0, ENV_END = 3 * 1024 * 1024, 3 * 1024 * 1024 + 256 * 1024
                # cmp -l prints "byteno v1 v2" per differing byte; fold that into
                # 4 KiB blocks and say which partition each falls in. A plain
                # string, not an f-string: awk's braces are not Python's.
                AWK_BLOCKS = (
                    'BEGIN{last=-1} '
                    '{bytes++; b=int(($1-1)/4096); if(b!=last){blocks++; last=b; off=base+b*4096; '
                    ' part=(off<4194304)?"gap":(off<121634816)?"p1(boot)":(off<134217728)?"gap":"p2(root)"; cnt[part]++; '
                    ' if(blocks<=8) printf("  differing block at byte %d (0x%x) in %s\\n", off, off, part)}} '
                    'END{printf("  %d differing bytes in %d differing 4 KiB blocks of %d compared: ", bytes+0, blocks+0, total); '
                    ' for(k in cnt) printf("%s=%d ", k, cnt[k]); printf("\\n")}'
                )
                s.note(f"cmp, read-only, in three regions: [0,{ENV0}) [{ENV0},{ENV_END}) env slots [{ENV_END},{size}) of {byid} against {args.cmp}")
                script = (
                    f"echo '== region A [0, {ENV0}) =='; "
                    f"dd if={byid} bs=1M iflag=count_bytes count={ENV0} status=none | cmp -n {ENV0} - {args.cmp}; echo \"cmp A exit $?\"; "
                    f"echo '== region B: the two 8 KiB environments, as text (device | image) =='; "
                    f"for off in {ENV0} {ENV0 + 200*1024}; do "
                    f"  echo \"-- env copy at $off --\"; "
                    f"  diff <(dd if={byid} bs=1 skip=$off count=8192 status=none | tail -c +5 | tr '\\0' '\\n' | grep .) "
                    f"       <(dd if={args.cmp} bs=1 skip=$off count=8192 status=none | tail -c +5 | tr '\\0' '\\n' | grep .) "
                    f"  && echo '   (identical text)'; done; "
                    f"echo '== region B2: partition 1 files, read through debugfs on the gadget (no mount) vs the same files in the image =='; "
                    f"dd if={args.cmp} bs=1M skip=4 count=112 of={args.out}.p1 status=none; "
                    f"for f in Image fw_jump_add_uboot_head.bin k230-tdisplay.dtb bootargs.txt initrd.uimg; do "
                    f"  a=$(/nix/store/xkbzmsvva53p5vbzm8j65hj8bkv4bhrc-e2fsprogs-1.47.4-bin/bin/debugfs -R \"cat /$f\" {args.out}.p1 2>/dev/null | sha256sum | cut -c1-64); "
                    f"  b=$(/nix/store/xkbzmsvva53p5vbzm8j65hj8bkv4bhrc-e2fsprogs-1.47.4-bin/bin/debugfs -R \"cat /$f\" {byid}-part1 2>/dev/null | sha256sum | cut -c1-64); "
                    f"  n=$(/nix/store/xkbzmsvva53p5vbzm8j65hj8bkv4bhrc-e2fsprogs-1.47.4-bin/bin/debugfs -R \"cat /$f\" {byid}-part1 2>/dev/null | wc -c); "
                    f"  [ \"$a\" = \"$b\" ] && v=IDENTICAL || v=DIFFERENT; "
                    f"  printf '  %-28s %s  %9d bytes  %s\\n' $f $b $n $v; done; rm -f {args.out}.p1; "
                    f"echo '== region C [{ENV_END}, {size}): the whole rest of the image, every byte, cmp -l aggregated per 4 KiB block =='; "
                    f"start=$(date +%s.%N); "
                    f"dd if={byid} bs=4M iflag=skip_bytes,count_bytes skip={ENV_END} count={size - ENV_END} status=progress 2>{args.out}.dd "
                    f"| cmp -l - <(dd if={args.cmp} bs=4M iflag=skip_bytes skip={ENV_END} status=none) "
                    f"| awk -v base={ENV_END} -v total={int((size - ENV_END + 4095) / 4096)} '{AWK_BLOCKS}'; "
                    f"end=$(date +%s.%N); "
                    f"tail -c 600 {args.out}.dd | tr '\\r' '\\n' | grep 'copied' | tail -1; "
                    f"echo \"region C read complete; elapsed $(echo \"$end - $start\" | bc) s\""
                )
                s.note("host: $ " + script)
                proc = subprocess.Popen(["bash", "-c", script], stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, text=True)
                last = 0.0
                while proc.poll() is None:
                    s.pump()
                    if time.time() - last > 30:
                        last = time.time()
                        try:
                            with open(args.out + ".dd", "rb") as fh:
                                fh.seek(0, 2); fh.seek(max(0, fh.tell() - 200))
                                prog = fh.read().decode("utf-8", "replace").replace("\r", "\n").strip().splitlines()
                            s.note("dd progress: " + (prog[-1] if prog else "(none yet)"))
                        except OSError:
                            pass
                    time.sleep(0.05)
                out = proc.stdout.read()
                s.log.write(out.encode("utf-8", "replace")); sys.stdout.write(out); sys.stdout.flush()
                a_ok = "cmp A exit 0" in out
                files_ok = out.count(" IDENTICAL") == 5
                c_done = "region C read complete" in out
                s.note(f"image cmp: region A {'IDENTICAL' if a_ok else 'DIFFERENT'}; partition-1 files {'all 5 IDENTICAL' if files_ok else 'NOT all identical'}; region C {'read to the end, block statistics above' if c_done else 'NOT completed'}; region B is the saved environment, shown above")
            status = 0
        else:
            s.note("no new usb disk appeared on the host")
            s.host(["lsusb"])
            status = 3

        wrote = False
        if args.flash and len(new) == 1:
            byid = f"/dev/disk/by-id/{sorted(new)[0]}"
            size = os.path.getsize(args.flash)
            s.note(f"WRITE: tools/flash.sh {args.flash} {byid} ({size} bytes); confirmation = last 12 chars of the by-id path, supplied by this tool")
            proc = subprocess.Popen(["./tools/flash.sh", args.flash, byid], stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            proc.stdin.write(byid[-12:] + "\n"); proc.stdin.flush(); proc.stdin.close()
            t0 = time.time(); last = 0.0; chunks = []
            os.set_blocking(proc.stdout.fileno(), False)
            while proc.poll() is None:
                s.pump()
                try:
                    data = proc.stdout.read()
                except (BlockingIOError, TypeError):
                    data = None
                if data:
                    chunks.append(data)
                    tail = data.replace("\r", "\n").strip().splitlines()
                    if tail and time.time() - last > 20:
                        last = time.time(); s.note("flash.sh: " + tail[-1][:120])
                time.sleep(0.05)
            rest = proc.stdout.read() or ""
            out = "".join(chunks) + rest
            s.log.write(out.replace("\r", "\n").encode("utf-8", "replace")); sys.stdout.write(out); sys.stdout.flush()
            elapsed = time.time() - t0
            s.note(f"flash.sh exit status {proc.returncode}; {size} bytes in {elapsed:.1f} s = {size / elapsed / 1e6:.1f} MB/s end to end (including flash.sh's own confirm step and final sync)")
            wrote = proc.returncode == 0
            if not wrote:
                s.note("WRITE FAILED -- stopping here; the board is left at the U-Boot prompt in ums for the coordinator")
                status = 1
                return

        # 4. Out of ums.
        s.note("sending Ctrl-C to leave ums")
        s.buf = b""
        s.port.write(CTRL_C); s.port.flush()
        if not s.wait_for(PROMPT, 20):
            s.port.write(b"\r\n"); s.port.flush()
            s.wait_for(PROMPT, 10)
        regs("after Ctrl-C (the driver has probed, run, and been released)")
        gone_at = None
        for _ in range(20):
            if not (usb_disks() - disks_before):
                gone_at = time.time()
                break
            time.sleep(0.5)
        s.note("host: gadget disk " + ("gone after Ctrl-C" if gone_at else "STILL PRESENT 10 s after Ctrl-C"))

        # 5. Back to Linux. After a write, `reset` rather than `boot`, so the
        #    SPL and U-Boot that run are the ones just written to the card.
        s.send_line("reset" if wrote else "boot")
        if s.wait_for(LOGIN, 240):
            s.note("Linux login prompt reached; the board is back in Linux")
            if wrote:
                time.sleep(6); s.pump()
                s.note("post-write checks on the board: the card's own stage-1 slots and the DSI PHY line")
                for c in ("dd if=/dev/mmcblk1 bs=1 skip=$((0x100000)) count=223348 2>/dev/null | sha256sum",
                          "dd if=/dev/mmcblk1 bs=1 skip=$((0x200000)) count=350046 2>/dev/null | sha256sum",
                          "dmesg | grep -m1 hsfreqrange",
                          "dmesg | grep -c 'BTF mismatch'",
                          "uptime"):
                    s.send_line(c)
                    end = time.time() + 12
                    while time.time() < end:
                        s.pump(); time.sleep(0.05)
        else:
            s.note("Linux login prompt NOT seen within 240 s -- the board may not be in Linux")
            status = 1
    finally:
        s.note(f"ums session end, status {status}")
        s.port.close()
        s.log.close()
        sys.exit(status)


if __name__ == "__main__":
    main()
