#!/usr/bin/env python3
"""Push a file to the running board over the serial console.

Reflashing the card to change one device-tree byte costs a card swap, a
20-minute build and a boot. The board already mounts /boot from that same
card, so a new DTB can simply be written there and the board rebooted.

The file is gzipped and base64'd (a 71 KB DTB becomes 13 KB, about 11 s at
115200), sent in chunks as shell appends, then decoded and verified by
md5 ON THE BOARD before it replaces anything. A transfer that arrives
corrupted must not produce an unbootable card.

  tools/push-file.py --src result.dtb --dest /boot/k230-tdisplay.dtb --reboot
"""
import argparse, base64, gzip, hashlib, io, os, sys, time

try:
    import serial
except ImportError:
    sys.exit("need pyserial")

PROMPT = b"root@nixos"


def wait_prompt(port, timeout=15.0):
    end, buf = time.time() + timeout, b""
    while time.time() < end:
        buf += port.read(4096)
        if PROMPT in buf:
            return True
    return False


def send(port, line, settle=0.05):
    port.write(line.encode() + b"\r\n")
    port.flush()
    time.sleep(settle)
    return port.read(65536)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", default="/dev/ttyACM0")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--src", required=True)
    ap.add_argument("--dest", required=True)
    ap.add_argument("--chunk", type=int, default=512)
    ap.add_argument("--reboot", action="store_true")
    a = ap.parse_args()

    raw = open(a.src, "rb").read()
    want = hashlib.md5(raw).hexdigest()
    payload = base64.b64encode(gzip.compress(raw, 9)).decode()
    print(f"{a.src}: {len(raw)} bytes, md5 {want}, {len(payload)} b64 chars")

    port = serial.Serial(a.dev, a.baud, timeout=0.3)
    time.sleep(0.4)
    port.reset_input_buffer()
    port.write(b"\r\n")
    port.flush()
    if not wait_prompt(port):
        sys.exit("no shell prompt on " + a.dev)

    send(port, "rm -f /tmp/push.b64")
    n = (len(payload) + a.chunk - 1) // a.chunk
    for i in range(n):
        part = payload[i * a.chunk:(i + 1) * a.chunk]
        send(port, f"printf '%s' '{part}' >> /tmp/push.b64", 0.04)
        if i % 5 == 0 or i == n - 1:
            print(f"  chunk {i+1}/{n}", end="\r", flush=True)
    print()

    # Decode and check ON THE BOARD before touching the destination.
    out = send(port, "base64 -d /tmp/push.b64 | gzip -d > /tmp/push.bin; "
                     "md5sum /tmp/push.bin | cut -d' ' -f1", 2.0)
    got = out.decode("utf-8", "replace")
    if want not in got:
        print(got[-400:])
        sys.exit(f"md5 mismatch on the board: wanted {want}. Destination untouched.")
    print(f"md5 verified on board: {want}")

    out = send(port, f"cp /tmp/push.bin {a.dest} && sync && echo INSTALLED", 2.0)
    if b"INSTALLED" not in out:
        print(out.decode("utf-8", "replace")[-400:])
        sys.exit("copy to destination failed")
    print(f"installed -> {a.dest}")

    if a.reboot:
        print("rebooting")
        port.write(b"reboot\r\n")
        port.flush()
        time.sleep(1)
    port.close()


if __name__ == "__main__":
    main()
