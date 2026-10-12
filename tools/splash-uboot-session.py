#!/usr/bin/env python3
"""Hold the board where the stage-1 splash is the only thing on the glass.

    flock /tmp/k230-board.lock tools/splash-uboot-session.py --out T.txt hold --seconds 60
    flock /tmp/k230-board.lock tools/splash-uboot-session.py --out T.txt idle \
        --stage /var/lib/k230/coherent-boot/<system>-<suffix> --bundle <boot files> --seconds 90

`hold`: warm `reboot`, stop autoboot, sit at K230# for --seconds while the
splash U-Boot lit stays up (the camera measures it meanwhile), run each
--poke command (e.g. an `mw.l` into the splash framebuffer, to show the
panel is scanning it rather than frozen) with 10 s after each, then `reset`.

`idle`: as `hold`, but then load the staged candidate's boot files from
mmc 1:2 (checking size and CRC32 against --bundle), import its bootargs,
append `systemd.mask=` for every display client (shell, seatd, k230-drm-splash), and
`bootm`. At the serial root shell it records the handoff checks, holds for
--seconds (photographs), then `reboot`s to the ordinary profile. The mask
lives only in this boot's volatile environment.

Prints AT_UBOOT_PROMPT / AT_IDLE_PROMPT on stdout when the hold begins.
Exit status 0 when Linux is back afterwards, 1 otherwise.
"""
import argparse, importlib.util, sys, time, zlib
from pathlib import Path

spec = importlib.util.spec_from_file_location("ums", Path(__file__).with_name("ums-session.py"))
ums = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ums)

LOADS = [('bootargs.txt', '0x7000000'), ('Image', '0x200000'),
         ('k230-tdisplay.dtb', '0x8400000'), ('initrd.uimg', '0x9000000')]
# The protected backup's OpenSBI (state.json normal_files): bytes, crc32.
FW_JUMP = (270808, '99b89787')
MASK = 'systemd.mask=shell.service systemd.mask=seatd.service systemd.mask=k230-drm-splash.service'
CHECKS = r'''echo K230_IDLE_BEGIN; cat /proc/cmdline; ls /proc/device-tree/chosen/; test -e /proc/device-tree/chosen/canaan,stage1-splash && echo FLAG_PRESENT; ls /dev/fb0; ls /dev/dri; systemctl is-active shell seatd; for p in /proc/[0-9]*; do ls -l $p/fd 2>/dev/null | grep -q /dev/dri && echo "DRM_CLIENT $(cat $p/comm) ${p#/proc/}"; done; echo DRM_CLIENTS_LISTED; systemctl is-active k230-drm-splash; dmesg | grep -E "stage 1 splash|canaan_panel|canaan-panel|fbcon|reserved mem: .*framebuffer"; echo K230_IDLE_END'''


def stop_autoboot(s, hammer):
    s.port.write(b"\r\n"); s.port.flush(); time.sleep(0.3); s.pump()
    s.send_line("reboot", kill=False)
    end = time.time() + hammer
    while time.time() < end:
        s.port.write(b" \x08"); s.port.flush(); s.pump(); time.sleep(0.1)
    s.buf = b""
    s.port.write(b"\r\n"); s.port.flush()
    return s.wait_for(ums.PROMPT, 30)


def run(s, command, timeout=30):
    """One U-Boot command, then drain until the console is quiet.

    This console echoes each reply a second time; without the drain the
    duplicate prompt satisfies the next command's wait (2026-10-12: a dtb
    ext4load was cut short that way and caught by its CRC check).
    """
    out = s.cmd_output(command, timeout)
    if out is None:
        return None
    quiet = time.time() + 0.5
    while time.time() < quiet:
        if s.pump():
            quiet = time.time() + 0.5
    return s.buf


def back_in_linux(s, timeout):
    end = time.time() + timeout
    while time.time() < end:
        s.pump()
        if ums.LOGIN in s.buf or b"root@nixos" in s.buf:
            return True
    return False


