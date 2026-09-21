#!/usr/bin/env python3
"""Capture a whole boot off the CH342 console, across USB re-enumeration.

Three earlier attempts at this by hand each produced a few hundred bytes and
missed the reason the boot failed, for three different reasons:

  - the port vanishes when the board resets, so a single open() ends at the
    moment the interesting part starts;
  - a script that only sends `reset` when it sees `K230#` does nothing at all
    when the board is already sitting in emergency mode, and then records the
    stale tail of the previous boot as if it were a new one;
  - without timestamps there is no way to tell a hang from a quiet period.

So: reopen forever until the deadline, stamp every line, flush every write,
and never require a prompt to be present.

  tools/capture-boot.py --out docs/evidence/hardware-boot.txt --seconds 180
  tools/capture-boot.py --send 'cat /proc/cpuinfo' --expect '# '
"""
import argparse, os, sys, time

try:
    import serial
except ImportError:
    sys.exit("need pyserial: nix shell nixpkgs#python3Packages.pyserial")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", default="/dev/ttyACM0")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seconds", type=float, default=180.0)
    ap.add_argument("--append", action="store_true")
    ap.add_argument("--send", action="append", default=[],
                    help="send this line once --expect is seen (repeatable)")
    ap.add_argument("--expect", default=None,
                    help="prompt substring that arms --send")
    ap.add_argument("--kick", action="store_true",
                    help="send a newline after opening, to elicit a prompt "
                         "from an idle shell. Do NOT use for a boot capture: "
                         "it would interrupt U-Boot's autoboot countdown")
    ap.add_argument("--hammer", type=float, default=0.0,
                    help="after opening, send a key every 100ms for this "
                         "many seconds. A single --kick is not enough to stop "
                         "U-Boot autoboot: the port opens before the countdown "
                         "starts, so the keypress is consumed too early and the "
                         "board boots anyway. Hammering covers the window.")
    ap.add_argument("--quiet-exit", type=float, default=0.0,
                    help="stop early after this many seconds with no output")
    args = ap.parse_args()

    deadline = time.time() + args.seconds
    pending = list(args.send)
    log = open(args.out, "ab" if args.append else "wb", buffering=0)
    started = time.time()

    def emit(text):
        stamp = f"[{time.time() - started:8.3f}] ".encode()
        log.write(stamp + text.encode() + b"\n")
        sys.stdout.write(stamp.decode() + text + "\n")
        sys.stdout.flush()

    emit(f"--- capture start, waiting for {args.dev} ---")
    line = b""
    tail = b""
    last_output = time.time()

    while time.time() < deadline:
        if not os.path.exists(args.dev):
            time.sleep(0.2)
            continue
        try:
            port = serial.Serial(args.dev, args.baud, timeout=0.2)
        except Exception:
            time.sleep(0.2)          # udev has not finished with it yet
            continue
        emit("--- port opened ---")
        if args.hammer:
            emit(f"--- hammering keys for {args.hammer}s to stop autoboot ---")
            end = time.time() + args.hammer
            while time.time() < end:
                try:
                    port.write(b" \x08")     # space then backspace: harmless at a prompt
                    port.flush()
                except Exception:
                    break
                chunk = port.read(512)
                if chunk:
                    log.write(chunk)
                    sys.stdout.write(chunk.decode("utf-8", "replace"))
                    sys.stdout.flush()
                time.sleep(0.1)
        if args.kick:
            # An idle shell emits nothing, so an --expect that is only checked
            # on arriving data never matches and no --send ever fires.
            try:
                port.write(b"\r\n")
                port.flush()
            except Exception:
                pass
        try:
            while time.time() < deadline:
                chunk = port.read(4096)
                if not chunk:
                    if args.quiet_exit and time.time() - last_output > args.quiet_exit:
                        emit("--- quiet, stopping ---")
                        return
                    continue
                last_output = time.time()
                log.write(chunk)
                sys.stdout.write(chunk.decode("utf-8", "replace"))
                sys.stdout.flush()

                # arm --send on the prompt, looking across chunk boundaries
                if pending and args.expect:
                    tail = (tail + chunk)[-256:]
                    if args.expect.encode() in tail:
                        cmd = pending.pop(0)
                        emit(f"--- sending: {cmd} ---")
                        port.write(cmd.encode() + b"\r\n")
                        port.flush()
                        tail = b""
        except Exception as exc:
            emit(f"--- port lost ({exc.__class__.__name__}), reopening ---")
        finally:
            try:
                port.close()
            except Exception:
                pass
    emit("--- capture end ---")


if __name__ == "__main__":
    main()
