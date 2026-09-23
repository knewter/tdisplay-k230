#!/usr/bin/env python3
"""Board-only injected-touch checks for launcher metadata, focus, and rollback.

This script intentionally retains no screenshots or catalog titles.  It uses
short-lived native captures only to assert the card colours rendered by the
current launcher source.  Every executed interaction is injected through the
uinput touchscreen and is not evidence of a finger on the glass.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
import zlib

PANEL_WIDTH, PANEL_HEIGHT = 568, 1232
UP_START, UP_END = (284, 460), (284, 210)
DOWN_START, DOWN_END = (284, 300), (284, 600)


def run(args, *, capture=False, timeout=3):
    return subprocess.run(args, check=True, stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.PIPE if capture else None, text=capture,
                          timeout=timeout)


def inject(script, device, start, end=None):
    command = [script, device, str(start[0]), str(start[1])]
    if end:
        command += [str(end[0]), str(end[1])]
    # evemu-event invokes many subprocesses for a drag; the default command
    # timeout is intentionally too short under single-core load.
    run(command, timeout=10)
    time.sleep(0.30)  # exceeds the 200 ms animation bound


def png_pixels(path):
    """Return (width, height, RGB bytes) for non-interlaced 8-bit grim PNGs."""
    raw = Path(path).read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    pos, payload, width = 8, bytearray(), None
    while pos < len(raw):
        length = struct.unpack(">I", raw[pos:pos + 4])[0]
        kind, body = raw[pos + 4:pos + 8], raw[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", body)
            if depth != 8 or color not in (0, 2, 6) or compression or filtering or interlace:
                raise ValueError("unsupported grim PNG encoding")
            channels = {0: 1, 2: 3, 6: 4}[color]
        elif kind == b"IDAT":
            payload.extend(body)
        elif kind == b"IEND":
            break
    decoded = zlib.decompress(payload)
    stride, previous, rows, at = width * channels, bytearray(width * channels), [], 0
    for _ in range(height):
        filter_type, line = decoded[at], bytearray(decoded[at + 1:at + 1 + stride])
        at += stride + 1
        for index in range(stride):
            left = line[index - channels] if index >= channels else 0
            above = previous[index]
            upper_left = previous[index - channels] if index >= channels else 0
            if filter_type == 1:
                line[index] = (line[index] + left) & 255
            elif filter_type == 2:
                line[index] = (line[index] + above) & 255
            elif filter_type == 3:
                line[index] = (line[index] + ((left + above) // 2)) & 255
            elif filter_type == 4:
                p, pa, pb, pc = left + above - upper_left, 0, 0, 0
                pa, pb, pc = abs(p - left), abs(p - above), abs(p - upper_left)
                line[index] = (line[index] + (left if pa <= pb and pa <= pc else above if pb <= pc else upper_left)) & 255
            elif filter_type != 0:
                raise ValueError("unsupported PNG filter")
        rows.extend(line)
        previous = line
    rgb = bytearray()
    for index in range(0, len(rows), channels):
        pixel = rows[index:index + channels]
        rgb.extend(pixel[:3] if channels != 1 else pixel * 3)
    return width, height, bytes(rgb)


def screen(grim, directory, name):
    path = Path(directory) / name
    run([grim, str(path)])
    return png_pixels(path)


def launcher_bounds(frame):
    """Find the #101821 launcher canvas at x=0 in a full-panel grim capture.

    Native evidence fixes the persistent bar at screen rows 0..55.  With
    wvkbd explicitly shown, canvas rows are 56..831 (776 pixels); hidden,
    they are 56..1231 (1176 pixels).  Detect rather than assume the keyboard
    state, and reject any other geometry.
    """
    width, height, rgb = frame
    base = (16, 24, 33)  # #111827 after the RGB565 scanout path
    rows = [y for y in range(height) if pixel(rgb, width, 0, y) == base]
    if not rows:
        raise RuntimeError("could not locate launcher canvas in grim capture")
    start, end = rows[0], rows[0]
    for y in rows[1:]:
        if y != end + 1:
            break
        end = y
    local_height = end - start + 1
    if start != 56 or local_height not in (776, 1176):
        raise RuntimeError(f"unexpected launcher bounds {start}..{end}")
    return start, local_height


def canvas_bytes(frame):
    width, _, rgb = frame
    top, height = launcher_bounds(frame)
    return rgb[top * width * 3:(top + height) * width * 3]


def pixel(rgb, width, x, y):
    at = (y * width + x) * 3
    return tuple(rgb[at:at + 3])


def card_geometry(height):
    page_size = 3 if height < 900 else 4
    top, gap, footer = 150, 14, height - 110
    return top, gap, (footer - top - 24 - (page_size - 1) * gap) // page_size, page_size


def window_card(rgb, width, x, y):
    """Source colours #24495a rendered through RGB565 have green/blue above no-card #243547."""
    red, green, blue = pixel(rgb, width, x, y)
    return 20 <= red <= 52 and green >= 62 and blue >= 78


