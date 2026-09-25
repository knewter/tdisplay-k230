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
"""
import argparse
import json
import socket
import sys
from pathlib import Path

DEFAULT_SOCKET = Path("/run/shell/theme-helper.sock")
DEFAULT_TIMEOUT_S = 0.3


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
    raises."""
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
                return None
            payload = json.loads(line)
            return payload["result"], int(payload["exit_code"])
    except (OSError, json.JSONDecodeError, KeyError, ValueError, TypeError):
        return None


def fallback(argv: list[str]) -> int:
    """The unmodified behaviour: import `theme_catalog` and run its parser
    and `handle()` directly in this process, exactly as a bare
    `python3 theme_catalog.py <argv>` would (still no subprocess -- one
    Python start-up total, not two)."""
    import theme_catalog

    parser = theme_catalog.build_parser()
    args = parser.parse_args(argv)
    if (args.rust_socket is None) != (args.deck_socket is None):
        parser.error("--rust-socket and --deck-socket must be supplied together")
    result, code = theme_catalog.handle(args)
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
        return fallback(raw_argv)
    if light_args.action != "list" and getattr(light_args, "id", None) is None:
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
