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
  2. At `K230# `: `version`, `dm tree`, `mmc list` for the record. With
     `--check-usb-host`, record the U-Boot USB and driver trees before UMS
     and again after leaving it.
  3. `ums 0 mmc 1`, then watch /dev/disk/by-id/ for a NEW whole-disk entry
     (the card reader, the console bridge and everything else present before
     the command are excluded by snapshot, not by name).
  4. When one appears: read-only host checks -- lsusb, udev properties,
     lsblk, the partition table, and a sha256 of the raw 2 MiB U-Boot slot
     for comparison against the stage 1 on the card. Nothing is written.
  5. Ctrl-C, back to `K230# `, `boot`, wait for the Linux login prompt.

Every byte the board sends is in the transcript, timestamped, as is every
host command and its output. Exit status: 0 when the gadget enumerated and
Linux came back, 3 when it did not enumerate but Linux came back, 4 when
that UMS path succeeded but the opt-in host coexistence verdict failed, and
1 when the board was not returned to Linux (say so loudly; the board is
shared).
"""
import argparse, hashlib, os, re, shlex, subprocess, sys, time
from pathlib import Path

KILL_LINE = b"\x15"
CTRL_C = b"\x03"
PROMPT = b"K230# "
LOGIN = b"nixos login"
UBOOT_SLOT = 2 * 1024 * 1024
UMS_DISK = "usb-Linux_UMS_disk_0-0:0"


def validate_flash_target(disks, properties, sectors, expected_sectors):
    """Fail closed before auto-confirming the board's flash.sh prompt."""
    if disks != {UMS_DISK}:
        raise ValueError(f"expected only {UMS_DISK}, discovered {sorted(disks)}")
    expected = {"DEVTYPE": "disk", "ID_BUS": "usb",
                "ID_VENDOR_ID": "29f1", "ID_MODEL_ID": "0230"}
    for key, value in expected.items():
        if properties.get(key) != value:
            raise ValueError(f"unexpected {key}: {properties.get(key)!r}")
    if expected_sectors <= 0 or sectors != expected_sectors:
        raise ValueError(f"card size {sectors} sectors != expected {expected_sectors}")


