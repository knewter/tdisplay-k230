#!/usr/bin/env python3
"""Persistent theme-catalog helper: keep Python warm across theme swaps.

Board evidence (`docs/evidence/omarchy-themes/background-decode-cache-qemu/README.md`)
measured about 1.2 s of Python interpreter start-up and import cost on every
`k230-theme` invocation on the K230 -- and a chooser Apply calls it twice
(`preview` then `activate`), so roughly 2.4 s of a 2.8-3.5 s swap was pure
process start-up, not theme work. This daemon does the imports and the
`discover()` theme-source walk once, then serves every later `preview`/
`activate`/`list` request over a private Unix socket by calling
`tools/theme_catalog.py`'s own `build_parser()`/`handle()` -- the *exact*
same code path a fresh CLI invocation takes, so there is no second protocol
to drift from the one already reviewed, tested, and evidenced.

This changes *when* Python interpreter cost is paid, never the two-phase
transaction it drives: every request still goes through
`theme_transaction.activate_generation`'s prepare/commit/rollback exchange
with the same receivers, so a crash mid-request leaves the same recoverable
state a crash mid-`theme_catalog.py` would. A request that raises is caught
and reported like any other `theme_catalog` error; it never brings the
daemon down, so one bad theme cannot wedge every later swap (`Restart=
on-failure` in the systemd unit is the remaining safety net, not the
primary one).

`tools/theme_client.py` is the small, argv-compatible front end: it tries
this socket first and falls back to spawning `theme_catalog.py` directly
(today's behaviour, unchanged) if the daemon is not reachable, so a board
that has not yet picked up this daemon -- or one where it crashed and is
mid-restart -- still switches themes, just without the speed-up.
"""
import argparse
import json
import os
import selectors
import signal
import socket
import struct
import sys
import threading
from pathlib import Path

import theme_catalog
import theme_timing

MAX_REQUEST = 8192
PEER_DEADLINE_S = 2.0


def fixed_flags_argv(fixed: dict) -> list[str]:
    """Serialize this daemon's own startup flags back into the argv form
    `theme_catalog.build_parser()` expects, so every request is parsed by
    that exact parser -- not a hand-rolled re-implementation of its
    defaults and validation."""
    argv: list[str] = []
    for flag, value in fixed.items():
        if value is None:
            continue
        argv += [flag, str(value)]
    return argv


def request_argv(fixed_argv: list[str], request: dict) -> list[str]:
    action = request.get("action")
    if action not in ("list", "preview", "activate"):
        raise ValueError("invalid action")
    argv = list(fixed_argv) + [action]
    if action != "list":
        theme_id = request.get("id")
        if not isinstance(theme_id, str) or not theme_id:
            raise ValueError("missing id")
        argv.append(theme_id)
        background = request.get("background")
        if background is not None:
            if not isinstance(background, str):
                raise ValueError("invalid background")
            argv += ["--background", background]
        if action == "activate":
            expected = request.get("expected_generation")
            if not isinstance(expected, str) or not expected:
                raise ValueError("missing expected_generation")
            argv += ["--expected-generation", expected]
    return argv


def peer_uid(connection: socket.socket) -> int | None:
    try:
        credentials = connection.getsockopt(
            socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")
        )
    except OSError:
        return None
    _pid, uid, _gid = struct.unpack("3i", credentials)
    return uid


