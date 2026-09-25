#!/usr/bin/env python3
"""JSON catalog and cancellable preparation for the handheld theme chooser.

No theme code runs. Preview prepares a generation without changing the active
pointer; Apply uses the existing acknowledged transaction. Asset paths in a
preview refer to staged files, not a mutable checkout. Image decode and the
touch UI are separate consumers and are not proved by this interface.
"""

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading

import theme_activate as activation
from theme_transaction import TransactionError, _pointer, activate_generation, prepare_only
from theme_preferences import SelectionIntent
import keyboard_appearance
import theme_timing


MAX_ENTRIES = 512
IDENTITY = re.compile(r"[a-f0-9]{24}\Z")


def identity(*parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=True).encode()).hexdigest()[:24]


@dataclass(frozen=True)
class Entry:
    id: str
    name: str
    label: str
    origin: str
    source: Path
    preview_path: Path | None

    def public(self):
        return {"id": self.id, "name": self.name, "label": self.label,
                "origin": self.origin,
                "preview_path": str(self.preview_path) if self.preview_path else None}


#: Search order for a theme's own preview image, matching upstream
#: `bin/omarchy-theme-switcher`'s `find_preview()` restricted to the still
#: formats this project actually decodes (`theme_activate.STILLS`); that
#: helper also accepts a video preview/background, which has no decodable
#: thumbnail here and is skipped rather than claimed.
PREVIEW_NAMES = ("preview.png", "preview.jpg", "preview.jpeg", "preview.webp",
                 "preview.gif", "preview.bmp")


def find_preview(path: Path) -> Path | None:
    """A theme's own preview image, matching Omarchy's per-theme `preview.*`
    convention, or (absent one) its first background image as a
    representative thumbnail. Cheap directory metadata only; never decodes.
    """
    for name in PREVIEW_NAMES:
        preview = path / name
        if preview.is_file() and not preview.is_symlink():
            return preview
    backgrounds = path / "backgrounds"
    if backgrounds.is_dir() and not backgrounds.is_symlink():
        with os.scandir(backgrounds) as scan:
            candidates = sorted(
                item.name for item in scan
                if item.is_file(follow_symlinks=False)
                and Path(item.name).suffix.lower() in activation.STILLS)
        if candidates:
            return backgrounds / candidates[0]
    return None


def _listing_signature(directory: Path) -> tuple | None:
    """A cheap (stat-only, no content read, no hashing, no `resolve()`)
    fingerprint of one directory's immediate children: name, mtime, and
    whether each is a directory. `None` if the directory is unreadable/
    missing, distinct from `()` (readable and empty)."""
    try:
        with os.scandir(directory) as scan:
            return tuple(sorted(
                (item.name, item.stat(follow_symlinks=False).st_mtime_ns,
                 item.is_dir(follow_symlinks=False))
                for item in scan
            ))
    except OSError:
        return None


def _catalog_signature(user_themes: Path, builtins: Path | None) -> tuple:
    """A fingerprint of exactly the directory levels `discover()` itself
    reads (each root's own top level, and -- for a user-origin entry that
    is a directory -- one level deeper under its own `themes/`, the
    collection case) so a cache keyed on this can tell "nothing `discover()`
    would see has changed" without paying `discover()`'s own, more
    expensive per-entry cost (`Entry.id`'s hashing, `has_palette()`'s and
    `find_preview()`'s extra stats, `path.resolve(strict=True)`)."""
    signature = []
    for origin, directory in (("user", user_themes), ("builtin", builtins)):
        if directory is None:
            signature.append((origin, None))
            continue
        top = _listing_signature(directory)
        signature.append((origin, top))
        if origin == "user" and top:
            for name, _mtime, is_dir in top:
                if is_dir:
                    signature.append((origin, name, _listing_signature(directory / name / "themes")))
    return tuple(signature)


#: Per-process cache of `_discover_uncached()`'s result, keyed by
#: (user_themes, builtins) and invalidated by `_catalog_signature()`. Board
#: evidence (2026-09-24): `discover()` cost ~42 ms per `preview`/`activate`
#: call even though the theme catalog itself had not changed since the
#: previous call moments earlier -- real, in `theme-helper.service`'s own
#: process, unrelated to Python start-up. A bare CLI process only ever
#: calls this once per invocation anyway (empty cache, no behavior change);
#: the daemon serves many requests against a catalog that, in the normal
#: preview-then-activate chooser flow, has not changed at all.
_discover_cache: dict[tuple[str, str | None], tuple[tuple, list["Entry"]]] = {}