def verify_written_image(session, image_path, target):
    """Read through the device, bypassing host page cache, before boot."""
    size = os.path.getsize(image_path)
    session.note(f"verifying all {size} written bytes with direct I/O before leaving ums")
    reader = subprocess.Popen(
        ["dd", f"if={target}", "bs=4M", "iflag=direct,count_bytes",
         f"count={size}", "status=none"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    verify = None
    started = last = time.monotonic()
    try:
        verify = subprocess.Popen(["cmp", "-n", str(size), str(image_path), "-"],
                                  stdin=reader.stdout, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT)
        reader.stdout.close()
        while verify.poll() is None:
            session.pump()
            now = time.monotonic()
            if now - last >= 30:
                last = now
                session.note(f"readback still running, elapsed {now - started:.0f}s")
            if now - started > 900:
                session.note("readback timed out")
                verify.kill()
                break
            time.sleep(0.01)
        output, _ = verify.communicate()
        session.log.write(output)
        try:
            reader.wait(timeout=5)
        except subprocess.TimeoutExpired:
            reader.kill()
            reader.wait()
        session.log.write(reader.stderr.read())
        if verify.returncode or reader.returncode:
            session.note(f"READBACK FAILED (dd {reader.returncode}, cmp {verify.returncode}); board remains in ums for recovery")
            return False
        session.note(f"readback PASS: all {size} bytes identical, {time.monotonic() - started:.1f}s")
        return True
    finally:
        for process in (verify, reader):
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()
        for stream in (reader.stdout, reader.stderr,
                       verify.stdout if verify is not None else None):
            if stream is not None:
                stream.close()


class Session:
    def __init__(self, dev, baud, out):
        try:
            import serial
        except ImportError:
            sys.exit("need pyserial: nix shell nixpkgs#python3Packages.pyserial")
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
        return self.cmd_output(text, timeout) is not None

    def cmd_output(self, text, timeout=30):
        """Send one command and return its complete prompt-delimited output."""
        self.send_line(text)
        if not self.wait_for(PROMPT, timeout):
            self.note(f"no prompt within {timeout}s after {text!r}")
            return None
        return self.buf

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


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_pull_arguments(pull, pull_output, expected_sectors, expected_sha256):
    """Validate paths before opening the serial port or a UMS disk.

    debugfs receives its command as one string.  Refuse whitespace and quote
    characters rather than trying to grow a second shell quoting language
    around a board-provided path.
    """
    if pull is None:
        if pull_output or expected_sha256:
            raise ValueError("--pull-output and --pull-sha256 require --pull")
        return None
    if expected_sectors is None or expected_sectors <= 0:
        raise ValueError("--pull requires a positive --expected-sectors from the board")
    if not pull_output:
        raise ValueError("--pull requires --pull-output")
    output = str(Path(pull_output).resolve())
    if os.path.lexists(output):
        raise ValueError("--pull-output must not already exist; refuse stale debugfs output")
    safe_path = re.compile(r"/[^\s'\"\\]*$")
    if not safe_path.fullmatch(pull):
        raise ValueError("--pull must be an absolute debugfs-safe path (no whitespace or quotes)")
    if any(char.isspace() or char in "'\"\\" for char in output):
        raise ValueError("--pull-output must not contain whitespace or quotes")
    if expected_sha256 and not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        raise ValueError("--pull-sha256 must be a 64-character hexadecimal SHA-256")
    return output


def validate_pull_result(output, expected_sha256=None):
    """Require debugfs to have produced a nonempty, optionally hashed file."""
    if not os.path.isfile(output) or os.path.getsize(output) == 0:
        raise ValueError("debugfs produced no nonempty output file")
    digest = sha256_file(output)
    if expected_sha256 and digest.lower() != expected_sha256.lower():
        raise ValueError(f"pulled SHA-256 {digest} != expected {expected_sha256}")
    return digest


def pull_root_file(session, byid, remote, output, expected_sha256=None):
    """Read one rootfs file through the UMS by-id partition with debugfs."""
    partition = byid + "-part2"
    if not os.path.exists(partition):
        session.note(f"PULL FAILED: expected root partition {partition} did not appear")
        return False
    # No -w: debugfs opens the ext4 filesystem read-only.  `dump -p` writes
    # only the explicit host output file, never the UMS card.
    command = f"dump -p {shlex.quote(remote)} {shlex.quote(output)}"
    session.note(f"PULL: debugfs read-only {partition}: {remote} -> {output}")
    try:
        proc = subprocess.run(["debugfs", "-R", command, partition],
                              capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        session.note(f"PULL FAILED: debugfs could not run: {exc}")
        return False
    transcript = proc.stdout + proc.stderr
    session.log.write(transcript.encode("utf-8", "replace"))
    sys.stdout.write(transcript); sys.stdout.flush()
    if proc.returncode:
        session.note(f"PULL FAILED: debugfs exit status {proc.returncode}")
        return False
    try:
        digest = validate_pull_result(output, expected_sha256)
    except (OSError, ValueError) as exc:
        session.note(f"PULL FAILED: {exc}")
        return False
    session.note(f"PULL PASS: {os.path.getsize(output)} bytes, sha256 {digest}")
    return True


def validated_ums_byid(disks, expected_sectors):
    """Return the exact UMS by-id target only after all identity checks pass."""
    byid = f"/dev/disk/by-id/{UMS_DISK}"
    properties = subprocess.run(
        ["udevadm", "info", "--query=property", "--name", byid],
        check=True, capture_output=True, text=True, timeout=10)
    props = dict(line.split("=", 1) for line in properties.stdout.splitlines()
                 if "=" in line)
    real = os.path.realpath(byid)
    sectors = int(Path(f"/sys/class/block/{os.path.basename(real)}/size").read_text())
    validate_flash_target(disks, props, sectors, expected_sectors)
    return byid


def usb_host_verdict(usb_tree, dm_tree, usb_start=None, require_start=False):
    """Return explicit binding/enumeration failures for one coexistence phase.

    A U-Boot prompt means only that a command completed.  It is not evidence
    that the host controller was available, so parse the transcript rather
    than treating Session.cmd() success as a host success.
    """
    failures = []

    def text(output):
        return output.decode("utf-8", "replace") if output is not None else ""

    start = text(usb_start)
    tree = text(usb_tree)
    dm = text(dm_tree)
    if require_start:
        if usb_start is None:
            failures.append("usb start did not return to the U-Boot prompt")
        elif "No working controllers found" in start:
            failures.append("usb start reported no working controllers")
        elif "dwc2_usb" not in start or "usb-otg@91540000" not in start:
            failures.append("usb start did not initialize usbotg1 with dwc2_usb")
    if "Realtek USB 10/100 LAN" not in tree:
        failures.append("usb tree did not enumerate the onboard RTL8152")
    if "dwc2_usb" not in dm or "usb-otg@91540000" not in dm:
        failures.append("dm tree lacks usbotg1 bound to dwc2_usb")
    if "dwc2-udc-otg" not in dm or "usb-otg@91500000" not in dm:
        failures.append("dm tree lacks usbotg0 bound to dwc2-udc-otg")
    return failures


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
                         "it, verify every byte with direct readback, then "
                         "reset and capture the Linux boot and DSI diagnostics. "
                         "Only with explicit authorisation")
    ap.add_argument("--pull", metavar="REMOTE_ABSOLUTE_PATH",
                    help="while the exact UMS gadget is present, read one prepared "
                         "absolute rootfs path with read-only debugfs dump, then boot Linux")
    ap.add_argument("--pull-output", metavar="HOST_FILE",
                    help="host destination for --pull; debugfs writes only this host file")
    ap.add_argument("--pull-sha256", metavar="SHA256",
                    help="optional expected SHA-256 for the nonempty --pull output")
    ap.add_argument("--expected-sectors", type=int,
                    help="required with --flash or --pull: card size previously observed on the board")
    ap.add_argument("--check-usb-host", action="store_true",
                    help="record U-Boot usb start/tree and dm tree before UMS, then "
                         "usb tree and dm tree after it; records controller binding, "
                         "not packet connectivity")
    ap.add_argument("--regs", action="store_true",
                    help="dump usbotg0's DWC2 OTG/device registers with md.l "
                         "before ums and again right after Ctrl-C. GOTGCTL "
                         "bit 19 is B_SESSION_VALID (dwc2_udc_otg_regs.h:91): "
                         "whether the PHY sees VBUS from the cable. DCTL bit 1 "
                         "is soft-disconnect: whether D+ was ever pulled up")
    args = ap.parse_args()
    if args.flash and args.pull:
        ap.error("--flash and --pull are mutually exclusive")
    if args.flash:
        if not args.expected_sectors or args.expected_sectors <= 0:
            ap.error("--flash requires a positive --expected-sectors from the board")
        if not os.path.isfile(args.flash) or os.path.getsize(args.flash) == 0:
            ap.error("--flash requires an existing, nonempty image")
    try:
        args.pull_output = validate_pull_arguments(
            args.pull, args.pull_output, args.expected_sectors, args.pull_sha256)
    except ValueError as exc:
        ap.error(str(exc))

    s = Session(args.dev, args.baud, args.out)
    status = 1
    validated_byid = None
    host_failures = []
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
        if args.check_usb_host:
            s.note("USB host coexistence record before ums (binding only; no packet test)")
            host_start = s.cmd_output("usb start", timeout=60)
            host_tree = s.cmd_output("usb tree", timeout=30)
            host_dm = s.cmd_output("dm tree", timeout=30)
            host_failures += usb_host_verdict(
                host_tree, host_dm, host_start, require_start=True)
            if host_failures:
                s.note("USB HOST VERDICT before ums: FAIL: " + "; ".join(host_failures))
            else:
                s.note("USB HOST VERDICT before ums: PASS")
        else:
            s.cmd("dm tree", timeout=30)
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
            status = 0
            if args.flash or args.pull:
                try:
                    validated_byid = validated_ums_byid(new, args.expected_sectors)
                except (ValueError, OSError, subprocess.SubprocessError) as exc:
                    action = "WRITE" if args.flash else "PULL"
                    s.note(f"{action} REFUSED: {exc}; target was not accessed")
                    status = 1
                    if args.flash:
                        s.note("board remains in ums, nothing written")
                        return
            if args.pull and validated_byid:
                if not pull_root_file(s, validated_byid, args.pull, args.pull_output,
                                      args.pull_sha256):
                    status = 1
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
        else:
            s.note("no new usb disk appeared on the host")
            s.host(["lsusb"])
            status = 3

        wrote = False
        write_requested = bool(args.flash and validated_byid)
        if args.flash and not validated_byid:
            s.note("WRITE REFUSED: exact UMS target did not validate; no write")
            status = 1
        if write_requested:
            byid = validated_byid
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

            # Before boot, every image byte must still match. After boot,
            # env_save and ext4 legitimately change bytes, so verify now.
            if not verify_written_image(s, args.flash, byid):
                status = 1
                return

        # 4. Out of ums.
        s.note("sending Ctrl-C to leave ums")
        s.buf = b""
        s.port.write(CTRL_C); s.port.flush()
        left_ums = s.wait_for(PROMPT, 20)
        if not left_ums:
            s.port.write(b"\r\n"); s.port.flush()
            left_ums = s.wait_for(PROMPT, 10)
        if not left_ums:
            s.note("U-Boot prompt NOT recovered after Ctrl-C; host verdict is skipped")
            status = 1
        regs("after Ctrl-C (the driver has probed, run, and been released)")
        if args.check_usb_host and left_ums:
            s.note("USB host coexistence record after leaving ums (binding only; no packet test)")
            host_tree = s.cmd_output("usb tree", timeout=30)
            host_dm = s.cmd_output("dm tree", timeout=30)
            post_failures = usb_host_verdict(host_tree, host_dm)
            host_failures += post_failures
            if post_failures:
                s.note("USB HOST VERDICT after ums: FAIL: " + "; ".join(post_failures))
            else:
                s.note("USB HOST VERDICT after ums: PASS")
        gone_at = None
        for _ in range(20):
            if not (usb_disks() - disks_before):
                gone_at = time.time()
                break
            time.sleep(0.5)
        s.note("host: gadget disk " + ("gone after Ctrl-C" if gone_at else "STILL PRESENT 10 s after Ctrl-C") +
               " (informational teardown timing only)")

        # 5. Back to Linux. After a write, `reset` rather than `boot`, so the
        #    SPL and U-Boot that run are the ones just written to the card.
        s.send_line("reset" if wrote else "boot")
        if s.wait_for(LOGIN, 240):
            s.note("Linux login prompt reached; the board is back in Linux")
            if wrote:
                time.sleep(6); s.pump()
                s.note("post-write diagnostics; full image equality was checked before boot")
                for c in ("readlink /run/current-system",
                          "dmesg | grep -m1 hsfreqrange",
                          "dmesg | grep -c 'BTF mismatch'",
                          "uptime"):
                    s.send_line(c)
                    end = time.time() + 12
                    while time.time() < end:
                        s.pump(); time.sleep(0.05)
            if args.check_usb_host:
                if host_failures and status == 0:
                    status = 4
                    s.note("UMS VERDICT: PASS; USB HOST VERDICT: FAIL (status 4)")
                elif not host_failures and status == 0:
                    s.note("UMS VERDICT: PASS; USB HOST VERDICT: PASS")
        else:
            s.note("Linux login prompt NOT seen within 240 s -- the board may not be in Linux")
            status = 1
    finally:
        # This finally exits explicitly even on early returns. Never let an
        # unexpected exception inherit status 0 from successful enumeration.
        failure = sys.exc_info()[1]
        if failure is not None:
            status = 1
            s.note(f"session failed: {type(failure).__name__}: {failure}")
        s.note(f"ums session end, status {status}")
        s.port.close()
        s.log.close()
        sys.exit(status)


if __name__ == "__main__":
    main()
