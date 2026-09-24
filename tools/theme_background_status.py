"""Read private wallpaper playback counters without exporting theme asset paths."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat


IDENTITY = re.compile(r"[a-f0-9]{24}\Z")
MAX_STATUS = 4096
MAX_REPORT = 256 * 1024
COUNTERS = ("frames_decoded", "frames_submitted", "frame_callbacks")
TIMES = ("last_decoded_monotonic_ms", "last_submitted_monotonic_ms",
         "last_callback_monotonic_ms")


def expected_fingerprint(generation: str, report_path: Path) -> str:
    if not IDENTITY.fullmatch(generation):
        raise ValueError("invalid wallpaper generation")
    descriptor = os.open(report_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_REPORT:
            raise ValueError("wallpaper report exceeds bound")
        report = json.loads(os.read(descriptor, MAX_REPORT + 1))
    finally:
        os.close(descriptor)
    if report.get("generation") != generation:
        raise ValueError("wallpaper report identity or bound mismatch")
    relative = report.get("selected_background")
    backgrounds = report.get("backgrounds")
    if (not isinstance(relative, str) or not relative.startswith("backgrounds/")
            or "/" in relative[len("backgrounds/"):] or ".." in Path(relative).parts
            or not isinstance(backgrounds, list) or relative not in backgrounds):
        raise ValueError("wallpaper report lacks selected staged background")
    return hashlib.sha256(f"{generation}\n{relative}".encode()).hexdigest()[:24]


def read_status(path: Path, generation: str, fingerprint: str) -> dict:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.geteuid()
                or metadata.st_mode & 0o077 or metadata.st_size > MAX_STATUS):
            raise ValueError("wallpaper status is not a bounded private regular file")
        raw = os.read(descriptor, MAX_STATUS + 1)
        if len(raw) > MAX_STATUS:
            raise ValueError("wallpaper status exceeds bound")
    finally:
        os.close(descriptor)
    value = json.loads(raw)
    if (not isinstance(value, dict) or value.get("schema") != 1
            or value.get("generation") != generation
            or value.get("background_fingerprint") != fingerprint):
        raise ValueError("wallpaper status identity mismatch")
    if value.get("state") != "playing":
        raise ValueError("wallpaper video is not playing")
    pid = value.get("decoder_pid")
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        raise ValueError("wallpaper decoder PID unavailable")
    for field in COUNTERS:
        count = value.get(field)
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError("invalid wallpaper frame counter")
    for field in TIMES:
        moment = value.get(field)
        if moment is not None and (not isinstance(moment, int) or isinstance(moment, bool) or moment < 0):
            raise ValueError("invalid wallpaper frame timestamp")
    if value.get("error_category") is not None:
        raise ValueError("wallpaper video reported an error")
    return value


def progress(before: dict, after: dict) -> dict:
    if (before["generation"] != after["generation"]
            or before["background_fingerprint"] != after["background_fingerprint"]
            or before["decoder_pid"] != after["decoder_pid"]):
        raise ValueError("wallpaper decoder identity changed during sample")
    delta = {}
    for field in COUNTERS:
        difference = after[field] - before[field]
        if difference < 2:
            raise ValueError("wallpaper frame evidence did not advance twice")
        delta[field] = difference
    for field in TIMES:
        old, new = before[field], after[field]
        if old is None or new is None or new <= old:
            raise ValueError("wallpaper frame timestamp did not advance")
    return delta