def discover(user_themes: Path, builtins: Path | None) -> list[Entry]:
    key = (str(user_themes), str(builtins) if builtins is not None else None)
    signature = _catalog_signature(user_themes, builtins)
    cached = _discover_cache.get(key)
    if cached is not None and cached[0] == signature:
        return cached[1]
    entries = _discover_uncached(user_themes, builtins)
    _discover_cache[key] = (signature, entries)
    return entries


def _discover_uncached(user_themes: Path, builtins: Path | None) -> list[Entry]:
    """Read only cheap directory metadata; hash/resolve only on explicit preview.

    A user child can be a standalone clone or a collection containing themes/.
    Built-in and user duplicates remain separately selectable. The entry budget
    is shared across both roots and collections, including ignored files.
    """
    entries, visited = [], 0

    def children(directory):
        nonlocal visited
        if not directory.exists():
            return []
        found = []
        with os.scandir(directory) as scan:
            for item in scan:
                visited += 1
                if visited > MAX_ENTRIES:
                    raise activation.ThemeError("theme catalog exceeds entry bound")
                if (not item.name.startswith(".") and not item.is_symlink()
                        and item.is_dir(follow_symlinks=False)):
                    found.append(Path(item.path))
        return sorted(found)

    def has_palette(path):
        return any((path / name).is_file() and not (path / name).is_symlink()
                   for name in ("colors.toml", "alacritty.toml"))

    def add(origin, relative, path):
        try:
            name = activation.normalize_name(path.name)
        except activation.ThemeError:
            return
        if len(path.name) > 80 or not path.name.isprintable():
            return
        resolved = path.resolve(strict=True)
        entries.append(Entry(identity(origin, relative), name, path.name,
                             origin, resolved, find_preview(resolved)))

    for origin, directory in (("user", user_themes), ("builtin", builtins)):
        if directory is None:
            continue
        for path in children(directory):
            if has_palette(path):
                add(origin, path.name, path)
            elif origin == "user":
                collection = path / "themes"
                if collection.is_dir() and not collection.is_symlink():
                    for member in children(collection):
                        if has_palette(member):
                            add(origin, f"{path.name}/themes/{member.name}", member)
    return sorted(entries, key=lambda entry: (entry.label.casefold(), entry.origin, entry.id))


def selected(state_root: Path, entries: list[Entry]) -> dict:
    generation = _pointer(state_root)
    if generation is None:
        return {"id": None, "generation": None}
    report_path = generation / "report.json"
    if report_path.stat().st_size > activation.MAX_CONFIG:
        raise activation.ThemeError("active report exceeds bound")
    report = json.loads(report_path.read_text())
    if not isinstance(report, dict):
        raise activation.ThemeError("invalid active theme report")
    entry = next((item for item in entries if str(item.source) == report.get("source")), None)
    return {"id": entry.id if entry else None, "generation": generation.name}


def choose(entries: list[Entry], theme_id: str) -> Entry:
    if not IDENTITY.fullmatch(theme_id):
        raise activation.ThemeError("invalid theme identity")
    entry = next((item for item in entries if item.id == theme_id), None)
    if entry is None:
        raise activation.ThemeError("theme is no longer in the catalog")
    return entry


def prepare_entry(entry: Entry, *, state_root: Path, tools: Path,
                  background_id: str | None = None,
                  wallpaper_cache_tool: Path | None = None) -> tuple[Path, dict]:
    def prepare(background=None):
        return activation.prepare(entry.name, source=entry.source, state_root=state_root,
                                  user_themes=entry.source.parent, builtins=None,
                                  tools=tools, background_choice=background,
                                  wallpaper_cache_tool=wallpaper_cache_tool)

    generation, report = prepare()
    if background_id is not None:
        asset = next((item for item in report["backgrounds"]
                      if identity(entry.id, item) == background_id), None)
        if asset is None:
            raise activation.ThemeError("background is no longer in this theme")
        if asset != report["selected_background"]:
            generation, report = prepare(asset)
    return generation, report


