#!/usr/bin/env python3
"""One-shot boot of the CPU0 remoteproc kernel, then start CPU0 from Linux.

    flock /tmp/k230-board.lock tools/cpu0-linux-start-session.py --out T.txt \
        --stage /var/lib/k230/coherent-boot/<system>-<suffix> --bundle <boot files> \
        --trial /var/lib/k230/cpu0-trial --image <kernel>/Image --dtb <cpu0 dtb> \
        --module <k230_cpu0_rproc.ko.xz> [--hold 60]

openspec/changes/the-small-core-runs-as-a-coprocessor task 5.1. The trial
directory must already hold Image, k230-tdisplay-mainline-drm-hotplug-cpu0.dtb
and k230_cpu0_rproc.ko.xz (copied over SSH); /boot/small-core-echo.bin is the
echo payload from task 3.

Warm `reboot`, stop autoboot, load the installed candidate's bootargs and
initrd and the protected backup's OpenSBI from --stage, but the trial Image
and DTB from --trial (each checked by size and CRC32 against the local
files), and `bootm`. Nothing on the card's boot path changes: the next
ordinary boot is the installed default. Nothing is masked; the shell
compositor runs.

In Linux it waits for the shell service, records the pre-start state, runs
a pre-start echo request as a negative control (CPU0 is not serving, so it
must not be answered), loads the module, starts CPU0 through the standard
remoteproc `state` file, sends echo requests through the driver's cpu0_echo
attribute, and records the compositor's IPC answer, a grim capture's hash
and the kernel log around the start. It holds --hold seconds (for an SSH
pull of the capture), then `reboot`s to the installed default.

Exit status 0 when Linux is back afterwards, 1 otherwise. The verdict lives
in the transcript (look for ECHO_RESULT lines and K230_CPU0_* markers).
"""
import argparse, importlib.util, re, sys, time, zlib
from pathlib import Path

spec = importlib.util.spec_from_file_location("ums", Path(__file__).with_name("ums-session.py"))
ums = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ums)

spec = importlib.util.spec_from_file_location("splash", Path(__file__).with_name("splash-uboot-session.py"))
splash = importlib.util.module_from_spec(spec)
spec.loader.exec_module(splash)
run, stop_autoboot, back_in_linux, hold = splash.run, splash.stop_autoboot, splash.back_in_linux, splash.hold

DTB_NAME = "k230-tdisplay-mainline-drm-hotplug-cpu0.dtb"
SWAY = "runuser -u shell -- env SWAYSOCK=/run/shell/sway-ipc.sock WAYLAND_DISPLAY=wayland-1 XDG_RUNTIME_DIR=/run/shell"
VALUES = ["0x00000000", "0x12345678", "0xfffffffe", "0xffffffff", "0xdeadbeef",
          "0x00000001", "0x80000000", "0x7fffffff"]

PRE = r'''echo K230_CPU0_PRE_BEGIN; uname -a; cat /proc/cmdline; systemctl is-system-running; systemctl is-active shell seatd; dmesg | grep -iE "cpu0|remoteproc|reserved mem"; ls /sys/class/remoteproc/; sha256sum /boot/small-core-echo.bin TRIAL/k230_cpu0_rproc.ko.xz; SWAY swaymsg -t get_version | head -3; echo K230_CPU0_PRE_END'''

LOAD = r'''echo K230_CPU0_LOAD_BEGIN; insmod TRIAL/k230_cpu0_rproc.ko.xz; echo insmod_rc=$?; D=$(ls -d /sys/bus/platform/drivers/k230-cpu0-rproc/*.remoteproc); R=$(ls -d $D/remoteproc/remoteproc*); echo D=$D R=$R; cat $R/name $R/state $R/firmware; cat $D/cpu0_status; echo 0x5a5a5a5a > $D/cpu0_echo; echo prestart_echo_rc=$?; echo "ECHO_RESULT prestart $(cat $D/cpu0_echo)"; dmesg | grep -iE "k230-cpu0|remoteproc" | tail -5; echo K230_CPU0_LOAD_END'''

START = r'''echo K230_CPU0_START_BEGIN; D=$(ls -d /sys/bus/platform/drivers/k230-cpu0-rproc/*.remoteproc); R=$(ls -d $D/remoteproc/remoteproc*); echo -n /boot > /sys/module/firmware_class/parameters/path; echo small-core-echo.bin > $R/firmware; cat $R/firmware; date +%s.%N; echo start > $R/state; echo start_rc=$?; cat $R/state; cat $D/cpu0_status; for v in VALUES; do echo $v > $D/cpu0_echo; echo "ECHO_RESULT rc=$? $(cat $D/cpu0_echo)"; done; i=0; ok=0; while [ $i -lt 1000 ]; do echo $i > $D/cpu0_echo && ok=$((ok+1)); i=$((i+1)); done; echo "ECHO_BULK ok=$ok of 1000 last: $(cat $D/cpu0_echo)"; cat $D/cpu0_status; dmesg | grep -iE "k230-cpu0|remoteproc|firmware" | tail -10; echo K230_CPU0_START_END'''