def hold(s, seconds, marker):
    s.note(marker)
    print(marker, file=sys.__stderr__, flush=True)
    end = time.time() + seconds
    while time.time() < end:
        s.pump(); time.sleep(0.2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", default="/dev/ttyACM0")
    ap.add_argument("--out", required=True)
    ap.add_argument("--hammer", type=float, default=12.0)
    sub = ap.add_subparsers(dest="mode", required=True)
    h = sub.add_parser("hold"); h.add_argument("--seconds", type=float, default=60)
    h.add_argument("--poke", action="append", default=[],
                   help="U-Boot command run after the hold, followed by another 10 s hold (repeatable)")
    i = sub.add_parser("idle"); i.add_argument("--seconds", type=float, default=90)
    i.add_argument("--stage", required=True); i.add_argument("--bundle", required=True)
    args = ap.parse_args()

    s = ums.Session(args.dev, 115200, args.out)
    ok = False
    try:
        s.note(f"splash session start ({args.mode})")
        if not stop_autoboot(s, args.hammer):
            s.note("no K230# prompt")
            ok = back_in_linux(s, 120)
            return
        run(s, "version")
        if args.mode == "hold":
            hold(s, args.seconds, "AT_UBOOT_PROMPT")
            for command in args.poke:
                run(s, command, 60)
                hold(s, 10, "POKED")
            run(s, "echo UBOOT_PROMPT_STILL_ALIVE")
            s.send_line("reset")
            ok = back_in_linux(s, 240)
            return
        for name, address in LOADS:
            data = (Path(args.bundle) / name).read_bytes()
            out = run(s, f"ext4load mmc 1:2 {address} {args.stage}/{name}", 90)
            crc = run(s, f"crc32 {address} {len(data):#x}", 40)
            want = f"{zlib.crc32(data):08x}".encode()
            if not out or f"{len(data)} bytes read".encode() not in out or not crc or want not in crc:
                s.note(f"LOAD CHECK FAILED for {name}; resetting")
                s.send_line("reset"); ok = back_in_linux(s, 240); return
        # fw_jump comes from the protected backup, as the boot tool loads it.
        out = run(s, f"ext4load mmc 1:2 0x8000000 {args.stage}/backup/fw_jump_add_uboot_head.bin", 90)
        crc = run(s, f"crc32 0x8000000 {FW_JUMP[0]:#x}", 40)
        if not out or f"{FW_JUMP[0]} bytes read".encode() not in out or not crc or FW_JUMP[1].encode() not in crc:
            s.note("LOAD CHECK FAILED for fw_jump; resetting")
            s.send_line("reset"); ok = back_in_linux(s, 240); return
        size = (Path(args.bundle) / 'bootargs.txt').stat().st_size
        if not run(s, f"env import -t 0x7000000 {size:#x}"):
            s.send_line("reset"); ok = back_in_linux(s, 240); return
        run(s, "printenv bootargs")
        run(s, f'setenv bootargs "${{bootargs}} {MASK}"')
        run(s, "printenv bootargs")
        s.send_line("bootm 0x8000000 0x9000000 0x8400000")
        if not s.wait_for(b"root@nixos", 240):
            s.note("no root shell after idle boot")
            ok = back_in_linux(s, 60)
            return
        time.sleep(3); s.pump()
        s.send_line(CHECKS, kill=False)
        s.wait_for(b"\nK230_IDLE_END", 60)
        hold(s, args.seconds, "AT_IDLE_PROMPT")
        s.send_line(CHECKS, kill=False)
        s.wait_for(b"\nK230_IDLE_END", 60)
        s.send_line("reboot", kill=False)
        # The old shell prompt is still in flight; wait for U-Boot first.
        s.wait_for(b"U-Boot SPL", 120)
        s.buf = b""
        ok = back_in_linux(s, 300)
    finally:
        s.note(f"session end, {'Linux back' if ok else 'LINUX NOT CONFIRMED'}")
        s.port.close()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
