#!/usr/bin/env python3
"""Generate bounded wvkbd start-up colour flags from an acknowledged theme.

wvkbd-mobintl only reads its `--bg/--fg/--fg-sp/--press/--press-sp/--text/
--text-sp` colours as process-start flags (confirmed against the pinned
nixpkgs revision's `wvkbd-mobintl --help`); there is no live-recolor IPC. So a
theme change can only reach the keyboard by restarting the process. This
module never restarts anything as a side effect of import or of `prepare()`:
`restart()` is the one function that signals a process, and it only ever
signals a same-uid `wvkbd-mobintl`, mirroring the existing
`k230-keyboard-gesture-signal` show/hide convention (same-uid SIGUSR1/
SIGUSR2 pkill). It also only signals when the supervised launcher has left a
sentinel proving *something* restarts wvkbd on exit; otherwise a plain
Sway-exec'd keyboard (the non-coherent-shell legacy path) would be killed and
never come back.

Visibility (shown/hidden) is preserved without any post-restart replay race:
the supervised launcher itself reads a small persisted marker
(`$XDG_RUNTIME_DIR/k230-keyboard-visible`, written by
`k230-keyboard-gesture-signal`) and chooses whether to pass `--hidden` at its
next start. This module owns colours and the restart trigger only.
"""

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from app_appearance import AppAppearanceError, activation_lock
from theme_transaction import TransactionError, _pointer


class KeyboardAppearanceError(Exception):
    pass


class KeyboardAppearanceSuperseded(KeyboardAppearanceError):
    pass


IDENTITY = re.compile(r"[0-9a-f]{24}\Z")
COLOR = re.compile(r"#[0-9a-fA-F]{6}\Z")
MAX_REPORT = 64 * 1024

# wvkbd's colour vocabulary in this integration is exactly these seven
# start-up flags, in the order they are written to the args file. Roles are
# chosen to match the card/grip appearance contract already in
# nix/card-shell/adapter.c (canvas=background, card=dark_background,
# selected=lighter_background, text=foreground): the keyboard should read as
# the same surface family, with a distinguishable resting/pressed state for
# special (Shift/Enter/Backspace) keys.
ROLES = (
    ("bg", "background"),
    ("fg", "dark_background"),
    ("fg-sp", "darker_background"),
    ("press", "selection"),
    ("press-sp", "lighter_background"),
    ("text", "foreground"),
    ("text-sp", "bright_foreground"),
)


def colors(generation: Path) -> dict[str, str]:
    """Resolve wvkbd's seven flag values from a generation's palette report."""
    if not IDENTITY.fullmatch(generation.name):
        raise KeyboardAppearanceError("invalid generation identity")
    source = generation / "report.json"
    if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_REPORT:
        raise KeyboardAppearanceError("missing or oversized generation report")
    report = json.loads(source.read_bytes())
    if not isinstance(report, dict) or report.get("generation") != generation.name:
        raise KeyboardAppearanceError("generation report identity mismatch")
    palette = report.get("palette")
    if not isinstance(palette, dict):
        raise KeyboardAppearanceError("generation has no resolved palette")
    result = {}
    for flag, key in ROLES:
        value = palette.get(key)
        if not isinstance(value, str) or not COLOR.fullmatch(value):
            raise KeyboardAppearanceError(f"invalid resolved color: {key}")
        result[flag] = value.lower()
    return result


def args_file(resolved: dict[str, str]) -> str:
    """One CLI token per line, in ROLES order, for a bash `mapfile` reader."""
    lines = []
    for flag, _key in ROLES:
        lines.append(f"--{flag}")
        lines.append(resolved[flag][1:])  # strip '#': wvkbd wants rrggbb[aa]
    return "\n".join(lines) + "\n"


def prepare(generation: Path, state_root: Path) -> Path:
    """Publish an immutable per-generation `wvkbd.args`; never touch the source."""
    root = state_root.resolve(strict=True)
    cache = (root / "generations").resolve(strict=True)
    generation = generation.resolve(strict=True)
    if not generation.is_relative_to(cache):
        raise KeyboardAppearanceError("generation is outside theme cache")
    resolved = colors(generation)
    content = args_file(resolved)
    identity = hashlib.sha256((generation.name + "\n" + content
                               + Path(__file__).read_text()).encode()).hexdigest()[:24]
    parent = root / "keyboard-appearance"
    if parent.is_symlink():
        raise KeyboardAppearanceError("foreign keyboard appearance directory")
    parent.mkdir(mode=0o700, exist_ok=True)
    target_root = parent / "generations"
    if target_root.is_symlink():
        raise KeyboardAppearanceError("foreign keyboard appearance generations")
    target_root.mkdir(mode=0o700, exist_ok=True)
    target = target_root / identity
    if target.exists():
        if target.is_symlink() or not target.is_dir():
            raise KeyboardAppearanceError("foreign keyboard appearance generation")
        existing = target / "wvkbd.args"
        if existing.is_symlink() or not existing.is_file() or existing.read_text() != content:
            raise KeyboardAppearanceError("cached keyboard appearance changed")
        return target
    with tempfile.TemporaryDirectory(prefix=".prepare-", dir=target_root) as scratch:
        work = Path(scratch)
        (work / "wvkbd.args").write_text(content)
        coverage = {
            "generation": generation.name,
            "applied": ["wvkbd: --bg/--fg/--fg-sp/--press/--press-sp/--text/--text-sp "
                        "from the resolved palette"],
            "unavailable": ["wvkbd: colours are read only at process start; a live "
                             "change restarts the supervised keyboard, never an "
                             "unsupervised one"],
        }
        (work / "coverage.json").write_text(json.dumps(coverage, indent=2, sort_keys=True) + "\n")
        for entry in work.iterdir():
            entry.chmod(0o600)
        try:
            os.rename(work, target)
        except FileExistsError:
            pass
    return target