def overview_has_two_cards(frame):
    width, _, rgb = frame
    origin, local_height = launcher_bounds(frame)
    top, gap, height_card, _ = card_geometry(local_height)
    return all(window_card(rgb, width, 32, origin + top + index * (height_card + gap) + 10)
               for index in (0, 1))


def header_hash(frame):
    width, _, rgb = frame
    origin, _ = launcher_bounds(frame)
    # Include the title and subtitle pixels, not only the common background.
    return hashlib.sha256(rgb[origin * width * 3:(origin + 145) * width * 3]).hexdigest()


def overview_ready(frame, apps_header):
    # Apps' Terminal and Monitor use the same fill as window cards.  A card
    # colour alone therefore cannot prove Up entered Windows.
    return header_hash(frame) != apps_header and overview_has_two_cards(frame)


def wait_frame(grim, directory, predicate, label, timeout=1.2):
    end = time.monotonic() + timeout
    while True:
        frame = screen(grim, directory, label + ".png")
        if predicate(frame):
            return frame
        if time.monotonic() >= end:
            raise RuntimeError(label + " did not reach the required rendered state")
        time.sleep(0.05)


def catalog(command):
    result = subprocess.run(command, shell=True, check=True, text=True, stdout=subprocess.PIPE,
                            timeout=2)
    rows = []
    for line in result.stdout.splitlines():
        fields = line.split("\t")
        if len(fields) == 4 and fields[0].isdigit():
            rows.append((fields[0], fields[2]))
    return rows


def process_ids(comm):
    result = []
    for path in Path("/proc").glob("[0-9]*"):
        try:
            if path.joinpath("comm").read_text().strip() == comm:
                result.append(path.name)
        except OSError:
            pass
    return tuple(sorted(result, key=int))


def focused_app(swaymsg):
    tree = json.loads(run([swaymsg, "-t", "get_tree", "-r"], capture=True).stdout)
    stack = [tree]
    while stack:
        node = stack.pop()
        if node.get("focused"):
            return node.get("app_id")
        stack.extend(node.get("nodes", []))
        stack.extend(node.get("floating_nodes", []))
    return None


