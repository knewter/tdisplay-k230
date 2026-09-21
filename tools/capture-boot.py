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

A fourth reason, found much later and much more expensively: the burst of
garbage every open begins with is made on the *host*, not the board. See
docs/evidence/ch342-open-garbage.md. In short, ModemManager probes the CH342
on every enumeration -- it holds the port with TIOCEXCL for ~18s, drops the
UART to its own default of 57600 while the K230 talks at 115200, and writes
"AT" at that wrong rate straight into U-Boot's line editor. Hence mis-framed
bytes on our side, and `Unknown command 'kKBBBBkBBBkrun'` on the board's.

The real fix is the udev rule next door:

  sudo install -m0644 tools/99-tdisplay-k230-no-modemmanager.rules /etc/udev/rules.d/
  sudo udevadm control --reload   # then replug the console cable

That cannot be the whole answer, because cdc_acm also programs 9600 into
every CDC device at probe time and leaves it there until the first open. So
this script additionally settles, flushes, and *records what it discarded*
under a marker -- so nobody reads a host artefact as a board crash again.

  tools/capture-boot.py --out docs/evidence/hardware-boot.txt --seconds 180
  tools/capture-boot.py --send 'cat /proc/cpuinfo' --expect '# '
"""
import argparse, os, subprocess, sys, time

try:
    import serial
except ImportError:
    sys.exit("need pyserial: nix shell nixpkgs#python3Packages.pyserial")

# Kill-line. U-Boot's cread_line treats CTL_CH('u') as "erase the line", and a
# tty in canonical mode treats it as VKILL. Sending it before a command drops
# whatever junk is already in the target's line editor instead of letting it
# become a prefix on ours.
KILL_LINE = b"\x15"


def modemmanager_warning(dev):
    """Return a warning if ModemManager will fight us for `dev`, else None.

    Reads systemd state and udev properties only. Never opens the port.
    """
    try:
        if subprocess.run(["systemctl", "is-active", "--quiet", "ModemManager"],
                          timeout=5).returncode != 0:
            return None
    except Exception:
        return None                  # no systemd, or no ModemManager: fine
    try:
        out = subprocess.run(["udevadm", "info", "--query=property", "--name", dev],
                             capture_output=True, text=True, timeout=5).stdout
    except Exception:
        return None
    if "ID_VENDOR_ID=" not in out:
        return None                  # not a USB device: a pty, a real UART
    if "ID_MM_DEVICE_IGNORE=1" in out or "ID_MM_PORT_IGNORE=1" in out:
        return None
    return (f"ModemManager is running and {dev} is not tagged "
            "ID_MM_DEVICE_IGNORE. It will hold the port with TIOCEXCL for "
            "~18s per enumeration and write AT at 57600 into the board. Fix: "
            "sudo install -m0644 tools/99-tdisplay-k230-no-modemmanager.rules "
            "/etc/udev/rules.d/ && sudo udevadm control --reload, then replug")


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
    ap.add_argument("--settle", type=float, default=0.30,
                    help="after opening, read and DISCARD for this long before "
                         "doing anything else. The CH342 sits at the wrong baud "
                         "from enumeration until our tcsetattr lands, so its "
                         "FIFO drains mis-framed bytes first; pyserial's own "
                         "flush during open() fires too early to catch them. "
                         "Discarded bytes are logged under a marker, not thrown "
                         "away. With the udev rule installed 0.05 is enough; "
                         "0 disables")
    ap.add_argument("--no-line-kill", dest="line_kill", action="store_false",
                    help="do not prefix each --send with Ctrl-U. By default we "
                         "do, so junk already in the target's line editor is "
                         "erased instead of prefixed onto our command")
    ap.add_argument("--no-exclusive", dest="exclusive", action="store_false",
                    help="do not take an advisory flock on the port. By default "
                         "we do, so a second copy of this script (or tio) "
                         "cannot silently steal half our bytes. This is flock, "
                         "not TIOCEXCL: it keeps our own tooling out, not "
                         "ModemManager")
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

    warning = modemmanager_warning(args.dev)
    if warning:
        emit(f"--- WARNING: {warning} ---")

    emit(f"--- capture start, waiting for {args.dev} ---")
    line = b""
    tail = b""
    last_output = time.time()
    last_busy_report = 0.0

    def write_cmd(port, cmd):
        """Send one command, erasing whatever junk precedes it."""
        if args.line_kill:
            port.write(KILL_LINE)
            port.flush()
            time.sleep(0.05)
        port.write(cmd.encode() + b"\r\n")
        port.flush()

    while time.time() < deadline:
        if not os.path.exists(args.dev):
            time.sleep(0.2)
            continue
        try:
            port = serial.Serial(args.dev, args.baud, timeout=0.2,
                                 exclusive=True if args.exclusive else None)
        except Exception as exc:
            # Not "udev has not finished with it yet", as this used to claim.
            # Usually ModemManager holding TIOCEXCL, or another reader's flock.
            if time.time() - last_busy_report > 5.0:
                last_busy_report = time.time()
                emit(f"--- {args.dev} not openable "
                     f"({exc.__class__.__name__}: {exc}), retrying ---")
            time.sleep(0.2)
            continue
        emit("--- port opened ---")

        # Settle, then flush. Everything read here came out of the chip's FIFO
        # from the wrong-baud window before our tcsetattr landed. Log it under
        # a marker so it is on the record but can never be mistaken for the
        # board's own output, and so no --expect can ever match inside it.
        if args.settle > 0:
            junk = b""
            end = time.time() + args.settle
            while time.time() < end:
                try:
                    junk += port.read(4096)
                except Exception:
                    break
                time.sleep(0.02)
            try:
                port.reset_input_buffer()
                port.reset_output_buffer()
            except Exception:
                pass
            if junk:
                emit(f"--- discarded {len(junk)} bytes from the {args.settle}s "
                     f"settle window (host-side wrong-baud artefact, NOT board "
                     f"output): {junk!r} ---")
            else:
                emit("--- settle window clean, nothing discarded ---")
            tail = b""      # a prompt may only be matched in post-flush data

        if args.hammer:
            emit(f"--- hammering keys for {args.hammer}s to stop autoboot ---")
            end = time.time() + args.hammer
            # The whole loop is guarded. The port disappears mid-hammer on
            # every power cycle -- which is exactly when hammering matters --
            # and an unguarded read() there raises SerialException straight
            # out of the program, killing the capture at the worst moment.
            while time.time() < end:
                try:
                    port.write(b" \x08")   # space then backspace: harmless at a prompt
                    port.flush()
                    chunk = port.read(512)
                except Exception:
                    emit("--- port lost while hammering, reopening ---")
                    break
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
                        write_cmd(port, cmd)
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