def preview(entry: Entry, generation: Path, report: dict) -> dict:
    backgrounds = []
    for asset in report["backgrounds"]:
        video = Path(asset).suffix.lower() in activation.VIDEOS
        backgrounds.append({"id": identity(entry.id, asset), "label": Path(asset).name,
                            "kind": "video" if video else "image",
                            "path": str(generation / "theme" / asset),
                            "selected": asset == report["selected_background"],
                            "decode_status": "unverified"})
    return {"schema": 1, "theme": entry.public(), "generation": generation.name,
            "appearance_path": str(generation / "appearance.json"),
            "palette": report["palette"], "icon_theme": report["icon_theme"],
            "backgrounds": backgrounds,
            "compatibility": {key: report[key] for key in ("applied", "unavailable", "unknown")},
            "activated": False}


def build_parser() -> argparse.ArgumentParser:
    """The single source of truth for this CLI's flags and subcommands.

    Shared with `tools/theme_helperd.py`'s persistent daemon so a warmed,
    long-lived process parses and validates a request identically to a
    fresh `python3 theme_catalog.py` invocation -- no separate protocol to
    let drift in.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tools", type=Path, default=activation.HOST_TOOLS)
    parser.add_argument("--wallpaper-cache-tool", type=Path,
                        help="k230-shell-rust binary, for precomputing a panel-sized wallpaper cache")
    parser.add_argument("--user-themes", type=Path, default=Path.home() / ".config/omarchy/themes")
    parser.add_argument("--builtins", type=Path)
    parser.add_argument("--state-root", type=Path, default=Path.home() / ".local/state/omarchy/current")
    parser.add_argument("--socket", type=Path, default=Path("/run/shell/appearance.sock"))
    parser.add_argument("--rust-socket", type=Path)
    parser.add_argument("--deck-socket", type=Path)
    parser.add_argument("--keyboard-runtime-dir", type=Path, default=Path("/run/shell"))
    parser.add_argument("--pkill", default="pkill")
    actions = parser.add_subparsers(dest="action", required=True)
    listing = actions.add_parser("list")
    listing.add_argument("--json", action="store_true", help="JSON is also the default")
    for action in ("preview", "activate"):
        command = actions.add_parser(action)
        command.add_argument("id")
        command.add_argument("--json", action="store_true")
        command.add_argument("--background", help="opaque background ID from preview")
        if action == "activate":
            command.add_argument("--expected-generation", required=True,
                                 help="generation reviewed in preview; reject changed sources")
    return parser


def _deferred_keyboard_sync(state_root: Path, generation_name: str, runtime_dir: Path,
                            pkill_path: str) -> None:
    """Background-thread body for the keyboard recolour/restart (task 4).

    `keyboard_appearance.sync_and_restart` already catches and reports every
    failure of its own as a `{"state": ...}` dict rather than raising (see
    its own doc); this wrapper only guards against something genuinely
    unexpected so a bug here can never surface as an unhandled exception in
    a background thread (which Python would otherwise print to stderr and
    silently drop with no effect on the caller either way, but never as a
    crash of the interpreter that started it).
    """
    stopwatch = theme_timing.Stopwatch()
    try:
        outcome = keyboard_appearance.sync_and_restart(
            state_root, expected_generation=generation_name,
            runtime_dir=runtime_dir, pkill_path=pkill_path)
        stopwatch.lap("sync_and_restart")
        theme_timing.log("keyboard_deferred", "activate", stopwatch,
                         generation=generation_name[:12], state=outcome.get("state", "?"))
    except Exception as error:  # noqa: BLE001 - last-resort background-thread guard
        print(f"k230-theme: deferred keyboard sync failed: {error}", file=sys.stderr)


def handle(args) -> tuple[dict, int]:
    """Run one already-parsed request and return `(result, exit_code)`.

    Pure with respect to process lifetime: never calls `sys.exit`, `print`,
    or reads `sys.argv`, so a persistent daemon can call this once per
    request, on the same warmed interpreter, without any risk that one
    request's state leaks into the next (every value it touches is either
    a local, a fresh import-module-level cache keyed by its own arguments,
    or the immutable, hash-identified on-disk generation store).
    """
    stopwatch = theme_timing.Stopwatch()
    try:
        entries = discover(args.user_themes, args.builtins)
        stopwatch.lap("discover")
        if args.action == "list":
            result = {"schema": 1, "themes": [entry.public() for entry in entries],
                      "active": selected(args.state_root, entries)}
            stopwatch.lap("selected")
        else:
            entry = choose(entries, args.id)
            generation, report = prepare_entry(entry, state_root=args.state_root,
                                               tools=args.tools, background_id=args.background,
                                               wallpaper_cache_tool=args.wallpaper_cache_tool)
            stopwatch.lap("prepare_entry")
            result = preview(entry, generation, report)
            if args.action == "preview" and args.rust_socket is not None:
                # Best-effort: warm both receivers' Prepare-phase state (in
                # particular the Rust receiver's in-memory wallpaper cache)
                # for this candidate while it is only being browsed, so an
                # Apply that follows without changing the selection commits
                # against an already-decoded buffer instead of a fresh
                # decode. Purely a latency optimisation -- activate_generation
                # below always re-sends its own "prepare" immediately before
                # every commit regardless, which is what the receiver
                # actually validates the commit against, so a failure here
                # can only cost time, never make Apply wrong.
                try:
                    prepare_only(generation, state_root=args.state_root, endpoint=args.socket,
                                endpoints=(args.rust_socket, args.deck_socket))
                except (OSError, TransactionError):
                    pass
                stopwatch.lap("prepare_only_warmup")
            if args.action == "activate":
                if args.expected_generation != generation.name:
                    raise activation.ThemeError("theme changed since preview; preview it again")
                preference = SelectionIntent(args.state_root.resolve(), Path(report["source"]),
                                             report["selected_background"], report["backgrounds"],
                                             explicit=args.background is not None)
                result["app_appearance"] = activate_generation(
                    generation, state_root=args.state_root, endpoint=args.socket,
                    preference=preference,
                    endpoints=(args.rust_socket, args.deck_socket)
                    if args.rust_socket is not None else None)
                stopwatch.lap("activate_generation")
                # Task 4 (visible side effects off the critical path): the
                # panel is already showing the new theme by this point --
                # activate_generation() above only returns after both
                # receivers' two-phase commit is acknowledged. wvkbd has no
                # live-recolor IPC (see keyboard_appearance.py's own doc), so
                # applying its new colours means restarting the process; that
                # restart has no bearing on whether *this* activation
                # succeeded (keyboard_appearance.py's own docstring: failure
                # here "never rolls back or fails the shell's own
                # acknowledged generation"), so it does not need to complete
                # before this response is observable. Run it on a background
                # thread rather than inline: `theme-helper.service`'s
                # request loop (tools/theme_helperd.py) sends its reply the
                # moment `handle()` returns, independent of this thread, so
                # the daemon-served chooser path sees this restart's cost
                # removed entirely. A non-daemon thread is used deliberately
                # so a bare `python3 theme_catalog.py activate` (or the
                # client's own in-process fallback) is unaffected: the
                # interpreter already waits for non-daemon threads at exit,
                # so that path's total wall-clock time is unchanged from
                # before this reordering -- only the daemon path's *observed*
                # latency (the client's read of the response) improves.
                result["keyboard_appearance"] = {"state": "deferred"}
                threading.Thread(
                    target=_deferred_keyboard_sync,
                    args=(args.state_root, generation.name, args.keyboard_runtime_dir, args.pkill),
                ).start()
                stopwatch.lap("keyboard_deferred_dispatch")
                result["activated"] = True
        theme_timing.log("handle", args.action, stopwatch,
                         id=getattr(args, "id", "-"), outcome="ok")
        return result, 0
    except (OSError, ValueError, activation.ThemeError, TransactionError,
            subprocess.SubprocessError) as error:
        theme_timing.log("handle", args.action, stopwatch,
                         id=getattr(args, "id", "-"), outcome="error", error=str(error)[:80])
        return {"schema": 1, "error": str(error), "activated": False}, 1


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if (args.rust_socket is None) != (args.deck_socket is None):
        parser.error("--rust-socket and --deck-socket must be supplied together")
    result, code = handle(args)
    print(json.dumps(result, sort_keys=True), file=sys.stderr if code else sys.stdout)
    return code


if __name__ == "__main__":
    sys.exit(main())
