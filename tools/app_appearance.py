#!/usr/bin/env python3
"""Generate bounded installed-app appearance from an acknowledged theme generation.

This never reads commands from a theme checkout or broadcasts to arbitrary PTYs.
The opt-in OSC operation writes only to the caller's own terminal stdout.
"""

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time

from theme_transaction import TransactionError, _pointer


class AppAppearanceError(Exception):
    pass


COLOR = re.compile(r"#[0-9a-fA-F]{6}\Z")
IDENTITY = re.compile(r"[0-9a-f]{24}\Z")
MAX_REPORT = 64 * 1024
ANSI_FALLBACK = ("background", "red", "green", "yellow", "blue", "magenta", "cyan", "foreground",
                 "muted", "bright_red", "bright_green", "bright_yellow", "bright_blue",
                 "bright_magenta", "bright_cyan", "bright_foreground")
OSC = ((10, "foreground"), (11, "background"), (12, "cursor"),
       (17, "selection_background"), (19, "selection_foreground"))


def palette(generation: Path) -> dict[str, str]:
    if not IDENTITY.fullmatch(generation.name):
        raise AppAppearanceError("invalid generation identity")
    source = generation / "report.json"
    if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_REPORT:
        raise AppAppearanceError("missing or oversized generation report")
    report = json.loads(source.read_bytes())
    if not isinstance(report, dict) or report.get("generation") != generation.name:
        raise AppAppearanceError("generation report identity mismatch")
    colors = report.get("palette")
    if not isinstance(colors, dict):
        raise AppAppearanceError("generation has no resolved palette")
    # The pinned fallback generation is intentionally a palette/icon subset;
    # prepared user generations already contain the upstream resolved aliases.
    colors = colors | {"cursor": colors.get("cursor", colors.get("foreground")),
                       "selection_background": colors.get("selection_background", colors.get("selection")),
                       "selection_foreground": colors.get("selection_foreground", colors.get("foreground"))}
    required = set(ANSI_FALLBACK + ("cursor", "selection_background", "selection_foreground"))
    result = {}
    for name in required | {f"color{i}" for i in range(16)}:
        fallback = ANSI_FALLBACK[int(name[5:])] if name.startswith("color") else None
        value = colors.get(name, colors.get(fallback)) if fallback else colors.get(name)
        if not isinstance(value, str) or not COLOR.fullmatch(value):
            raise AppAppearanceError(f"invalid resolved color: {name}")
        result[name] = value.lower()
    return result


def foot_config(colors: dict[str, str], *, monitor: bool) -> str:
    """Emit only trusted Foot appearance keys plus the repo's portrait defaults."""
    lines = ["[main]", "font=DejaVu Sans Mono:size=15"]
    if monitor:
        lines += ["title=Monitor", "locked-title=yes", "app-id=k230-monitor"]
    else:
        lines += ["app-id=k230-terminal", "login-shell=yes"]
    for section in ("colors-dark", "colors-light"):
        lines += ["", f"[{section}]",
                  f"foreground={colors['foreground'][1:]}",
                  f"background={colors['background'][1:]}",
                  f"selection-foreground={colors['selection_foreground'][1:]}",
                  f"selection-background={colors['selection_background'][1:]}",
                  f"cursor={colors['background'][1:]} {colors['cursor'][1:]}"]
        lines += [f"regular{i}={colors[f'color{i}'][1:]}" for i in range(8)]
        lines += [f"bright{i}={colors[f'color{i+8}'][1:]}" for i in range(8)]
    return "\n".join(lines) + "\n"


def osc_sequences(colors: dict[str, str]) -> bytes:
    """Mirror the pinned upstream OSC key/order contract, with validated colors."""
    parts = [f"\x1b]{code};{colors[name]}\x07" for code, name in OSC]
    parts += [f"\x1b]4;{i};{colors[f'color{i}']}\x07" for i in range(16)]
    return "".join(parts).encode("ascii")


