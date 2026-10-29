#!/usr/bin/env python3
"""Exhibition: the clock the handheld shows while idle on its charger.

Opened by `k230-idle-dimmer dim` (nix/idle-dimmer/idle_dimmer.py) in a Foot
card, on black, at the dimmed backlight. It shows the time and date, moves
them a little every minute against burn-in, and about every five minutes (Settings: 5 min, 15 min or Off) plays
one `ttfx` text effect over the committed K230 banner. Any touch or key closes
it. When the notification broker holds events a small dot and their number
sit under the date (read once per minute redraw; nothing when there are none
or the broker does not answer). `--on-close` runs when input or lost focus
ends the card, for a card the idle timer did not start. It also closes, after asking the idle step to blank the display, when the
charger goes away or after two hours (Settings: 2 h, 8 h or None).

CPU is the budget: the board has one online CPU and Foot repaints in software.
So the clock changes once a minute (no seconds), the card sleeps in select()
between events (at most POLL_SECONDS), effects run at EFFECT_FRAME_RATE for at
most EFFECT_MAX_SECONDS from a fixed list of finite effects, and nothing is
drawn while the display is off.

    k230_exhibition.py --ttfx PATH --banner PATH [--pid-file PATH] [--on-end CMD]
                       [--on-close CMD] [--notification-socket PATH]
    k230_exhibition.py --render-once WIDTHxHEIGHT      (debug: one frame)
"""
import argparse
import math
import os
import json
import select
import shlex
import socket
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import k230_term_apps as apps  # noqa: E402  (sibling module in the same lib dir)

POLL_SECONDS = 10
FIRST_EFFECT_DELAY = 8
EFFECT_INTERVAL = 300
PREFS_DIR = "/var/lib/k230-shell-prefs"
CLOCK_EFFECTS_FILE = "clock-effects"
CLOCK_LIMIT_FILE = "clock-limit"
EFFECT_MAX_SECONDS = 20
BANNER_HOLD_SECONDS = 4
EFFECT_FRAME_RATE = 15
MAX_UP_SECONDS = 2 * 3600
RELEASE_WAIT_SECONDS = 0.25
# Finite effects only, each measured on the host to end within the cap at the
# frame rate above (docs/evidence/clock-display/host/README.md). decrypt and
# spotlights run past 40 s at 15 fps and are left out.
EFFECTS = ("slice", "expand", "slide", "middleout", "scattered", "wipe",
           "highlight", "sweep", "beams")

CLOCK_SGR = "\x1b[2;94m"
DATE_SGR = "\x1b[2m"
DOT_SGR = "\x1b[2;93m"
DOT = "\u25cf"
NOTIFICATION_TIMEOUT = 0.5
DRIFT_COLS = 6
DRIFT_ROWS = 2

POWER_SUPPLY_ROOT = "/sys/class/power_supply"
DRM_ROOT = "/sys/class/drm"


# ---------------------------------------------------------------------------
# Pure decisions

def _read_pref(prefs_dir, name, words, default):
    """The seconds for the word in prefs file `name`; a missing, unreadable
    or unrecognised file means `default`. None means the feature is off.
    The Settings rows (shell_prefs.rs) write the same words."""
    try:
        text = (Path(prefs_dir) / name).read_text().strip()
    except (OSError, ValueError):
        return default
    return words.get(text, default)


def read_effect_interval(prefs_dir=PREFS_DIR):
    """Seconds between effects, or None for "Clock effects" Off. Default 5 min."""
    return _read_pref(prefs_dir, CLOCK_EFFECTS_FILE,
                      {"5m": 300, "15m": 900, "off": None}, EFFECT_INTERVAL)


def read_max_up(prefs_dir=PREFS_DIR):
    """Seconds before the card closes itself, or None for "Clock limit" None.
    Default 2 h."""
    return _read_pref(prefs_dir, CLOCK_LIMIT_FILE,
                      {"2h": 2 * 3600, "8h": 8 * 3600, "none": None}, MAX_UP_SECONDS)


def effect_for(index):
    """The effect for the `index`th play, in a fixed rotation."""
    return EFFECTS[index % len(EFFECTS)]


def next_effect_at(started_at, last_effect_at, interval=EFFECT_INTERVAL):
    if last_effect_at is None:
        return started_at + FIRST_EFFECT_DELAY
    return last_effect_at + interval


def drift(minute_index, max_dx=DRIFT_COLS, max_dy=DRIFT_ROWS):
    """(dx, dy) for a minute: a stride walk over every offset in the range."""
    width, height = 2 * max_dx + 1, 2 * max_dy + 1
    count = width * height
    stride = max(1, round(count * 0.43))
    while math.gcd(stride, count) != 1:
        stride += 1
    k = (minute_index * stride) % count
    return k % width - max_dx, k // width - max_dy