class Helperd:
    def __init__(self, fixed: dict, listen: Path):
        self.fixed_argv = fixed_flags_argv(fixed)
        self.listen = listen
        self.lock = threading.Lock()
        # Board evidence (2026-09-25): a request's own "parse" phase cost
        # 65 ms -- on this daemon's slow single core, building a fresh
        # `argparse.ArgumentParser` (three subcommands, ~15 flags) turned
        # out to be real, repeated cost, not bare JSON decoding. Built once
        # per `argparse.ArgumentParser`'s own contract that `parse_args()`
        # never mutates the parser itself, so reusing one instance across
        # every request -- exactly like reusing any other stateless,
        # thread-safe-under-this-daemon's-own-single-request-at-a-time-lock
        # object -- is safe and behaves identically to a fresh one each time.
        self.parser = theme_catalog.build_parser()

    def handle_line(self, line: bytes) -> tuple[dict, int]:
        stopwatch = theme_timing.Stopwatch()
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("request must be a JSON object")
            argv = request_argv(self.fixed_argv, request)
        except (json.JSONDecodeError, ValueError) as error:
            theme_timing.log("helperd", "malformed", stopwatch, error=str(error)[:80])
            return {"schema": 1, "error": f"malformed request: {error}", "activated": False}, 1
        action = argv[len(self.fixed_argv)] if len(argv) > len(self.fixed_argv) else "-"
        try:
            args = self.parser.parse_args(argv)
        except SystemExit:
            theme_timing.log("helperd", action, stopwatch, outcome="invalid-arguments")
            return {"schema": 1, "error": "invalid request arguments", "activated": False}, 1
        if (args.rust_socket is None) != (args.deck_socket is None):
            theme_timing.log("helperd", action, stopwatch, outcome="socket-flags-mismatch")
            return {"schema": 1, "error": "--rust-socket and --deck-socket must be supplied together",
                    "activated": False}, 1
        stopwatch.lap("parse")
        # theme_catalog's own functions never raise anything this daemon has
        # not already seen reported as a normal `{"error": ...}` result from
        # a one-shot CLI call -- but this loop must survive an unexpected
        # exception too, or one bad request would take down every later
        # swap until systemd restarts it.
        with self.lock:  # theme_catalog's module-level state is not designed for concurrent calls
            stopwatch.lap("lock_wait")
            try:
                result, code = theme_catalog.handle(args)
            except Exception as error:  # noqa: BLE001 - see docstring: never let this kill the daemon
                stopwatch.lap("handle")
                theme_timing.log("helperd", action, stopwatch,
                                 id=getattr(args, "id", "-"), outcome="internal-error")
                return {"schema": 1, "error": f"helper internal error: {error}",
                        "activated": False}, 1
        stopwatch.lap("handle")
        # `handle()` already logged its own per-phase THEME_TIMING line
        # (component "handle"); this one is the daemon-specific envelope
        # around it -- request parsing and time actually spent waiting for
        # `self.lock` (the coordinator's own question: "does the daemon
        # hold a lock ... on every call") -- so a slow request is
        # attributable to one or the other from the journal alone.
        theme_timing.log("helperd", action, stopwatch, id=getattr(args, "id", "-"),
                         outcome="ok" if code == 0 else "error")
        return result, code

    def serve_one(self, connection: socket.socket) -> None:
        connection.settimeout(PEER_DEADLINE_S)
        try:
            if peer_uid(connection) not in (None, os.geteuid()):
                return
            buffer = b""
            while b"\n" not in buffer:
                chunk = connection.recv(MAX_REQUEST + 1)
                if not chunk:
                    return
                buffer += chunk
                if len(buffer) > MAX_REQUEST:
                    connection.sendall(json.dumps(
                        {"schema": 1, "error": "request exceeds bound", "activated": False}
                    ).encode() + b"\n")
                    return
            line, _, _rest = buffer.partition(b"\n")
            result, code = self.handle_line(line)
            payload = json.dumps({"result": result, "exit_code": code}).encode() + b"\n"
            connection.sendall(payload)
        except OSError:
            pass
        finally:
            connection.close()

    def serve_forever(self, stop: threading.Event | None = None) -> None:
        """Serve connections until SIGTERM/SIGINT, or until `stop` is set.

        `stop` lets a test run this in a background thread of the *same*
        process (so `mock.patch.object(theme_catalog, ...)` in that test
        reaches the daemon's calls) and shut it down deterministically;
        `signal.signal` only works from the main thread, so signal-based
        shutdown is used only when the caller (the real standalone daemon,
        via `main()`) did not pass an explicit `stop` event.
        """
        runtime = self.listen.parent
        runtime.mkdir(parents=True, exist_ok=True)
        if self.listen.exists():
            self.listen.unlink()
        old_umask = os.umask(0o077)
        try:
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            listener.bind(str(self.listen))
        finally:
            os.umask(old_umask)
        os.chmod(self.listen, 0o600)
        listener.listen(4)
        selector = selectors.DefaultSelector()
        selector.register(listener, selectors.EVENT_READ)
        owns_stop = stop is None
        if owns_stop:
            stop = threading.Event()

            def handle_signal(_signum, _frame):
                stop.set()

            signal.signal(signal.SIGTERM, handle_signal)
            signal.signal(signal.SIGINT, handle_signal)
        try:
            while not stop.is_set():
                for _key, _events in selector.select(timeout=0.2):
                    try:
                        connection, _address = listener.accept()
                    except OSError:
                        continue
                    # Theme swaps are inherently one-at-a-time user actions
                    # (one active chooser); a thread per connection is
                    # simplicity, not a concurrency design, and `self.lock`
                    # still serializes the actual theme_catalog work.
                    threading.Thread(target=self.serve_one, args=(connection,), daemon=True).start()
        finally:
            listener.close()
            if self.listen.exists():
                self.listen.unlink()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listen", type=Path, default=Path("/run/shell/theme-helper.sock"))
    parser.add_argument("--tools", type=Path, default=theme_catalog.activation.HOST_TOOLS)
    parser.add_argument("--wallpaper-cache-tool", type=Path)
    parser.add_argument("--user-themes", type=Path, default=Path.home() / ".config/omarchy/themes")
    parser.add_argument("--builtins", type=Path)
    parser.add_argument("--state-root", type=Path, default=Path.home() / ".local/state/omarchy/current")
    parser.add_argument("--socket", type=Path, default=Path("/run/shell/appearance.sock"))
    parser.add_argument("--rust-socket", type=Path)
    parser.add_argument("--deck-socket", type=Path)
    parser.add_argument("--keyboard-runtime-dir", type=Path, default=Path("/run/shell"))
    parser.add_argument("--pkill", default="pkill")
    args = parser.parse_args(argv)
    if (args.rust_socket is None) != (args.deck_socket is None):
        parser.error("--rust-socket and --deck-socket must be supplied together")
    fixed = {
        "--tools": args.tools,
        "--wallpaper-cache-tool": args.wallpaper_cache_tool,
        "--user-themes": args.user_themes,
        "--builtins": args.builtins,
        "--state-root": args.state_root,
        "--socket": args.socket,
        "--rust-socket": args.rust_socket,
        "--deck-socket": args.deck_socket,
        "--keyboard-runtime-dir": args.keyboard_runtime_dir,
        "--pkill": args.pkill,
    }
    Helperd(fixed, args.listen).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