def process_identity(pid):
    """Return PID plus Linux start time, so PID reuse cannot satisfy a check."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
        tail = stat[stat.rfind(")") + 2:].split()
        return (pid, tail[19])  # field 22 (starttime), after fields 1 and 2
    except (OSError, IndexError):
        return None


def same_process(identity):
    return identity is not None and process_identity(identity[0]) == identity


def wait_until(predicate, description, timeout=1.2):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(0.05)
    raise RuntimeError(description)


def require_launcher(pid):
    identity = process_identity(pid)
    if identity is None:
        raise RuntimeError("specified launcher PID is not running")
    return identity


def launcher_env_has(pid, name, value):
    try:
        entries = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
    except OSError:
        return False
    return (name + "=" + value).encode() in entries


def write_report(path, report):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n")
    temporary.replace(path)


def progress_report(args, completed, row_counts):
    write_report(args.report, {
        "result": "in-progress", "phase": "overview",
        "interaction_provenance": "injected-touch",
        "completed_cycles": completed, "catalog_row_counts": row_counts,
        "progress_note": "Completed cycles are preserved if a later board command times out.",
    })


def phase_overview(args, directory):
    require_launcher(args.launcher_pid)
    run(["sh", "-c", args.keyboard_show])
    time.sleep(.30)
    apps = screen(args.grim, directory, "apps.png")
    apps_header = header_hash(apps)
    _, local_height = launcher_bounds(apps)
    if local_height != 776:
        raise RuntimeError("wvkbd show signal did not produce the 400-pixel keyboard reservation")
    observed = []
    progress_report(args, 0, observed)
    for cycle in range(1, 21):
        inject(args.inject_script, args.device, UP_START, UP_END)
        frame = wait_frame(args.grim, directory,
                           lambda candidate: overview_ready(candidate, apps_header), "overview")
        rows = catalog(args.catalog_command)
        if len(rows) < 2:
            raise RuntimeError("catalog no longer has two rows while two rendered cards were expected")
        observed.append(len(rows))
        inject(args.inject_script, args.device, DOWN_START, DOWN_END)
        wait_frame(args.grim, directory, lambda frame: header_hash(frame) == apps_header, "apps-return")
        progress_report(args, cycle, observed)
    return {"overview_cycles": 20, "catalog_row_counts": observed,
            "keyboard": "explicit SIGUSR2 show with 400-pixel reservation",
            "rendered_two_cards_each": True}


def phase_focus(args, directory):
    launcher_identity = require_launcher(args.launcher_pid)
    if focused_app(args.swaymsg) != "k230-monitor":
        raise RuntimeError("Monitor must be focused before selecting Terminal")
    before = {name: process_ids(name) for name in ("foot", "htop")}
    if not all(before.values()):
        raise RuntimeError("Terminal and Monitor processes must already exist")
    apps_header = header_hash(screen(args.grim, directory, "apps-focus.png"))
    inject(args.inject_script, args.device, UP_START, UP_END)
    frame = wait_frame(args.grim, directory,
                       lambda candidate: overview_ready(candidate, apps_header), "overview-focus")
    rows = catalog(args.catalog_command)
    terminal_index = next((index for index, (_, app_id) in enumerate(rows) if app_id == "k230-terminal"), None)
    origin, local_height = launcher_bounds(frame)
    top, gap, card_height, page_size = card_geometry(local_height)
    if terminal_index is None or terminal_index >= page_size:
        raise RuntimeError("Terminal is not a first-page overview card")
    inject(args.inject_script, args.device,
           (284, origin + top + terminal_index * (card_height + gap) + card_height // 2))
    wait_until(lambda: not same_process(launcher_identity), "launcher did not close before focus")
    wait_until(lambda: focused_app(args.swaymsg) == "k230-terminal", "Terminal did not become focused")
    after = {name: process_ids(name) for name in ("foot", "htop")}
    if after != before:
        raise RuntimeError("focus changed Terminal or Monitor process identity")
    return {"launcher_closed_and_terminal_focused": True, "focused_app": "k230-terminal",
            "terminal_monitor_process_sets_unchanged": True}


def phase_rollback(args, directory):
    launcher_identity = require_launcher(args.launcher_pid)
    if not launcher_env_has(args.launcher_pid, "K230_LAUNCHER_GESTURES", "0"):
        raise RuntimeError("launcher was not started with K230_LAUNCHER_GESTURES=0")
    apps = screen(args.grim, directory, "rollback-apps.png")
    before = hashlib.sha256(canvas_bytes(apps)).hexdigest()
    inject(args.inject_script, args.device, (430, 320), (130, 320))
    after = screen(args.grim, directory, "rollback-after-swipe.png")
    if hashlib.sha256(canvas_bytes(after)).hexdigest() != before:
        raise RuntimeError("disabled-gesture swipe changed Apps")
    width, _, _ = apps
    origin, local_height = launcher_bounds(apps)
    footer, bw = origin + local_height - 110, (width - 64) // 3
    inject(args.inject_script, args.device, (40 + 2 * bw + bw // 2, footer + 43))
    next_frame = screen(args.grim, directory, "rollback-next.png")
    if hashlib.sha256(canvas_bytes(next_frame)).hexdigest() == before:
        raise RuntimeError("Next button did not change Apps")
    inject(args.inject_script, args.device, (24 + bw // 2, footer + 43))
    previous_frame = screen(args.grim, directory, "rollback-previous.png")
    if hashlib.sha256(canvas_bytes(previous_frame)).hexdigest() != before:
        raise RuntimeError("Previous button did not restore Apps")
    inject(args.inject_script, args.device, (32 + bw + bw // 2, footer + 43))
    wait_until(lambda: not same_process(launcher_identity), "Back did not close disabled-gesture launcher")
    return {"disabled_gesture_swipe_left_apps_unchanged": True,
            "rollback_env_verified": True, "next_previous_back_buttons_worked": True}


def self_test():
    # Model the verified 56px bar plus a 400px wvkbd reservation.  Geometry
    # identifies two source-coloured cards and rejects a no-window card.
    width, full_height, origin, local_height = PANEL_WIDTH, PANEL_HEIGHT, 56, 776
    rgb = bytearray([33, 32, 33] * width * full_height)
    for y in range(origin, origin + local_height):
        for x in range(width):
            at = (y * width + x) * 3
            rgb[at:at + 3] = bytes((16, 24, 33))
    top, gap, card_height, _ = card_geometry(local_height)
    for row in (0, 1):
        for y in range(origin + top + row * (card_height + gap), origin + top + row * (card_height + gap) + card_height):
            for x in range(24, width - 24):
                at = (y * width + x) * 3
                rgb[at:at + 3] = bytes((36, 73, 90))
    frame = (width, full_height, bytes(rgb))
    assert launcher_bounds(frame) == (56, 776)
    assert overview_has_two_cards(frame)
    at = ((origin + top + card_height + gap + 10) * width + 32) * 3
    rgb[at:at + 3] = bytes((36, 53, 71))
    assert not overview_has_two_cards((width, full_height, bytes(rgb)))
    print("gesture catalog acceptance self-test: ok")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("overview", "focus", "rollback"))
    parser.add_argument("--launcher-pid", type=int, required=True)
    parser.add_argument("--device", default="/dev/input/event1")
    parser.add_argument("--inject-script", default="/run/inject-tap.sh")
    parser.add_argument("--grim", default="grim")
    parser.add_argument("--catalog-command", required=True)
    parser.add_argument("--swaymsg", required=True)
    parser.add_argument("--keyboard-show", default="pkill -USR2 -x wvkbd-mobintl")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test(); return 0
    if not Path(args.inject_script).is_file():
        parser.error("inject script is missing")
    with tempfile.TemporaryDirectory(prefix="k230-gesture-check-") as directory:
        try:
            result = {"overview": phase_overview, "focus": phase_focus, "rollback": phase_rollback}[args.phase](args, directory)
            report = {"result": "pass", "phase": args.phase, "interaction_provenance": "injected-touch",
                      "captured_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(), **result}
        except Exception as error:
            try:
                prior = json.loads(args.report.read_text())
            except (OSError, json.JSONDecodeError):
                prior = {}
            report = {**prior, "result": "fail", "phase": args.phase,
                      "interaction_provenance": "injected-touch", "error": str(error)}
        write_report(args.report, report)
        print(json.dumps(report))
        return 0 if report["result"] == "pass" else 1

if __name__ == "__main__":
    raise SystemExit(main())