def notification_count(path, timeout=NOTIFICATION_TIMEOUT):
    """The number of events the broker retains (the same `history` count Home
    and the shade show), or 0 when the path is unset or anything goes wrong:
    a missing socket, a slow or malformed reply, a bad count."""
    if not path:
        return 0
    try:
        with socket.socket(socket.AF_UNIX) as connection:
            connection.settimeout(timeout)
            connection.connect(str(path))
            connection.sendall(b'{"operation":"history"}\n')
            reply = b""
            while b"\n" not in reply:
                chunk = connection.recv(8192)
                if not chunk or len(reply) + len(chunk) > 256 * 1024:
                    return 0
                reply += chunk
        count = json.loads(reply)["count"]
    except (OSError, ValueError, KeyError, TypeError):
        return 0
    return count if type(count) is int and count > 0 else 0


def count_text(count):
    return f"{DOT} {count}" if count < 100 else f"{DOT} 99+"


def clock_layout(cols, rows, tm, minute_index, count=0, twelve=False):
    """The frame for one minute: big HH:MM, a rule-free gap, the date, all
    shifted by that minute's drift but kept entirely inside the frame. With
    `count` waiting notifications a dot and the number sit two rows under the
    date, centred on it."""
    frame = apps.Frame(cols, rows)
    text = apps.clock_digits(tm, twelve)
    date = apps.clock_date_line(tm, twelve)
    sx, sy = apps.pick_scale(text, cols, rows, reserve_rows=9, width_fraction=0.6)
    big_h = apps.GLYPH_ROWS * sy
    big_w = apps.text_units(text) * sx
    badge = count_text(count) if count > 0 else ""
    block_h = big_h + 2 + (2 if badge else 0)
    block_w = max(big_w, len(date))
    max_dx = max(0, min(DRIFT_COLS, (cols - block_w) // 2))
    max_dy = max(0, min(DRIFT_ROWS, (rows - block_h) // 2))
    # The stride walk over the room this window really has.
    dx, dy = drift(minute_index, max_dx, max_dy)
    top = 1 + apps.centre(block_h, rows) + dy
    left = 1 + apps.centre(block_w, cols) + dx
    frame.put_big(top, text, sx, sy, CLOCK_SGR, col=left + apps.centre(big_w, block_w))
    frame.put(top + big_h + 1, left + apps.centre(len(date), block_w), date, DATE_SGR)
    if badge:
        frame.put(top + big_h + 3, left + apps.centre(len(badge), block_w), badge, DOT_SGR)
    return frame


def charger_online(root=POWER_SUPPLY_ROOT):
    """True when any supply that is not the Battery reports online 1."""
    try:
        entries = sorted(Path(root).iterdir())
    except OSError:
        return False
    for entry in entries:
        try:
            kind = (entry / "type").read_text().strip()
            online = (entry / "online").read_text().strip()
        except OSError:
            continue
        if kind != "Battery" and online == "1":
            return True
    return False


def display_on(root=DRM_ROOT):
    """False only when a connected DRM connector reports dpms Off. Anything
    unreadable counts as on, so the card keeps drawing rather than freezing."""
    try:
        entries = sorted(Path(root).iterdir())
    except OSError:
        return True
    seen = False
    for entry in entries:
        try:
            if (entry / "status").read_text().strip() != "connected":
                continue
            dpms = (entry / "dpms").read_text().strip()
        except OSError:
            continue
        seen = True
        if dpms.lower() == "on":
            return True
    return not seen


def needs_release(data):
    """True when `data` holds an SGR mouse press with no release after it,
    i.e. a touch is still down and its lift should be read before leaving.
    Motion reports (button bit 32, from mode 1003) are not presses."""
    pressed = False
    i = 0
    while True:
        start = data.find(b"\x1b[<", i)
        if start < 0:
            return pressed
        end = start + 3
        while end < len(data) and not 0x40 <= data[end] <= 0x7E:
            end += 1
        if end >= len(data):
            return pressed
        final = chr(data[end])
        button = data[start + 3:end].split(b";")[0]
        motion = button.isdigit() and int(button) & 32
        if final == "M" and not motion:
            pressed = True
        elif final == "m":
            pressed = False
        i = end + 1


FOCUS_IN = b"\x1b[I"
FOCUS_OUT = b"\x1b[O"


def split_focus(data):
    """Take the terminal's focus reports (mode 1004) out of `data`.
    Returns the remaining bytes and whether focus was lost. Focus-in is not
    input: the card gets it when it maps."""
    lost = FOCUS_OUT in data
    return data.replace(FOCUS_IN, b"").replace(FOCUS_OUT, b""), lost


def ttfx_command(ttfx, banner, effect, rows):
    """Centre the banner on a full-width canvas one row short of the
    terminal, as Omarchy's screensaver does, so the last line cannot scroll;
    leave the cursor hidden when the effect ends."""
    return [ttfx, "-i", banner, "--frame-rate", str(EFFECT_FRAME_RATE),
            "--canvas-width", "0", "--canvas-height", str(max(1, rows - 1)),
            "--anchor-canvas", "c", "--anchor-text", "c",
            "--no-eol", "--no-restore-cursor", effect]


# ---------------------------------------------------------------------------
# Terminal side

class ExhibitSession(apps.Session):
    """The Session with every input byte reported, releases included."""

    def __init__(self):
        super().__init__(mouse=True)

    def __enter__(self):
        super().__enter__()
        # Black default background whatever the theme says (AMOLED); undone
        # in __exit__ with OSC 111. Focus reports let the card end when
        # something else takes focus without input reaching it (a card
        # focused over IPC), instead of lingering behind it. Any-motion
        # reports (1003) let a mouse that only moves close it too.
        self._write("\x1b]11;#000000\x1b\\\x1b[?1004h\x1b[?1003h")
        return self

    def __exit__(self, *exc):
        self._write("\x1b[?1003l\x1b[?1004l\x1b]111\x1b\\")
        return super().__exit__(*exc)

    def wait(self, timeout):
        if self.quit:
            return [("quit",)]
        try:
            ready, _, _ = select.select([self.fd, self.wake_r], [], [], timeout)
        except InterruptedError:
            ready = []
        events = []
        if self.wake_r in ready:
            try:
                os.read(self.wake_r, 64)
            except BlockingIOError:
                pass
        if self.quit:
            return [("quit",)]
        if self.resized:
            self.resized = False
            events.append(("resize",))
        if self.fd in ready:
            data = os.read(self.fd, 4096)
            if not data:
                return [("quit",)]
            data, lost = split_focus(data)
            if lost:
                return [("quit",)]
            if data:
                events.append(("input", data))
        if not ready and not events:
            events.append(("timeout",))
        return events

    def read_release(self, first):
        """Keep the touch inside the card: read until its lift or a short
        deadline."""
        data = first
        deadline = time.monotonic() + RELEASE_WAIT_SECONDS
        while needs_release(data):
            left = deadline - time.monotonic()
            if left <= 0:
                return
            ready, _, _ = select.select([self.fd], [], [], left)
            if not ready:
                return
            chunk = os.read(self.fd, 4096)
            if not chunk:
                return
            data += chunk


class Exhibition:
    """The loop, with the clock, the machine's state and ttfx injectable."""

    def __init__(self, sess, cfg, clock=time.time, charger=charger_online,
                 display=display_on, play=None, end=None, localtime=time.localtime,
                 count=notification_count):
        self.sess = sess
        self.cfg = cfg
        self.clock = clock
        self.charger = charger
        self.display = display
        self.play = play or self.play_ttfx
        self.end = end or self.run_on_end
        self.localtime = localtime
        self.count = count
        self.started = clock()
        self.last_effect = None
        self.effects_played = 0
        self.drawn_minute = None
        self.next_poll = self.started + POLL_SECONDS
        self.max_up = cfg.get("max_up", MAX_UP_SECONDS)
        self.interval = cfg.get("interval", EFFECT_INTERVAL)

    # -- drawing --------------------------------------------------------
    def draw(self, now):
        cols, rows = self.sess.size()
        minute = int(now // 60)
        count = self.count(self.cfg.get("notification_socket"))
        # Read each minute, so a Settings change shows at the next redraw.
        twelve = apps.read_twelve_hour(self.cfg.get("prefs_dir", PREFS_DIR))
        self.sess.draw(clock_layout(cols, rows, self.localtime(now), minute, count, twelve))
        self.sess._write("\x1b[?25l")
        self.drawn_minute = minute

    # -- effect ---------------------------------------------------------
    def effect_due(self, now):
        if not self.cfg.get("ttfx") or self.interval is None:
            return False
        return now >= next_effect_at(self.started, self.last_effect, self.interval)

    def play_ttfx(self, effect):
        """Run one effect; "input" if the person touched, otherwise "done"."""
        cfg = self.cfg
        self.sess._write("\x1b[2J\x1b[H")
        _, rows = self.sess.size()
        child = subprocess.Popen(ttfx_command(cfg["ttfx"], cfg["banner"], effect, rows),
                                 stdin=subprocess.DEVNULL)
        deadline = time.monotonic() + EFFECT_MAX_SECONDS
        result = "done"
        try:
            while child.poll() is None and time.monotonic() < deadline:
                events = self.sess.wait(0.5)
                if any(ev[0] == "quit" for ev in events):
                    return "quit"
                for ev in events:
                    if ev[0] == "input":
                        self.sess.read_release(ev[1])
                        return "input"
        finally:
            if child.poll() is None:
                child.terminate()
            try:
                child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        return result

    def hold_banner(self):
        """Leave the finished banner up for a moment; "input"/"quit"/"done"."""
        end = time.monotonic() + BANNER_HOLD_SECONDS
        while time.monotonic() < end:
            for ev in self.sess.wait(max(0.05, end - time.monotonic())):
                if ev[0] == "quit":
                    return "quit"
                if ev[0] == "input":
                    self.sess.read_release(ev[1])
                    return "input"
        return "done"

    # -- ending ---------------------------------------------------------
    def run_on_end(self, key="on_end"):
        command = self.cfg.get(key)
        if not command:
            return
        try:
            subprocess.run(shlex.split(command), timeout=15, check=False)
        except (OSError, subprocess.SubprocessError):
            pass

    def run_on_close(self):
        self.run_on_end("on_close")

    # -- the loop -------------------------------------------------------
    def run(self):
        """Returns why it ended: "input", "quit", "unplugged" or "cap"."""
        lit = self.display()
        while True:
            now = self.clock()
            if now >= self.next_poll:
                self.next_poll = now + POLL_SECONDS
                if not self.charger():
                    self.end()
                    return "unplugged"
                if self.max_up is not None and now - self.started >= self.max_up:
                    self.end()
                    return "cap"
                lit = self.display()
                if not lit:
                    self.drawn_minute = None
            if lit:
                if self.effect_due(now):
                    self.last_effect = now
                    outcome = self.play(effect_for(self.effects_played))
                    self.effects_played += 1
                    if outcome == "done":
                        outcome = self.hold_banner()
                    if outcome in ("input", "quit"):
                        return outcome
                    self.draw(self.clock())
                    continue
                if self.drawn_minute != int(now // 60):
                    self.draw(now)
            events = self.sess.wait(self.timeout(now, lit))
            for ev in events:
                if ev[0] == "quit":
                    return "quit"
                if ev[0] == "input":
                    self.sess.read_release(ev[1])
                    return "input"
                if ev[0] == "resize":
                    self.drawn_minute = None

    def timeout(self, now, lit):
        """Seconds to sleep: the next minute, effect or poll, whichever is first."""
        targets = [self.next_poll]
        if lit:
            targets.append((int(now // 60) + 1) * 60 + 0.05)
            if self.cfg.get("ttfx") and self.interval is not None:
                targets.append(next_effect_at(self.started, self.last_effect, self.interval))
        return max(0.05, min(targets) - now)


# ---------------------------------------------------------------------------

def pid_file_write(path):
    if path:
        try:
            Path(path).write_text(f"{os.getpid()}\n")
        except OSError:
            pass


def pid_file_remove(path):
    if path:
        try:
            Path(path).unlink()
        except OSError:
            pass


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--ttfx")
    parser.add_argument("--banner")
    parser.add_argument("--pid-file")
    parser.add_argument("--on-end", help="command run before closing for the charger or the cap")
    parser.add_argument("--on-close", help="command run when input or lost focus closes the card")
    parser.add_argument("--notification-socket", help="the broker socket, for the count dot")
    parser.add_argument("--prefs-dir", default=PREFS_DIR)
    parser.add_argument("--interval", type=int,
                        help="seconds between effects (debug; default: the Clock effects setting)")
    parser.add_argument("--max-up", type=int,
                        help="seconds before closing (debug; default: the Clock limit setting)")
    parser.add_argument("--render-once", metavar="WIDTHxHEIGHT")
    args = parser.parse_args(argv)
    if args.render_once:
        cols, rows = (int(p) for p in args.render_once.lower().split("x"))
        now = time.time()
        print(clock_layout(cols, rows, time.localtime(now), int(now // 60)).plain())
        return 0
    if not sys.stdin.isatty():
        print("k230-exhibition: needs a terminal", file=sys.stderr)
        return 1
    cfg = {"ttfx": args.ttfx, "banner": args.banner, "on_end": args.on_end,
           "on_close": args.on_close, "notification_socket": args.notification_socket,
           "interval": (read_effect_interval(args.prefs_dir)
                         if args.interval is None else args.interval),
           "max_up": read_max_up(args.prefs_dir) if args.max_up is None else args.max_up,
           "prefs_dir": args.prefs_dir}
    pid_file_write(args.pid_file)
    try:
        with ExhibitSession() as sess:
            exhibition = Exhibition(sess, cfg)
            if exhibition.run() in ("input", "quit"):
                exhibition.run_on_close()
    finally:
        pid_file_remove(args.pid_file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
