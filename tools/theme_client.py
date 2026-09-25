#!/usr/bin/env python3
"""Argv-compatible front end for `theme_catalog.py`, fast when the helper
daemon (`tools/theme_helperd.py`) is up, correct when it is not.

This binary is what `k230-theme`/`omarchy-theme-set` actually exec on the
board (see `nix/handheld-theme-command.nix`). On the common path -- the
daemon reachable at `--helper-socket` -- it does no more than argument
parsing with the stdlib `argparse` and a JSON round trip over that socket:
it deliberately does **not** import `theme_catalog` (and so not
`theme_activate`/`theme_transaction`/`theme_preferences`/
`keyboard_appearance` either) unless it actually needs that module's own
parser/logic, because board evidence
(`docs/evidence/omarchy-themes/background-decode-cache-qemu/README.md`)
measured that import chain, not bare interpreter start-up, as most of the
~1.2 s a `k230-theme` call cost on the K230's slower core -- importing it
here on every call regardless of the daemon would have defeated the whole
point of keeping a warm process elsewhere. `--tools`/`--builtins`/
`--state-root`/the sockets/etc are therefore not sent in the request: the
already-running daemon has its own authoritative copies from its own
startup flags (`nix/shell.nix`'s `theme-helper.service`), the same way a
caller of any other long-lived shell service does not re-supply that
service's own configuration on every call.

If the socket is missing, refused, or does not answer within
`--helper-timeout-s`, or if this module cannot confidently reduce the
request to the daemon's minimal shape, this falls back to importing
`theme_catalog` and calling `handle()` directly in this same process (not a
subprocess -- no Python start-up is paid twice), which is exactly what ran
before this daemon existed. A stale or partially-started daemon can
therefore never make theme switching worse than it is today, only
sometimes not faster.

Board evidence (coordinator, 2026-09-24, `theme-helper.service` reachable
and owned correctly) showed the *opposite*: `preview`/`activate` measured
3.95-4.26 s each -- worse than the pre-daemon 2.8-3.5 s baseline. The cause
was this file, not the daemon: `DEFAULT_TIMEOUT_S` was 0.3 s, chosen back
when the only known cost on this path was Python start-up (which the
daemon already eliminates in well under 0.3 s); it did not anticipate
`theme_activate.prepare()`'s own real cost (now fixed separately -- see
`theme_activate.py`'s cache-hit fast path -- but even a legitimate *first*
preparation of a theme can take a few seconds for its external
`omarchy-theme-*` helper invocations). A `preview`/`activate` heavier than
0.3 s therefore had this client abandon an already-in-flight, working
daemon reply mid-flight and fall back to the *full* in-process path --
paying both the wasted 0.3 s and the entire ~1.2 s import chain *and*
`prepare()`'s own cost a second time. `DEFAULT_TIMEOUT_S` must stay
comfortably above the slowest legitimate daemon reply, not near the
fastest one; see its own comment for the value chosen and why.
"""
import argparse
import json
import socket
import sys
from pathlib import Path

import theme_timing

DEFAULT_SOCKET = Path("/run/shell/theme-helper.sock")
# Comfortably above every board number measured for this path so far --
# including the *slow*, not-yet-cache-hit ones (the 2026-09-24 board
# evidence's worst case, before this file's own fix, was 4.26 s) -- with
# more than 2x headroom for board-to-board variability, while still
# failing over to the fallback path in a bounded, human-noticeable time if
# the daemon is genuinely wedged (which `theme_helperd.py`'s own per-request
# exception handling and bounded `theme_transaction.EXCHANGE_TIMEOUT_S`
# network exchanges make rare, not routine).
DEFAULT_TIMEOUT_S = 10.0