@contextmanager
def _keyboard_activation_lock(root: Path, timeout: float):
    """Same lock file and semantics as app_appearance, under this module's
    own exception type so callers need not import app_appearance."""
    try:
        with activation_lock(root, timeout):
            yield
    except AppAppearanceError as error:
        raise KeyboardAppearanceError(str(error)) from error


def sync(state_root: Path, *, expected_generation: str | None = None,
         lock_timeout: float = 2.0) -> tuple[Path, bool, str]:
    """Publish the active theme's keyboard colours; report whether they changed.

    Returns (keyboard-appearance cache path, changed, theme generation name).
    The cache path's own identity is a private detail: callers report the
    *theme's* generation name, matching how app_appearance's caller reports
    theme_transaction's own `generation.name` rather than app_appearance's
    internal cache identity.
    """
    root = state_root.resolve(strict=True)
    with _keyboard_activation_lock(root, lock_timeout):
        current = _pointer(root)
        if current is None:
            raise KeyboardAppearanceError("no acknowledged active generation")
        if expected_generation is not None and current.name != expected_generation:
            raise KeyboardAppearanceSuperseded("keyboard sync superseded by newer generation")
        target = prepare(current, root)
        parent = root / "keyboard-appearance"
        link = parent / "active"
        previous = None
        if link.is_symlink():
            raw = Path(os.readlink(link))
            resolved = (raw if raw.is_absolute() else parent / raw).resolve(strict=False)
            if not resolved.is_relative_to((parent / "generations").resolve(strict=True)):
                raise KeyboardAppearanceError("foreign keyboard appearance pointer")
            previous = resolved
        elif os.path.lexists(link):
            raise KeyboardAppearanceError("foreign keyboard appearance pointer")
        changed = previous != target
        with tempfile.TemporaryDirectory(prefix=".link-", dir=parent) as scratch:
            candidate = Path(scratch) / "active"
            candidate.symlink_to(target)
            os.replace(candidate, link)
        directory = os.open(parent, os.O_DIRECTORY | os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        return target, changed, current.name


def restart(runtime_dir: Path, *, pkill_path: str = "pkill", timeout: float = 5.0) -> dict:
    """Ask systemd's Restart=always to relaunch wvkbd with the new args file.

    Never manages the process directly and never signals unless the
    supervised launcher's own sentinel is present, so an unsupervised
    (legacy, non-coherent-shell) wvkbd is never killed without a restart.
    """
    sentinel = runtime_dir / "k230-keyboard-supervised"
    if not sentinel.is_file():
        return {"restarted": False, "reason": "not-supervised"}
    try:
        result = subprocess.run(
            [pkill_path, "-TERM", "-u", str(os.getuid()), "-x", "wvkbd-mobintl"],
            capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as error:
        raise KeyboardAppearanceError(f"pkill invocation failed: {error}") from error
    if result.returncode == 0:
        return {"restarted": True}
    if result.returncode == 1:
        return {"restarted": False, "reason": "not-running"}
    raise KeyboardAppearanceError(
        f"pkill failed: {result.stderr.strip() or result.returncode}")


def sync_and_restart(state_root: Path, *, expected_generation: str | None = None,
                     lock_timeout: float = 2.0,
                     runtime_dir: Path = Path("/run/shell"),
                     pkill_path: str = "pkill") -> dict:
    """The one call theme activation makes: publish colours, then restart if needed.

    Failure here never rolls back or fails the shell's own acknowledged
    generation; it is reported under its own state, same convention as
    `app_appearance.sync`.
    """
    try:
        _target, changed, theme_generation = sync(
            state_root, expected_generation=expected_generation, lock_timeout=lock_timeout)
    except KeyboardAppearanceSuperseded:
        return {"state": "superseded", "error": "newer-generation-active"}
    except Exception as error:
        return {"state": "failed", "error": "keyboard-sync-failed",
                "kind": type(error).__name__}
    if not changed:
        return {"state": "applied", "generation": theme_generation, "restarted": False}
    try:
        outcome = restart(runtime_dir, pkill_path=pkill_path)
    except Exception as error:
        return {"state": "failed", "error": "keyboard-restart-failed",
                "kind": type(error).__name__, "generation": theme_generation}
    return {"state": "applied", "generation": theme_generation, **outcome}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "sync"))
    parser.add_argument("--state-root", type=Path, default=Path.home() / ".local/state/omarchy/current")
    parser.add_argument("--generation", type=Path)
    parser.add_argument("--runtime-dir", type=Path, default=Path("/run/shell"))
    parser.add_argument("--pkill", default="pkill")
    args = parser.parse_args()
    if args.operation == "prepare":
        if args.generation is None:
            parser.error("prepare requires --generation")
        print(prepare(args.generation, args.state_root))
    else:
        print(json.dumps(sync_and_restart(args.state_root, runtime_dir=args.runtime_dir,
                                          pkill_path=args.pkill)))


if __name__ == "__main__":
    try:
        main()
    except (KeyboardAppearanceError, TransactionError, OSError, ValueError) as error:
        print(f"k230-keyboard-appearance: {error}", file=sys.stderr)
        sys.exit(1)
