#!/usr/bin/env python3
"""Shared per-phase timing log for the theme-swap path.

Board evidence (the coordinator's own run, 2026-09-24 against `master`
`766yhn3l...`) showed `theme-helper.service` running and reachable, but
`preview`/`activate` of an *already-prepared* theme still took 3.95-4.26 s
each, with `journalctl -u theme-helper` showing "No entries" -- because
nothing in this path had ever logged anything, a board run could not be
self-diagnosing. Every module on this path (`theme_client.py`,
`theme_helperd.py`, `theme_catalog.py`, `theme_activate.py`,
`theme_transaction.py`) calls into this module to emit one grep-friendly
`THEME_TIMING` line per phase to stderr -- captured by journald for the
daemon (a systemd service) and printed directly for a client run from an
interactive shell (exactly how the coordinator's own commands already
capture output).

This deliberately logs via `syslog`, not `print(..., file=sys.stderr)`:
`theme_catalog.py`/`theme_client.py` print exactly one JSON value to stdout
(success) or stderr (failure) as their whole documented contract --
`nix/rust-shell-client/src/theme_catalog.rs`'s `command_error()` parses that
stderr byte-for-byte as JSON on a nonzero exit, so any other text sharing
that stream (from this module, called deep inside `prepare()`/`exchange()`
in the very same process, in both the daemon and the bare-CLI/fallback
cases) would corrupt it and turn a real error message into a generic
"theme command failed". `syslog` reaches the journal (journald captures the
syslog socket by default, tagged with the emitting process's own systemd
unit when it has one -- `journalctl -u theme-helper` for the daemon, or a
plain `journalctl` for a bare CLI run) without ever touching stdout/stderr.

This module never raises: a missing or unreachable `/dev/log` (e.g. a
sandboxed test environment) is swallowed, exactly like a failed
`background.cache` write elsewhere in this codebase -- logging can only
ever be missing, never something that changes what `prepare()`/`exchange()`/
`handle()` compute or return.
"""
import syslog
import time

_opened = False


def _ensure_open() -> None:
    global _opened
    if not _opened:
        syslog.openlog(ident="k230-theme-timing", logoption=syslog.LOG_PID)
        _opened = True


def now_ms() -> float:
    return time.monotonic() * 1000.0


class Stopwatch:
    """Accumulates named phase durations (ms) from sequential `lap()` calls
    for one flat `THEME_TIMING` line. Not thread-safe; one per request."""

    def __init__(self):
        self._start = now_ms()
        self._last = self._start
        self.phases: list[tuple[str, float]] = []

    def lap(self, name: str) -> float:
        """Record `name` as the phase since the last `lap()` (or since
        construction, for the first). Returns that phase's own ms."""
        current = now_ms()
        elapsed = current - self._last
        self._last = current
        self.phases.append((name, elapsed))
        return elapsed

    def total_ms(self) -> float:
        return now_ms() - self._start


def log(component: str, action: str, stopwatch: Stopwatch | None = None, **extra) -> None:
    """Emit one `THEME_TIMING <component> <action> phase=Xms ... key=value
    ...` line to syslog/journal (see module doc for why not stdout/stderr).
    `extra` values are stringified as-is (ids, hit/miss markers, booleans)
    after every timed phase and the stopwatch's own total. Never raises."""
    try:
        parts = []
        if stopwatch is not None:
            parts.extend(f"{name}={ms:.1f}ms" for name, ms in stopwatch.phases)
            parts.append(f"total={stopwatch.total_ms():.1f}ms")
        parts.extend(f"{key}={value}" for key, value in extra.items())
        _ensure_open()
        syslog.syslog(syslog.LOG_INFO,
                      f"THEME_TIMING {component} {action} " + " ".join(parts))
    except Exception:  # noqa: BLE001 - logging must never break the theme-swap path
        pass