POST = r'''echo K230_CPU0_POST_BEGIN; D=$(ls -d /sys/bus/platform/drivers/k230-cpu0-rproc/*.remoteproc); R=$(ls -d $D/remoteproc/remoteproc*); cat $R/state; systemctl is-system-running; systemctl is-active shell seatd; SWAY swaymsg -t get_version | head -3; SWAY grim /run/shell/cpu0-start.png; echo grim_rc=$?; sha256sum /run/shell/cpu0-start.png; echo 0xa5a5a5a5 > $D/cpu0_echo; echo "ECHO_RESULT post $(cat $D/cpu0_echo)"; cat $D/cpu0_status; uptime; dmesg --level=err,warn | tail -15; echo K230_CPU0_POST_END'''


def check_load(s, local, address, remote):
    data = Path(local).read_bytes()
    out = run(s, f"ext4load mmc 1:2 {address} {remote}", 90)
    crc = run(s, f"crc32 {address} {len(data):#x}", 40)
    want = f"{zlib.crc32(data):08x}".encode()
    ok = bool(out) and f"{len(data)} bytes read".encode() in out and bool(crc) and want in crc
    if not ok:
        s.note(f"LOAD CHECK FAILED for {remote}")
    return ok


def linux_block(s, text, end, timeout):
    s.send_line(text, kill=False)
    return s.wait_for(b"\n" + end, timeout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", default="/dev/ttyACM0")
    ap.add_argument("--out", required=True)
    ap.add_argument("--hammer", type=float, default=12.0)
    ap.add_argument("--stage", required=True)
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--trial", default="/var/lib/k230/cpu0-trial")
    ap.add_argument("--image", required=True)
    ap.add_argument("--dtb", required=True)
    ap.add_argument("--hold", type=float, default=60)
    args = ap.parse_args()

    sub = lambda t: (t.replace("TRIAL", args.trial).replace("SWAY", SWAY)
                     .replace("VALUES", " ".join(VALUES)))
    s = ums.Session(args.dev, 115200, args.out)
    ok = False
    try:
        s.note("cpu0 linux-start session start")
        if not stop_autoboot(s, args.hammer):
            s.note("no K230# prompt")
            ok = back_in_linux(s, 120)
            return
        run(s, "version")
        bundle = Path(args.bundle)
        loads = [(bundle / "bootargs.txt", "0x7000000", f"{args.stage}/bootargs.txt"),
                 (Path(args.image), "0x200000", f"{args.trial}/Image"),
                 (Path(args.dtb), "0x8400000", f"{args.trial}/{DTB_NAME}"),
                 (bundle / "initrd.uimg", "0x9000000", f"{args.stage}/initrd.uimg")]
        for local, address, remote in loads:
            if not check_load(s, local, address, remote):
                s.send_line("reset"); ok = back_in_linux(s, 240); return
        out = run(s, f"ext4load mmc 1:2 0x8000000 {args.stage}/backup/fw_jump_add_uboot_head.bin", 90)
        crc = run(s, f"crc32 0x8000000 {splash.FW_JUMP[0]:#x}", 40)
        if not out or f"{splash.FW_JUMP[0]} bytes read".encode() not in out or not crc \
                or splash.FW_JUMP[1].encode() not in crc:
            s.note("LOAD CHECK FAILED for fw_jump; resetting")
            s.send_line("reset"); ok = back_in_linux(s, 240); return
        size = (bundle / "bootargs.txt").stat().st_size
        if not run(s, f"env import -t 0x7000000 {size:#x}"):
            s.send_line("reset"); ok = back_in_linux(s, 240); return
        run(s, "printenv bootargs")
        s.send_line("bootm 0x8000000 0x9000000 0x8400000")
        if not s.wait_for(b"root@nixos", 300):
            s.note("no root shell after trial boot")
            ok = back_in_linux(s, 60)
            return
        # Let the shell compositor come up before measuring anything.
        end = time.time() + 120
        while time.time() < end:
            s.buf = b""
            s.send_line("systemctl is-active shell; echo SHELL_POLL_DONE", kill=False)
            s.wait_for(b"\nSHELL_POLL_DONE", 20)
            # bash's bracketed-paste reset puts "\x1b[?2004l\r" before the
            # answer, so match on the line ending, not a leading newline.
            if re.search(rb"[\r\n]active\r?\nSHELL_POLL_DONE", s.buf):
                break
            time.sleep(5)
        time.sleep(10); s.pump()
        linux_block(s, sub(PRE), b"K230_CPU0_PRE_END", 60)
        linux_block(s, sub(LOAD), b"K230_CPU0_LOAD_END", 60)
        linux_block(s, sub(START), b"K230_CPU0_START_END", 600)
        linux_block(s, sub(POST), b"K230_CPU0_POST_END", 120)
        hold(s, args.hold, "AT_CPU0_HOLD")
        linux_block(s, sub(POST), b"K230_CPU0_POST_END", 120)
        s.send_line("reboot", kill=False)
        s.wait_for(b"U-Boot SPL", 120)
        s.buf = b""
        ok = back_in_linux(s, 300)
    finally:
        s.note(f"session end, {'Linux back' if ok else 'LINUX NOT CONFIRMED'}")
        s.port.close()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
