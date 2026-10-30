#!/usr/bin/env python3
"""Full-screen terminal apps for the handheld: clock, timer and weather.

Each app owns the whole Foot window (alternate screen, hidden cursor) and
draws with plain ANSI. Only the default foreground/background and the
palette's bright blue are used, so the active theme's Foot palette colours
everything. Layout, glyph, parsing and timer logic are pure functions; the
terminal and network code is a thin shell around them.

    k230_term_apps.py clock
    k230_term_apps.py timer [seconds]
    k230_term_apps.py weather
    k230_term_apps.py timerd DEADLINE INITIAL STATE   (internal: outlives a closed Timer card)
    k230_term_apps.py APP ... --render-once WIDTHxHEIGHT   (debug: one frame)
"""
import json
import math
import os
import select
import shutil
import signal
import socket
import subprocess
import sys
import time
from collections import namedtuple
from pathlib import Path

ACCENT = "\x1b[94m"
ACCENT_BOLD = "\x1b[1;94m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
BLOCK = "█"

# ---------------------------------------------------------------------------
# Block-glyph font: five rows per glyph, one unit per grid cell.

_GLYPHS = {
    "0": ("###", "# #", "# #", "# #", "###"),
    "1": (" # ", "## ", " # ", " # ", "###"),
    "2": ("###", "  #", "###", "#  ", "###"),
    "3": ("###", "  #", "###", "  #", "###"),
    "4": ("# #", "# #", "###", "  #", "  #"),
    "5": ("###", "#  ", "###", "  #", "###"),
    "6": ("###", "#  ", "###", "# #", "###"),
    "7": ("###", "  #", "  #", "  #", "  #"),
    "8": ("###", "# #", "###", "# #", "###"),
    "9": ("###", "# #", "###", "  #", "###"),
    ":": (" ", "#", " ", "#", " "),
    "-": ("   ", "   ", "###", "   ", "   "),
    "°": ("##", "##", "  ", "  ", "  "),
    "'": ("#", "#", " ", " ", " "),
    " ": ("  ", "  ", "  ", "  ", "  "),
    "F": ("###", "#  ", "## ", "#  ", "#  "),
    "C": ("###", "#  ", "#  ", "#  ", "###"),
    "T": ("###", " # ", " # ", " # ", " # "),
    "I": ("###", " # ", " # ", " # ", "###"),
    "M": ("#   #", "## ##", "# # #", "#   #", "#   #"),
    "E": ("###", "#  ", "## ", "#  ", "###"),
    "S": ("###", "#  ", "###", "  #", "###"),
    "U": ("# #", "# #", "# #", "# #", "###"),
    "P": ("###", "# #", "###", "#  ", "#  "),
}
GLYPH_ROWS = 5
GLYPH_GAP = 1


def text_units(text):
    """Width of `text` in glyph-grid units, gaps included."""
    if not text:
        return 0
    return sum(len(_GLYPHS[c][0]) for c in text) + GLYPH_GAP * (len(text) - 1)


def render_text(text, sx, sy):
    """Rows of block characters for `text`, each cell sx columns by sy rows."""
    rows = []
    for r in range(GLYPH_ROWS):
        line = []
        for i, c in enumerate(text):
            if i:
                line.append(" " * GLYPH_GAP)
            line.append(_GLYPHS[c][r])
        cells = "".join(line)
        row = "".join((BLOCK if ch == "#" else " ") * sx for ch in cells)
        rows.extend([row] * sy)
    return rows


