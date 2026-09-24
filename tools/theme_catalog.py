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

import theme_activate as activation
from theme_transaction import TransactionError, _pointer, activate_generation
from theme_preferences import SelectionIntent
import keyboard_appearance


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


def discover(user_themes: Path, builtins: Path | None) -> list[Entry]:
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
                  background_id: str | None = None) -> tuple[Path, dict]:
    def prepare(background=None):
        return activation.prepare(entry.name, source=entry.source, state_root=state_root,
                                  user_themes=entry.source.parent, builtins=None,
                                  tools=tools, background_choice=background)

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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tools", type=Path, default=activation.HOST_TOOLS)
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
    args = parser.parse_args(argv)
    if (args.rust_socket is None) != (args.deck_socket is None):
        parser.error("--rust-socket and --deck-socket must be supplied together")
    try:
        entries = discover(args.user_themes, args.builtins)
        if args.action == "list":
            result = {"schema": 1, "themes": [entry.public() for entry in entries],
                      "active": selected(args.state_root, entries)}
        else:
            entry = choose(entries, args.id)
            generation, report = prepare_entry(entry, state_root=args.state_root,
                                               tools=args.tools, background_id=args.background)
            result = preview(entry, generation, report)
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
                result["keyboard_appearance"] = keyboard_appearance.sync_and_restart(
                    args.state_root, expected_generation=generation.name,
                    runtime_dir=args.keyboard_runtime_dir, pkill_path=args.pkill)
                result["activated"] = True
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, activation.ThemeError, TransactionError,
            subprocess.SubprocessError) as error:
        print(json.dumps({"schema": 1, "error": str(error), "activated": False}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
