#!/usr/bin/env python3
"""Show, set or unset one variable in the board's saved U-Boot environment.

The board has no fw_printenv/fw_setenv.  The saved environment is one plain
(non-redundant) 8 KiB record at byte 0x300000 of /dev/mmcblk1: a little-endian
CRC-32 of the data, then NAME=VALUE entries separated by NUL and ended by a
double NUL (CONFIG_ENV_SIZE 0x2000, CONFIG_ENV_OFFSET 0x300000, ENV_IS_IN_MMC).

    tools/uboot-env-edit.py show
    tools/uboot-env-edit.py set boot_life=1
    tools/uboot-env-edit.py unset boot_life

Values are never printed except for the variable being changed (the saved
environment can hold Wi-Fi credentials).  Every change keeps a copy of the old
record under --backup-dir, writes only the 8 KiB record, re-reads it with
O_DIRECT, and verifies that the rest of the first 4 MiB is byte-identical.
Run it on the host that can reach the board; the caller holds the board lock
(`flock /tmp/k230-board.lock tools/uboot-env-edit.py ...`).  Needs the board
at its normal Linux (SSH).
"""
import argparse
import hashlib
import os
import struct
import subprocess
import sys
import time
import zlib

OFFSET = 0x300000
SIZE = 0x2000
FIRST = 4 * 1024 * 1024


def ssh(args, cmd, data=None, timeout=120):
    p = subprocess.run(["ssh", "-F", args.ssh_config, args.host, cmd], input=data,
                       capture_output=True, timeout=timeout)
    if p.returncode:
        sys.exit("ssh failed (%d): %s" % (p.returncode, p.stderr.decode(errors="replace")[:300]))
    return p.stdout


def read_first(args):
    return ssh(args, "dd if=/dev/mmcblk1 bs=4096 count=1024 iflag=direct status=none", timeout=300)


def parse(region):
    if len(region) != SIZE:
        sys.exit("environment record is %d bytes, expected %d" % (len(region), SIZE))
    stored = struct.unpack("<I", region[:4])[0]
    if zlib.crc32(region[4:]) & 0xFFFFFFFF != stored:
        sys.exit("saved environment CRC is invalid; refusing to edit it")
    data = region[4:].split(b"\0\0")[0]
    items = [v for v in data.split(b"\0") if v]
    return items


def build(items):
    data = b"\0".join(items) + b"\0\0"
    if len(data) > SIZE - 4:
        sys.exit("environment would not fit in %d bytes" % (SIZE - 4))
    data += b"\0" * (SIZE - 4 - len(data))
    return struct.pack("<I", zlib.crc32(data) & 0xFFFFFFFF) + data


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--ssh-config", default=os.path.expanduser("~/tmp/k230-coordination/ssh_config.private"))
    ap.add_argument("--host", default="k230")
    ap.add_argument("--backup-dir", default=os.path.expanduser("~/tmp/k230-life-install"))
    ap.add_argument("cmd", choices=["show", "set", "unset"])
    ap.add_argument("arg", nargs="?")
    args = ap.parse_args()

    before = read_first(args)
    if len(before) != FIRST:
        sys.exit("short read of the first 4 MiB")
    region = before[OFFSET:OFFSET + SIZE]
    items = parse(region)
    names = [i.split(b"=", 1)[0].decode() for i in items]
    if args.cmd == "show":
        print("environment record valid, %d variables: %s" % (len(items), " ".join(sorted(names))))
        for i in items:
            if i.startswith(b"boot_life="):
                print(i.decode())
        return
    if not args.arg:
        sys.exit("need an argument")
    if args.cmd == "set":
        if "=" not in args.arg:
            sys.exit("set needs NAME=VALUE")
        name = args.arg.split("=", 1)[0]
        new = [i for i in items if i.split(b"=", 1)[0].decode() != name] + [args.arg.encode()]
    else:
        name = args.arg
        new = [i for i in items if i.split(b"=", 1)[0].decode() != name]
        if len(new) == len(items):
            print("%s is not set; nothing to do" % name)
            return
    newregion = build(new)
    os.makedirs(args.backup_dir, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    bak = os.path.join(args.backup_dir, "env-record-before-%s.bin" % stamp)
    with open(bak, "wb") as f:
        f.write(region)
    print("old record saved to %s (sha256 %s)" % (bak, hashlib.sha256(region).hexdigest()))
    ssh(args, "dd of=/dev/mmcblk1 bs=512 seek=%d count=%d oflag=direct conv=notrunc,fsync status=none"
        % (OFFSET // 512, SIZE // 512), data=newregion)
    after = read_first(args)
    if after[OFFSET:OFFSET + SIZE] != newregion:
        print("READBACK MISMATCH: restoring the old record", file=sys.stderr)
        ssh(args, "dd of=/dev/mmcblk1 bs=512 seek=%d count=%d oflag=direct conv=notrunc,fsync status=none"
            % (OFFSET // 512, SIZE // 512), data=region)
        sys.exit(1)
    if after[:OFFSET] != before[:OFFSET] or after[OFFSET + SIZE:] != before[OFFSET + SIZE:]:
        print("OUTSIDE-RECORD BYTES CHANGED: restoring the old record", file=sys.stderr)
        ssh(args, "dd of=/dev/mmcblk1 bs=512 seek=%d count=%d oflag=direct conv=notrunc,fsync status=none"
            % (OFFSET // 512, SIZE // 512), data=region)
        sys.exit(1)
    items2 = parse(after[OFFSET:OFFSET + SIZE])
    print("written and verified (direct readback, CRC valid, %d variables, bytes outside the record unchanged)"
          % len(items2))
    for i in items2:
        if i.split(b"=", 1)[0].decode() == name:
            print("now: " + i.decode())
    if args.cmd == "unset":
        print("%s no longer set" % name)


if __name__ == "__main__":
    main()