def prepare(generation: Path, state_root: Path) -> Path:
    root = state_root.resolve(strict=True)
    cache = (root / "generations").resolve(strict=True)
    generation = generation.resolve(strict=True)
    if not generation.is_relative_to(cache):
        raise AppAppearanceError("generation is outside theme cache")
    colors = palette(generation)
    identity = hashlib.sha256((generation.name + "\n" + json.dumps(colors, sort_keys=True)
                               + Path(__file__).read_text()).encode()).hexdigest()[:24]
    parent = root / "app-appearance"
    if parent.is_symlink():
        raise AppAppearanceError("foreign app appearance directory")
    parent.mkdir(mode=0o700, exist_ok=True)
    target_root = parent / "generations"
    if target_root.is_symlink():
        raise AppAppearanceError("foreign app appearance generations")
    target_root.mkdir(mode=0o700, exist_ok=True)
    target = target_root / identity
    if target.exists():
        if target.is_symlink() or not target.is_dir():
            raise AppAppearanceError("foreign app appearance generation")
        for name, monitor in (("terminal-foot.ini", False), ("monitor-foot.ini", True)):
            file = target / name
            if file.is_symlink() or not file.is_file() or file.read_text() != foot_config(colors, monitor=monitor):
                raise AppAppearanceError("cached app appearance changed")
        return target
    with tempfile.TemporaryDirectory(prefix=".prepare-", dir=target_root) as scratch:
        work = Path(scratch)
        for name, monitor in (("terminal-foot.ini", False), ("monitor-foot.ini", True)):
            (work / name).write_text(foot_config(colors, monitor=monitor))
        coverage = {
            "generation": generation.name,
            "applied": ["Foot: generated terminal/monitor configs for new windows",
                        "Foot: opt-in OSC for caller's current terminal"],
            "inherited": ["htop", "nano", "nnn"],
            "limited": ["mpv: video surface does not consume terminal colors",
                        "Help: shell client uses shared shell tokens, not a separate app adapter",
                        "wvkbd keyboard: separate shell-surface integration pending",
                        "existing Foot windows: no automatic PTY broadcast"],
            "withheld": ["theme foot.ini executable settings"]}
        (work / "coverage.json").write_text(json.dumps(coverage, indent=2, sort_keys=True) + "\n")
        for entry in work.iterdir():
            entry.chmod(0o600)
        try:
            os.rename(work, target)
        except FileExistsError:
            pass
    return target


@contextmanager
def activation_lock(root: Path, timeout: float):
    fd = os.open(root / ".activation.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as error:
                if time.monotonic() >= deadline:
                    raise AppAppearanceError("activation lock timed out") from error
                time.sleep(min(0.01, max(0, deadline - time.monotonic())))
        yield
    finally:
        os.close(fd)


def sync(state_root: Path, *, lock_timeout: float = 2.0) -> Path:
    """Update future-launch config only after caller has completed shell ACK."""
    root = state_root.resolve(strict=True)
    with activation_lock(root, lock_timeout):
        current = _pointer(root)
        if current is None:
            raise AppAppearanceError("no acknowledged active generation")
        target = prepare(current, root)
        parent = root / "app-appearance"
        link = parent / "active"
        if link.is_symlink():
            raw = Path(os.readlink(link))
            resolved = (raw if raw.is_absolute() else parent / raw).resolve(strict=False)
            if not resolved.is_relative_to((parent / "generations").resolve(strict=True)):
                raise AppAppearanceError("foreign app appearance pointer")
        elif os.path.lexists(link):
            raise AppAppearanceError("foreign app appearance pointer")
        with tempfile.TemporaryDirectory(prefix=".link-", dir=parent) as scratch:
            candidate = Path(scratch) / "active"
            candidate.symlink_to(target)
            os.replace(candidate, link)
        directory = os.open(parent, os.O_DIRECTORY | os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        return target


def emit_current(state_root: Path, stream, *, lock_timeout: float = 2.0) -> None:
    """Serialize selection and OSC flush with shell generation publication."""
    root = state_root.resolve(strict=True)
    with activation_lock(root, lock_timeout):
        current = _pointer(root)
        if current is None:
            raise AppAppearanceError("no acknowledged active generation")
        stream.write(osc_sequences(palette(current)))
        stream.flush()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "sync", "osc-current"))
    parser.add_argument("--state-root", type=Path, default=Path.home() / ".local/state/omarchy/current")
    parser.add_argument("--generation", type=Path)
    args = parser.parse_args()
    if args.operation == "prepare":
        if args.generation is None:
            parser.error("prepare requires --generation")
        print(prepare(args.generation, args.state_root))
    elif args.operation == "sync":
        print(sync(args.state_root))
    else:
        if args.generation is not None:
            parser.error("osc-current uses the acknowledged active generation")
        if not sys.stdout.isatty() or os.environ.get("TERM", "").split("-", 1)[0] != "foot":
            raise AppAppearanceError("OSC requires an explicitly invoked Foot terminal session")
        emit_current(args.state_root, sys.stdout.buffer)


if __name__ == "__main__":
    try:
        main()
    except (AppAppearanceError, TransactionError, OSError, ValueError) as error:
        print(f"k230-app-appearance: {error}", file=sys.stderr)
        sys.exit(1)