def pick_scale(text, cols, rows, reserve_rows, width_fraction=0.7):
    """Largest (sx, sy) for a glyph run: a glyph cell is sx columns by sy
    rows with sx about twice sy so cells look square, and the run stays
    within `width_fraction` of the width and `rows - reserve_rows` high."""
    units = max(1, text_units(text))
    width_budget = max(units, int(cols * width_fraction))
    height_budget = max(GLYPH_ROWS, rows - reserve_rows)
    sy = max(1, height_budget // GLYPH_ROWS)
    while sy > 1 and 2 * sy * units > width_budget:
        sy -= 1
    sx = max(1, min(2 * sy + 1, width_budget // units))
    return sx, sy


def centre(size, avail):
    """Offset that centres `size` within `avail` (never negative)."""
    return max(0, (avail - size) // 2)


# ---------------------------------------------------------------------------
# Frame: a character grid, drawn whole each time (no clear, so no flicker).

class Frame:
    def __init__(self, cols, rows):
        self.cols = cols
        self.rows = rows
        self.cells = [[(" ", "")] * cols for _ in range(rows)]

    def put(self, row, col, text, sgr=""):
        """Write `text` at 1-based (row, col), clipped to the frame."""
        if not 1 <= row <= self.rows:
            return
        line = self.cells[row - 1]
        for i, ch in enumerate(text):
            c = col - 1 + i
            if 0 <= c < self.cols:
                line[c] = (ch, sgr)

    def put_centred(self, row, text, sgr=""):
        self.put(row, 1 + centre(len(text), self.cols), text, sgr)

    def put_big(self, row, text, sx, sy, sgr=ACCENT, col=None):
        rows = render_text(text, sx, sy)
        width = len(rows[0])
        if col is None:
            col = 1 + centre(width, self.cols)
        for i, line in enumerate(rows):
            self.put(row + i, col, line, sgr)

    def plain(self):
        return "\n".join("".join(ch for ch, _ in line).rstrip() for line in self.cells)

    def ansi(self):
        out = []
        for r, line in enumerate(self.cells, 1):
            out.append(f"\x1b[{r};1H")
            current = ""
            for ch, sgr in line:
                if sgr != current:
                    out.append("\x1b[0m" + sgr)
                    current = sgr
                out.append(ch)
            out.append("\x1b[0m")
        return "".join(out)


# ---------------------------------------------------------------------------
# Buttons: boxed labels with rectangle hit testing (1-based cell coordinates).

Button = namedtuple("Button", "key label x0 y0 x1 y1")


def layout_buttons(keys_labels, cols, top, height=3, pad=3, gap=2):
    """Centre a row of buttons whose top row is `top`; x1/y1 are inclusive."""
    while True:
        widths = [len(label) + 2 * pad for _, label in keys_labels]
        total = sum(widths) + gap * (len(widths) - 1)
        if total <= cols or (pad <= 1 and gap <= 1):
            break
        if pad > 1:
            pad -= 1
        else:
            gap -= 1
    x = 1 + centre(total, cols)
    buttons = []
    for (key, label), width in zip(keys_labels, widths):
        buttons.append(Button(key, label, x, top, x + width - 1, top + height - 1))
        x += width + gap
    return buttons


def hit_test(buttons, x, y):
    for b in buttons:
        if b.x0 <= x <= b.x1 and b.y0 <= y <= b.y1:
            return b.key
    return None


def draw_button(frame, b, sgr=""):
    inner = b.x1 - b.x0 - 1
    mid = (b.y0 + b.y1) // 2
    frame.put(b.y0, b.x0, "╭" + "─" * inner + "╮", sgr)
    for y in range(b.y0 + 1, b.y1):
        frame.put(y, b.x0, "│" + " " * inner + "│", sgr)
    frame.put(b.y1, b.x0, "╰" + "─" * inner + "╯", sgr)
    frame.put(mid, b.x0 + 1 + centre(len(b.label), inner), b.label, sgr + BOLD)


# ---------------------------------------------------------------------------
# Input: SGR mouse reports and a few keys from raw stdin bytes.

def parse_input(data):
    """Split bytes into events; returns (events, unparsed tail).

    Events are ("key", char) or ("click", x, y) for a left press. Releases,
    drags, wheel reports and other escape sequences are dropped."""
    events = []
    i = 0
    n = len(data)
    while i < n:
        b = data[i]
        if b != 0x1B:
            events.append(("key", chr(b)))
            i += 1
            continue
        if i + 1 == n:
            events.append(("key", "esc"))
            i += 1
            continue
        if data[i + 1] != ord("["):
            i += 2
            continue
        j = i + 2
        while j < n and not 0x40 <= data[j] <= 0x7E:
            j += 1
        if j >= n:
            return events, data[i:]
        final = chr(data[j])
        body = data[i + 2:j].decode("ascii", "replace")
        if body.startswith("<") and final in "Mm":
            try:
                code, x, y = (int(p) for p in body[1:].split(";"))
            except ValueError:
                code = None
            # Bits 4/8/16 are modifiers; 32 is motion, 64 the wheel.
            if final == "M" and code is not None and code & ~(4 | 8 | 16) == 0:
                events.append(("click", x, y))
        i = j + 1
    return events, b""


# ---------------------------------------------------------------------------
# Clock

# The shell's clock-format preference (`shell_prefs.rs`, CLOCK_FORMAT_FILE):
# only the word `12-hour` selects a 12-hour clock; anything else, or no file,
# keeps 24-hour.
PREFS_DIR = "/var/lib/k230-shell-prefs"
CLOCK_FORMAT_FILE = "clock-format"


def read_twelve_hour(prefs_dir=PREFS_DIR):
    try:
        return (Path(prefs_dir) / CLOCK_FORMAT_FILE).read_text().strip() == "12-hour"
    except OSError:
        return False


def local_time(when=None):
    """`time.localtime` after re-reading /etc/localtime: Settings changes the
    zone while apps run, and `localtime_r` alone never notices."""
    time.tzset()
    return time.localtime(when)


def clock_digits(tm, twelve=False):
    """`21:05`, or `9:05` on a 12-hour clock (midnight and noon are 12)."""
    if not twelve:
        return time.strftime("%H:%M", tm)
    return f"{tm.tm_hour % 12 or 12}:{tm.tm_min:02d}"


def meridiem(tm):
    return "AM" if tm.tm_hour < 12 else "PM"


def clock_text(tm, twelve=False):
    """A time inside a line of text: `21:05`, or `9:05 PM`."""
    return f"{clock_digits(tm, True)} {meridiem(tm)}" if twelve else clock_digits(tm)


def clock_date_line(tm, twelve=False):
    """The date under big digits, which have no letters for AM/PM, so a
    12-hour clock leads the date with it: `PM · Thursday 29 October`."""
    date = time.strftime("%A %-d %B", tm)
    return f"{meridiem(tm)} · {date}" if twelve else date


def clock_frame(cols, rows, tm, subsec=0.0, twelve=False):
    f = Frame(cols, rows)
    text = clock_digits(tm, twelve)
    sx, sy = pick_scale(text, cols, rows, reserve_rows=7)
    big_h = GLYPH_ROWS * sy
    big_w = text_units(text) * sx
    total = big_h + 4
    top = 1 + centre(total, rows)
    f.put_big(top, text, sx, sy)
    # A slim bar fills across the minute, one step per second.
    bar_row = top + big_h + 1
    bar_w = max(1, min(big_w, cols - 2))
    filled = (bar_w * tm.tm_sec) // 59 if tm.tm_sec else 0
    bar_col = 1 + centre(bar_w, cols)
    f.put(bar_row, bar_col, "━" * filled, ACCENT)
    f.put(bar_row, bar_col + filled, "─" * (bar_w - filled), DIM)
    f.put_centred(bar_row + 2, clock_date_line(tm, twelve), BOLD)
    return f


def next_second_delay(now):
    return 1.0 - (now % 1.0) + 0.01


# ---------------------------------------------------------------------------
# Timer

MAX_SECONDS = 99 * 3600 + 59 * 60 + 59
TimerState = namedtuple("TimerState", "initial remaining running deadline expired")


def timer_new(seconds):
    seconds = max(0, min(int(seconds), MAX_SECONDS))
    return TimerState(seconds, seconds, False, 0.0, False)


def timer_remaining(s, now):
    if s.running:
        return max(0, math.ceil(s.deadline - now - 1e-9))
    return s.remaining


def timer_start(s, now):
    if s.expired:
        s = timer_new(s.initial)
    if s.running or s.remaining <= 0:
        return s
    return s._replace(running=True, deadline=now + s.remaining)


def timer_pause(s, now):
    if not s.running:
        return s
    return s._replace(running=False, remaining=timer_remaining(s, now), deadline=0.0)


def timer_toggle(s, now):
    return timer_pause(s, now) if s.running else timer_start(s, now)


def timer_add(s, delta, now):
    """Move the timer by `delta` seconds. A running timer never drops below
    one second this way; an idle one also moves its reset value."""
    if s.running:
        deadline = max(s.deadline + delta, now + 1)
        if deadline - now > MAX_SECONDS:
            deadline = now + MAX_SECONDS
        return s._replace(deadline=deadline)
    if s.expired:
        value = max(0, min(delta, MAX_SECONDS))
        return s._replace(remaining=value, expired=False)
    value = max(0, min(s.remaining + delta, MAX_SECONDS))
    initial = value if s.remaining == s.initial else s.initial
    return s._replace(remaining=value, initial=initial)


def timer_reset(s, now=0.0):
    return timer_new(s.initial)


def timer_tick(s, now):
    if s.running and s.deadline - now <= 1e-9:
        return s._replace(running=False, remaining=0, deadline=0.0, expired=True)
    return s


# A silent device needs the shell's notification broker to alert the person.
# The Timer and its detached helper are listed there as the trusted "Timer"
# source (nix/shell.nix); a missing broker never disturbs the countdown.

def notification_socket():
    return os.environ.get("K230_NOTIFICATION_SOCKET", "/run/shell-notifications/events.sock")


def timer_expiry_request(initial):
    return {"operation": "emit", "summary": "Timer finished",
            "body": f"{format_hms(initial)} elapsed" if initial else "",
            "tag": "timer", "priority": "important", "private": False}


def notify_broker(request, path=None):
    """One request to the broker; True when it accepted. Never raises."""
    try:
        with socket.socket(socket.AF_UNIX) as conn:
            conn.settimeout(3)
            conn.connect(path or notification_socket())
            conn.sendall(json.dumps(request, separators=(",", ":")).encode() + b"\n")
            reply = b""
            while b"\n" not in reply and len(reply) < 65536:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                reply += chunk
        return json.loads(reply.split(b"\n", 1)[0]).get("state") == "accepted"
    except (OSError, ValueError, AttributeError):
        return False


def timer_state_path():
    base = os.environ.get("K230_TIMER_STATE_DIR") or os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    return os.path.join(base, "k230-timer.json")


def timer_pending(path):
    """The detached timer's record if its helper is still alive, else None."""
    try:
        with open(path) as handle:
            record = json.load(handle)
        pid, deadline, initial = int(record["pid"]), float(record["deadline"]), int(record["initial"])
        with open(f"/proc/{pid}/cmdline", "rb") as handle:
            if b"timerd" not in handle.read():
                return None
        return {"pid": pid, "deadline": deadline, "initial": initial}
    except (OSError, ValueError, KeyError, TypeError):
        return None


def timer_adopt(path, now):
    """Take back a countdown a closed card left behind: stop its helper and
    return the running state, or None when nothing is pending or it is past."""
    record = timer_pending(path)
    if record is None:
        return None
    try:
        os.kill(record["pid"], signal.SIGTERM)
    except OSError:
        pass
    try:
        os.unlink(path)
    except OSError:
        pass
    left = record["deadline"] - now
    if left <= 0:
        return None
    return TimerState(record["initial"], math.ceil(left), True, record["deadline"], False)


def timer_detach(state, path):
    """Leave a helper that posts the expiry after this card is gone."""
    if not state.running:
        return None
    try:
        child = subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), "timerd", repr(state.deadline), str(state.initial), path],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True, close_fds=True)
        tmp = f"{path}.{child.pid}"
        with open(tmp, "w") as handle:
            json.dump({"pid": child.pid, "deadline": state.deadline, "initial": state.initial}, handle)
        os.replace(tmp, path)
        return child
    except OSError:
        return None


def run_timerd(deadline, initial, path, clock=time.monotonic, sleep=time.sleep, notify=notify_broker):
    """Sleep to the deadline (no polling), then alert once and clean up."""
    while True:
        left = deadline - clock()
        if left <= 0:
            break
        sleep(left)
    notify(timer_expiry_request(initial))
    try:
        with open(path) as handle:
            if int(json.load(handle).get("pid", -1)) == os.getpid():
                os.unlink(path)
    except (OSError, ValueError, AttributeError):
        pass


def format_hms(seconds):
    h, rem = divmod(seconds, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def timer_buttons(s, cols, rows):
    labels = [("toggle", "Pause" if s.running else "Start"),
              ("sub", "−1 min"), ("add", "+1 min"), ("reset", "Reset")]
    return layout_buttons(labels, cols, top=max(1, rows - 4))


def timer_frame(cols, rows, s, now):
    f = Frame(cols, rows)
    buttons = timer_buttons(s, cols, rows)
    left = timer_remaining(s, now)
    text = "TIME'S UP" if s.expired else format_hms(left)
    # Reserve the button row, its gap, and one line for the status text.
    sx, sy = pick_scale(text, cols, rows, reserve_rows=7, width_fraction=0.85)
    big_h = GLYPH_ROWS * sy
    avail = buttons[0].y0 - 2
    top = 1 + centre(big_h + 2, avail)
    f.put_big(top, text, sx, sy, ACCENT_BOLD if s.expired else ACCENT)
    if s.expired:
        status = "Time's up"
    elif s.running:
        status = "Running"
    elif left == s.initial:
        status = "Ready"
    else:
        status = "Paused"
    f.put_centred(top + big_h + 1, status, BOLD if s.expired else DIM)
    for b in buttons:
        draw_button(f, b, ACCENT if b.key == "toggle" else "")
    return f


def timer_apply(s, key, now):
    """Apply a button or key action to the timer state."""
    if key == "toggle":
        return timer_toggle(s, now)
    if key == "add":
        return timer_add(s, 60, now)
    if key == "sub":
        return timer_add(s, -60, now)
    if key == "reset":
        return timer_reset(s, now)
    return s


TIMER_KEYS = {" ": "toggle", "\r": "toggle", "+": "add", "=": "add",
              "-": "sub", "_": "sub", "r": "reset", "R": "reset"}


def timer_delay(s, now):
    """Seconds until the display next changes; None while idle."""
    if not s.running:
        return None
    left = s.deadline - now
    frac = left % 1.0
    return (frac if frac > 0.02 else 1.0 + frac) + 0.01


# ---------------------------------------------------------------------------
# Weather: the Home widget's cache file, extended with a few extra fields.

WTTR_URL = "https://wttr.in/?format=j1"
REFRESH_SECONDS = 30 * 60
OFFLINE_RETRY_SECONDS = 5 * 60


def cache_path(env=None):
    env = os.environ if env is None else env
    override = env.get("K230_WEATHER_CACHE", "").strip()
    if override:
        return override
    xdg = env.get("XDG_CACHE_HOME", "").strip()
    if xdg:
        return os.path.join(xdg, "k230-shell", "weather.json")
    home = env.get("HOME", "").strip()
    if home:
        return os.path.join(home, ".cache", "k230-shell", "weather.json")
    return None


def hour_label(hour_abs):
    hour = hour_abs % 24
    period = "am" if hour < 12 else "pm"
    return f"{hour % 12 or 12}{period}"


def fahrenheit(celsius):
    return math.floor(celsius * 9 / 5 + 32 + 0.5)


def _int(value, default=0):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _first(items, key="value"):
    if isinstance(items, list) and items and isinstance(items[0], dict):
        return str(items[0].get(key, ""))
    return ""


def parse_wttr_j1(raw, current_hour, now=0):
    """wttr.in j1 JSON -> cache snapshot, or None when it is not j1.

    The fields the Home widget reads keep its names (temperature in Celsius,
    five `forecast` entries); `region`, `humidity`, `wind_kmph`, `wind_dir`
    and the six-entry `slots` are extras its parser ignores."""
    try:
        doc = json.loads(raw)
        current = doc["current_condition"][0]
        days = doc["weather"]
        today = days[0]
    except (ValueError, KeyError, IndexError, TypeError):
        return None
    if not isinstance(current, dict) or not isinstance(today, dict):
        return None
    area = doc.get("nearest_area") or [{}]
    area = area[0] if isinstance(area[0], dict) else {}
    slots = []
    for day_index, day in enumerate(days[:2]):
        for hour in day.get("hourly", []):
            hour_abs = day_index * 24 + _int(hour.get("time")) // 100
            if hour_abs < current_hour:
                continue
            slots.append({"label": hour_label(hour_abs),
                          "temp_c": _int(hour.get("tempC")),
                          "condition": _first(hour.get("weatherDesc"))})
    slots = slots[:6]
    return {
        "location": _first(area.get("areaName")),
        "region": _first(area.get("region")),
        "condition": _first(current.get("weatherDesc")),
        "temperature_c": _int(current.get("temp_C")),
        "feels_like_c": _int(current.get("FeelsLikeC")),
        "high_c": _int(today.get("maxtempC")),
        "low_c": _int(today.get("mintempC")),
        "humidity": _int(current.get("humidity"), -1),
        "wind_kmph": _int(current.get("windspeedKmph"), -1),
        "wind_dir": str(current.get("winddir16Point", "")),
        "forecast": slots[:5],
        "slots": slots,
        "fetched_unix_secs": int(now),
    }


def is_stale(snapshot, now):
    if not snapshot:
        return True
    return now - snapshot.get("fetched_unix_secs", 0) >= REFRESH_SECONDS


def load_cache(path):
    try:
        with open(path, "rb") as fh:
            doc = json.load(fh)
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(doc, dict) or "temperature_c" not in doc:
        return None
    return doc


def save_cache(path, snapshot):
    """Atomic best-effort write; a failure only costs an extra fetch."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(snapshot, fh)
        os.replace(tmp, path)
    except OSError:
        pass


def fetch_snapshot(now=None, timeout=8):
    """Fetch wttr.in; None on any failure."""
    import urllib.request
    now = time.time() if now is None else now
    request = urllib.request.Request(WTTR_URL, headers={"User-Agent": "curl"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", "replace")
    except Exception:
        return None
    return parse_wttr_j1(body, local_time(now).tm_hour, now)


def wind_text(snapshot):
    kmph = snapshot.get("wind_kmph", -1)
    if kmph < 0:
        return ""
    mph = math.floor(kmph * 0.621371 + 0.5)
    return f"Wind {mph} mph {snapshot.get('wind_dir', '')}".rstrip()


def weather_frame(cols, rows, snapshot, offline, now, fetching=False):
    """Returns (frame, buttons)."""
    f = Frame(cols, rows)
    label = "Retry" if (offline and not snapshot) else "Refresh"
    buttons = layout_buttons([("refresh", label)], cols, top=max(1, rows - 3))
    if fetching and not snapshot:
        f.put_centred(centre(1, rows) + 1, "Fetching weather...", DIM)
        return f, []
    if not snapshot:
        f.put_centred(centre(3, rows - 4) + 1, "No weather data — check Wi-Fi", BOLD)
        for b in buttons:
            draw_button(f, b, ACCENT)
        return f, buttons

    place = ", ".join(p for p in (snapshot.get("location"), snapshot.get("region")) if p)
    temp = f"{fahrenheit(snapshot.get('temperature_c', 0))}°F"
    details = [f"Feels like {fahrenheit(snapshot.get('feels_like_c', 0))}°F"]
    if snapshot.get("humidity", -1) >= 0:
        details.append(f"Humidity {snapshot['humidity']}%")
    if wind_text(snapshot):
        details.append(wind_text(snapshot))
    slots = (snapshot.get("slots") or snapshot.get("forecast") or [])[:6]
    # place, gap, big, condition, details, gap, 3-line strip, status, button
    sx, sy = pick_scale(temp, cols, rows, reserve_rows=14, width_fraction=0.6)
    big_h = GLYPH_ROWS * sy
    used = 1 + 1 + big_h + 2 + 1 + (3 if slots else 0) + 1 + 3
    row = 1 + centre(used, rows)
    f.put_centred(row, place or "Weather", ACCENT_BOLD)
    row += 2
    f.put_big(row, temp, sx, sy, ACCENT)
    row += big_h
    f.put_centred(row, snapshot.get("condition", ""), BOLD)
    f.put_centred(row + 1, "  ·  ".join(details), DIM)
    row += 3
    if slots:
        width = max(6, min(14, cols // len(slots)))
        left = 1 + centre(width * len(slots), cols)
        for i, slot in enumerate(slots):
            col = left + i * width
            cond = slot.get("condition", "")[: width - 1]
            for r, (text, sgr) in enumerate(((slot.get("label", ""), DIM),
                                              (f"{fahrenheit(slot.get('temp_c', 0))}°F", BOLD),
                                              (cond, ""))):
                f.put(row + r, col + centre(len(text), width), text, sgr)
        row += 4
    status = ""
    stamp = snapshot.get("fetched_unix_secs", 0)
    if offline:
        status = "Offline — showing data from " + clock_text(local_time(stamp), read_twelve_hour())
    elif stamp:
        status = "Updated " + clock_text(local_time(stamp), read_twelve_hour())
    f.put_centred(buttons[0].y0 - 1, status, DIM)
    for b in buttons:
        draw_button(f, b, ACCENT)
    return f, buttons


# ---------------------------------------------------------------------------
# Terminal session: alternate screen, hidden cursor, mouse, signals.

class Session:
    def __init__(self, mouse):
        self.mouse = mouse
        self.fd = sys.stdin.fileno()
        self.quit = False
        self.resized = False
        self.pending = b""
        self.saved = None
        self.wake_r, self.wake_w = os.pipe()
        for fd in (self.wake_r, self.wake_w):
            os.set_blocking(fd, False)

    def __enter__(self):
        import termios
        import tty
        self.saved = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        signal.set_wakeup_fd(self.wake_w, warn_on_full_buffer=False)
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(sig, self._on_quit)
        signal.signal(signal.SIGWINCH, self._on_winch)
        modes = "\x1b[?1049h\x1b[?25l" + ("\x1b[?1000h\x1b[?1006h" if self.mouse else "")
        self._write(modes)
        return self

    def __exit__(self, *exc):
        import termios
        modes = ("\x1b[?1006l\x1b[?1000l" if self.mouse else "") + "\x1b[?25h\x1b[?1049l"
        self._write(modes)
        if self.saved is not None:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.saved)
        signal.set_wakeup_fd(-1)
        return False

    def _on_quit(self, *_):
        self.quit = True

    def _on_winch(self, *_):
        self.resized = True

    @staticmethod
    def _write(text):
        sys.stdout.write(text)
        sys.stdout.flush()

    def size(self):
        size = shutil.get_terminal_size((80, 24))
        return size.columns, size.lines

    def draw(self, frame):
        self._write(frame.ansi())

    def wait(self, timeout):
        """Block until input, a signal or `timeout` seconds; returns events:
        ("quit",), ("resize",), ("key", c), ("click", x, y) or ("timeout",)."""
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
            parsed, self.pending = parse_input(self.pending + data)
            for ev in parsed:
                if ev == ("key", "q") or ev == ("key", "Q") or ev == ("key", "esc"):
                    return [("quit",)]
                events.append(ev)
        if not ready and not events:
            events.append(("timeout",))
        return events


def run_clock(sess):
    while True:
        cols, rows = sess.size()
        now = time.time()
        sess.draw(clock_frame(cols, rows, local_time(now), twelve=read_twelve_hour()))
        if any(ev[0] == "quit" for ev in sess.wait(next_second_delay(now))):
            return


def run_timer(sess, seconds, path=None):
    path = path or timer_state_path()
    state = timer_adopt(path, time.monotonic()) or timer_new(seconds)
    rang = False
    while True:
        cols, rows = sess.size()
        now = time.monotonic()
        state = timer_tick(state, now)
        if state.expired and not rang:
            rang = True
            sess._write("\a")
            notify_broker(timer_expiry_request(state.initial))
        elif not state.expired:
            rang = False
        sess.draw(timer_frame(cols, rows, state, now))
        buttons = timer_buttons(state, cols, rows)
        for ev in sess.wait(timer_delay(state, now)):
            now = time.monotonic()
            action = None
            if ev[0] == "quit":
                timer_detach(timer_tick(state, now), path)
                return
            if ev[0] == "click":
                action = hit_test(buttons, ev[1], ev[2])
            elif ev[0] == "key":
                action = TIMER_KEYS.get(ev[1])
            if action:
                state = timer_apply(timer_tick(state, now), action, now)


def run_weather(sess, path):
    snapshot = load_cache(path) if path else None
    offline = False
    due = is_stale(snapshot, time.time())
    while True:
        cols, rows = sess.size()
        if due:
            frame, _ = weather_frame(cols, rows, snapshot, offline, time.time(), fetching=True)
            sess.draw(frame)
            fresh = fetch_snapshot()
            if fresh:
                snapshot, offline = fresh, False
                if path:
                    save_cache(path, snapshot)
            else:
                offline = True
            due = False
        now = time.time()
        frame, buttons = weather_frame(cols, rows, snapshot, offline, now)
        sess.draw(frame)
        if snapshot and not offline:
            timeout = max(1.0, snapshot.get("fetched_unix_secs", 0) + REFRESH_SECONDS - now)
        else:
            timeout = OFFLINE_RETRY_SECONDS
        for ev in sess.wait(timeout):
            if ev[0] == "quit":
                return
            if ev[0] == "timeout":
                due = True
            elif ev[0] == "click" and hit_test(buttons, ev[1], ev[2]) == "refresh":
                due = True
            elif ev == ("key", "r") or ev == ("key", "R") or ev == ("key", " "):
                due = True


def render_once(app, args, size):
    cols, rows = (int(p) for p in size.lower().split("x"))
    now = time.time()
    if app == "clock":
        frame = clock_frame(cols, rows, local_time(now), twelve=read_twelve_hour())
    elif app == "timer":
        frame = timer_frame(cols, rows, timer_new(timer_seconds(args)), time.monotonic())
    else:
        path = cache_path()
        snapshot = load_cache(path) if path else None
        frame, _ = weather_frame(cols, rows, snapshot, snapshot is None, now)
    print(frame.plain())


def timer_seconds(args):
    try:
        return int(args[0]) if args else 300
    except ValueError:
        return 300


def main(argv):
    args = list(argv[1:])
    size = None
    if "--render-once" in args:
        i = args.index("--render-once")
        try:
            size = args[i + 1]
            del args[i:i + 2]
        except IndexError:
            print("--render-once needs WIDTHxHEIGHT", file=sys.stderr)
            return 2
    if args and args[0] == "timerd" and len(args) == 4:
        try:
            run_timerd(float(args[1]), int(args[2]), args[3])
        except ValueError:
            return 2
        return 0
    if not args or args[0] not in ("clock", "timer", "weather"):
        print("usage: k230-term-apps clock|timer [seconds]|weather", file=sys.stderr)
        return 2
    app, rest = args[0], args[1:]
    if size:
        render_once(app, rest, size)
        return 0
    if not sys.stdin.isatty():
        print(f"k230-{app}: needs a terminal", file=sys.stderr)
        return 1
    with Session(mouse=app != "clock") as sess:
        if app == "clock":
            run_clock(sess)
        elif app == "timer":
            run_timer(sess, timer_seconds(rest))
        else:
            run_weather(sess, cache_path())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
