#!/usr/bin/env python3
"""Run one app inside Foot while its own terminal follows theme colors.

The short-lived follower inherits this terminal's stdout. It does not discover
or open another PTY, signal another process, or replace the app's foreground
program. A pidfd bounds its lifetime to the exec'd app process.
"""

import argparse
import os
from pathlib import Path
import select
import sys

from app_appearance import AppAppearanceError, activation_lock, osc_sequences, palette
from theme_transaction import TransactionError, _pointer


def observe(state_root: Path, default_generation: Path, last: str | None, stream) -> str | None:
    """Publish one generation change under the coordinator's activation lock."""
    with activation_lock(state_root, 0.25):
        generation = _pointer(state_root) or default_generation
        identity = str(generation.resolve(strict=True))
        if identity != last:
            stream.write(osc_sequences(palette(generation)))
            stream.flush()
        return identity


def follow(parent_pid: int, state_root: Path, default_generation: Path,
           interval: float, stream) -> None:
    pidfd = os.pidfd_open(parent_pid)
    try:
        watcher = select.poll()
        watcher.register(pidfd, select.POLLIN | select.POLLHUP)
        last = None
        while not watcher.poll(0):
            try:
                last = observe(state_root, default_generation, last, stream)
            except (AppAppearanceError, OSError, ValueError, TransactionError):
                # A malformed/missing generation or in-flight activation does
                # not terminate the app. Retry at the next bounded interval.
                pass
            watcher.poll(int(interval * 1000))
    finally:
        os.close(pidfd)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--default-generation", type=Path, required=True)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command and args.command[0] == "--" else args.command
    if not command or not 0.25 <= args.interval <= 5.0:
        parser.error("supply -- COMMAND and an interval from 0.25 to 5 seconds")
    if not sys.stdout.isatty() or os.environ.get("TERM", "").split("-", 1)[0] != "foot":
        parser.error("must run inside the Foot terminal being themed")
    if not args.default_generation.is_absolute():
        parser.error("default generation must be an absolute pinned path")
    # Validate the only external palette before creating a follower.
    default_generation = args.default_generation.resolve(strict=True)
    palette(default_generation)
    if args.state_root.is_symlink():
        parser.error("foreign theme state root")
    args.state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    state_root = args.state_root.resolve(strict=True)
    try:
        child = os.fork()
    except OSError:
        print("k230-foot-session: color follower unavailable", file=sys.stderr)
        child = None
    if child == 0:
        try:
            if os.isatty(0):
                os.close(0)
            follow(os.getppid(), state_root, default_generation,
                   args.interval, sys.stdout.buffer)
        except Exception:
            pass
        os._exit(0)
    try:
        os.execvpe(command[0], command, os.environ)
    except OSError as error:
        print(f"k230-foot-session: command could not start: {error.strerror}", file=sys.stderr)
        return 127


if __name__ == "__main__":
    sys.exit(main())