def build_light_parser() -> argparse.ArgumentParser:
    """A parser accepting the same flags `theme_catalog.build_parser()`
    does, but that never imports it: only used to recognise the request
    shape for the fast daemon path. Any flag whose *value* actually matters
    once the daemon is reached (there are none -- see module docstring) or
    any parse failure sends this straight to the full fallback parser
    instead of trying to emulate its exact error text here.
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--tools", type=Path)
    parser.add_argument("--wallpaper-cache-tool", type=Path)
    parser.add_argument("--user-themes", type=Path)
    parser.add_argument("--builtins", type=Path)
    parser.add_argument("--state-root", type=Path)
    parser.add_argument("--socket", type=Path)
    parser.add_argument("--rust-socket", type=Path)
    parser.add_argument("--deck-socket", type=Path)
    parser.add_argument("--keyboard-runtime-dir", type=Path)
    parser.add_argument("--pkill")
    parser.add_argument("--helper-socket", type=Path, default=DEFAULT_SOCKET)
    parser.add_argument("--helper-timeout-s", type=float, default=DEFAULT_TIMEOUT_S)
    actions = parser.add_subparsers(dest="action")
    listing = actions.add_parser("list", add_help=False)
    listing.add_argument("--json", action="store_true")
    for action in ("preview", "activate"):
        command = actions.add_parser(action, add_help=False)
        command.add_argument("id")
        command.add_argument("--json", action="store_true")
        command.add_argument("--background")
        if action == "activate":
            command.add_argument("--expected-generation")
    return parser


def as_request(args: argparse.Namespace) -> dict:
    request: dict = {"action": args.action}
    if args.action != "list":
        request["id"] = args.id
        request["background"] = args.background
        if args.action == "activate":
            request["expected_generation"] = args.expected_generation
    return request


def try_helper(request: dict, helper_socket: Path, timeout_s: float) -> tuple[dict, int] | None:
    """Returns `(result, exit_code)` on a clean answer from the daemon, or
    `None` on anything that should fall back to the full path -- never
    raises. Always logs which of those happened and how long it took (the
    coordinator's own question: "is the client actually served by the
    daemon, or is it falling back?"), distinguishing a real answer from a
    timeout/refusal/malformed-reply so a board run is self-diagnosing."""
    stopwatch = theme_timing.Stopwatch()
    reason = "ok"
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(timeout_s)
            connection.connect(str(helper_socket))
            connection.sendall(json.dumps(request).encode() + b"\n")
            connection.shutdown(socket.SHUT_WR)
            buffer = b""
            while b"\n" not in buffer:
                chunk = connection.recv(65536)
                if not chunk:
                    break
                buffer += chunk
            line, _, _rest = buffer.partition(b"\n")
            if not line:
                reason = "empty-reply"
                return None
            payload = json.loads(line)
            return payload["result"], int(payload["exit_code"])
    except socket.timeout:
        reason = f"timeout>{timeout_s}s"
        return None
    except (OSError, json.JSONDecodeError, KeyError, ValueError, TypeError) as error:
        reason = f"{type(error).__name__}: {error}"[:80]
        return None
    finally:
        stopwatch.lap("socket_round_trip")
        theme_timing.log("client", request.get("action", "-"), stopwatch,
                         id=request.get("id", "-"), path="daemon", outcome=reason)


def fallback(argv: list[str]) -> int:
    """The unmodified behaviour: import `theme_catalog` and run its parser
    and `handle()` directly in this process, exactly as a bare
    `python3 theme_catalog.py <argv>` would (still no subprocess -- no
    Python start-up is paid twice)."""
    stopwatch = theme_timing.Stopwatch()
    import theme_catalog
    stopwatch.lap("import_theme_catalog")

    parser = theme_catalog.build_parser()
    args = parser.parse_args(argv)
    if (args.rust_socket is None) != (args.deck_socket is None):
        parser.error("--rust-socket and --deck-socket must be supplied together")
    result, code = theme_catalog.handle(args)
    stopwatch.lap("handle")
    # `handle()` already logged its own THEME_TIMING line; this one marks
    # that the *fallback* path (full import chain, in this same process)
    # was the one actually taken, and how much of the total was the import
    # itself versus `handle()`'s own (already itemised) work.
    theme_timing.log("client", args.action, stopwatch, id=getattr(args, "id", "-"), path="fallback")
    print(json.dumps(result, sort_keys=True), file=sys.stderr if code else sys.stdout)
    return code


def main(argv=None) -> int:
    raw_argv = sys.argv[1:] if argv is None else list(argv)
    try:
        light_args, unrecognized = build_light_parser().parse_known_args(raw_argv)
    except SystemExit:
        light_args = None
        unrecognized = None
    if light_args is None or unrecognized or light_args.action is None:
        # Cannot confidently reduce this to the daemon's minimal request
        # shape (unknown flag, missing subcommand, etc) -- let the real
        # parser produce the real, exact error instead of guessing here.
        theme_timing.log("client", "-", path="fallback", reason="unrecognised-argv")
        return fallback(raw_argv)
    if light_args.action != "list" and getattr(light_args, "id", None) is None:
        theme_timing.log("client", light_args.action, path="fallback", reason="no-id")
        return fallback(raw_argv)
    answer = try_helper(as_request(light_args), light_args.helper_socket, light_args.helper_timeout_s)
    if answer is None:
        # Strip the two client-only flags before falling back, so
        # theme_catalog's own parser (which does not know them) still sees
        # a clean argv.
        stripped = []
        skip_next = False
        for token in raw_argv:
            if skip_next:
                skip_next = False
                continue
            if token in ("--helper-socket", "--helper-timeout-s"):
                skip_next = True
                continue
            stripped.append(token)
        return fallback(stripped)
    result, code = answer
    print(json.dumps(result, sort_keys=True), file=sys.stderr if code else sys.stdout)
    return code


if __name__ == "__main__":
    sys.exit(main())
