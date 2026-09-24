#!/usr/bin/env python3
"""Prepare an unchanged Omarchy theme for an acknowledged handheld swap.

This host-side coordinator deliberately fails closed without a shell receiver.
The normal service integration is a later OpenSpec task.
"""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
import tomllib

from theme_sources import source_dir, source_digest


ROOT = Path(__file__).resolve().parents[1]
HOST_TOOLS = ROOT / "nix/omarchy-theme-tools/upstream"
SAFE_NAME = re.compile(r"[a-z0-9][a-z0-9._-]{0,79}\Z")
ICON_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,159}\Z")
SECTION = re.compile(r"shell\.[a-zA-Z0-9_-]+\.toml\Z")
STILLS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
VIDEOS = {".mp4", ".m4v", ".mov", ".webm", ".mkv", ".avi"}
MAX_CONFIG = 2 * 1024 * 1024
MAX_ASSET = 256 * 1024 * 1024
MAX_TOTAL = 512 * 1024 * 1024
KNOWN_PALETTE = {
    "mode", "theme_type", "accent", "background", "foreground", "selection",
    "selection_background", "selection_foreground", "cursor", "muted",
    "dark_background", "darker_background", "lighter_background",
    "dark_foreground", "light_foreground", "bright_foreground", "bg", "fg",
    "dark_bg", "darker_bg", "lighter_bg", "dark_fg", "light_fg", "bright_fg",
    "red", "green", "yellow", "blue", "magenta", "purple", "cyan", "orange", "brown",
    "bright_red", "bright_green", "bright_yellow", "bright_blue",
    "bright_magenta", "bright_purple", "bright_cyan",
    "hyprland_active_border", "hyprland_inactive_border",
} | {f"color{index}" for index in range(16)}


class ThemeError(Exception):
    pass


def normalize_name(name: str) -> str:
    normalized = re.sub(r"\s+", "-", name.strip().lower())
    if not SAFE_NAME.fullmatch(normalized):
        raise ThemeError("invalid theme name")
    return normalized


def tool_path(tools: Path, name: str) -> Path:
    candidate = tools / "bin" / name
    if not candidate.is_file():
        raise ThemeError(f"missing trusted helper: {name}")
    return candidate


def template_root(tools: Path) -> Path:
    for candidate in (tools / "default/themed", tools / "share/omarchy/default/themed"):
        if candidate.is_dir():
            return candidate
    raise ThemeError("trusted helper templates unavailable")


def invoke(tools: Path, name: str, *args: str, env=None) -> str:
    child_env = os.environ.copy() if env is None else env.copy()
    child_env["PATH"] = str(tools / "bin") + os.pathsep + child_env.get("PATH", "")
    result = subprocess.run([str(tool_path(tools, name)), *args],
                            env=child_env, text=True, capture_output=True, timeout=10)
    if result.returncode or result.stderr.strip():
        raise ThemeError(f"{name} rejected theme data: {result.stderr.strip() or result.returncode}")
    return result.stdout


def checked_copy(source: Path, destination: Path, *, limit: int) -> int:
    if source.is_symlink() or not source.is_file():
        raise ThemeError(f"unsafe source entry: {source.name}")
    size = source.stat().st_size
    if size < 0 or size > limit:
        raise ThemeError(f"source entry exceeds bound: {source.name}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination, follow_symlinks=False)
    return size


def choose_source(name: str, source: Path | None, user_themes: Path, builtins: Path | None):
    name = normalize_name(name)
    if source is not None:
        root = source.resolve(strict=True)
        if (root / "colors.toml").is_file() or (root / "alacritty.toml").is_file():
            return root, source_dir(root)
        return root, source_dir(root, name)
    for root in (user_themes / name, (builtins / name) if builtins else None):
        if root is not None and root.is_dir():
            return root.resolve(strict=True), source_dir(root)
    raise ThemeError(f"theme not found: {name}")


def prepare(name: str, *, source: Path | None, state_root: Path,
            user_themes: Path, builtins: Path | None, tools: Path) -> tuple[Path, dict]:
    name = normalize_name(name)
    root, theme = choose_source(name, source, user_themes, builtins)
    source_hash = source_digest(theme)
    helper_hash = source_digest(tools)
    adapter_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    generations = state_root / "generations"
    generations.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".prepare-", dir=generations) as temporary:
        work = Path(temporary)
        staged = work / "theme"
        staged.mkdir()
        report = {"source": str(theme), "source_sha256": source_hash,
                  "helper_sha256": helper_hash, "adapter_sha256": adapter_hash,
                  "name": name, "applied": [], "unavailable": [], "unknown": [],
                  "backgrounds": [], "icon_theme": None}
        total = 0
        allowed = {"colors.toml", "shell.toml", "icons.theme", "foot.ini", "alacritty.toml"}
        for entry in sorted(theme.iterdir()):
            if entry.name == ".git":
                continue
            if entry.is_symlink():
                raise ThemeError(f"symlink in theme: {entry.name}")
            if entry.is_dir() and entry.name == "backgrounds":
                for asset in sorted(entry.iterdir()):
                    if asset.suffix.lower() not in STILLS | VIDEOS:
                        report["unknown"].append(f"backgrounds/{asset.name}: unsupported suffix")
                        continue
                    total += checked_copy(asset, staged / "backgrounds" / asset.name, limit=MAX_ASSET)
                    report["backgrounds"].append(f"backgrounds/{asset.name}")
            elif entry.is_dir():
                report["unknown"].append(f"{entry.name}/: not an appearance input")
            elif entry.name in allowed or SECTION.fullmatch(entry.name):
                if entry.name in ("foot.ini", "alacritty.toml"):
                    # Terminal files can contain executable directives. Use
                    # only a scratch Alacritty palette when colors.toml is absent.
                    report["unavailable"].append(f"{entry.name}: executable configuration withheld")
                    if entry.name != "alacritty.toml" or (theme / "colors.toml").exists():
                        continue
                    scratch = work / "legacy"
                    scratch.mkdir(exist_ok=True)
                    total += checked_copy(entry, scratch / "alacritty.toml", limit=MAX_CONFIG)
                    invoke(tools, "omarchy-theme-colors-from-alacritty", str(scratch))
                    if not (scratch / "colors.toml").is_file():
                        raise ThemeError("legacy palette could not be converted")
                    total += checked_copy(scratch / "colors.toml", staged / "colors.toml", limit=MAX_CONFIG)
                    report["applied"].append("colors.toml: legacy scratch conversion")
                    continue
                total += checked_copy(entry, staged / entry.name, limit=MAX_CONFIG)
                report["applied"].append(entry.name)
            else:
                report["unknown"].append(f"{entry.name}: not an appearance input")
            if total > MAX_TOTAL:
                raise ThemeError("theme exceeds total staging bound")
        if not (staged / "colors.toml").is_file():
            raise ThemeError("theme has no usable palette")
        try:
            with (staged / "colors.toml").open("rb") as stream:
                raw = tomllib.load(stream)
            if not all(isinstance(k, str) and isinstance(v, str) for k, v in raw.items()):
                raise ValueError("palette must contain string keys and values")
        except (tomllib.TOMLDecodeError, ValueError) as error:
            raise ThemeError(f"invalid palette: {error}") from error
        for key in raw:
            if key not in KNOWN_PALETTE:
                report["unknown"].append(f"palette.{key}: preserved; no current role mapping")
        resolved = invoke(tools, "omarchy-theme-color", "--file", str(staged / "colors.toml"), "--all")
        report["palette"] = dict(line.split("\t", 1) for line in resolved.splitlines())
        # Curate trusted outputs before invoking the upstream template engine.
        curated = work / "templates"
        curated.mkdir()
        for filename in ("shell.toml.tpl", "foot.ini.tpl"):
            checked_copy(template_root(tools) / filename, curated / filename, limit=MAX_CONFIG)
        user_templates = work / "empty-user-templates"
        user_templates.mkdir()
        env = os.environ | {"OMARCHY_THEME_TEMPLATES_DIR": str(curated),
                            "OMARCHY_THEME_USER_TEMPLATES_DIR": str(user_templates),
                            "OMARCHY_THEME_STAGING_DIR": str(staged)}
        invoke(tools, "omarchy-theme-set-templates", env=env)
        for filename in ("shell.toml", "foot.ini"):
            path = staged / filename
            if not path.is_file() or path.stat().st_size > MAX_CONFIG:
                raise ThemeError(f"missing or oversized generated {filename}")
            if b"{{" in path.read_bytes():
                raise ThemeError(f"unresolved template reference in {filename}")
        try:
            with (staged / "shell.toml").open("rb") as stream:
                tomllib.load(stream)
        except tomllib.TOMLDecodeError as error:
            raise ThemeError(f"invalid shell appearance: {error}") from error
        icon_file = staged / "icons.theme"
        if icon_file.exists():
            selected = icon_file.read_text().strip()
            if not ICON_NAME.fullmatch(selected):
                raise ThemeError("invalid icon theme selector")
            report["icon_theme"] = selected
        report["generation"] = hashlib.sha256(
            json.dumps({"source": source_hash, "source_path": str(theme),
                        "helpers": helper_hash, "adapter": adapter_hash,
                        "name": name, "version": 1}, sort_keys=True).encode()
        ).hexdigest()[:24]
        destination = generations / report["generation"]
        (work / "theme.name").write_text(name + "\n")
        (work / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        if report["backgrounds"]:
            (work / "background").symlink_to("theme/" + report["backgrounds"][0])
        if source_digest(theme) != source_hash:
            raise ThemeError("theme source changed during preparation")
        if destination.exists():
            existing = json.loads((destination / "report.json").read_text())
            if (existing["source_sha256"] != source_hash or existing["name"] != name
                    or existing["source"] != str(theme)
                    or existing["helper_sha256"] != helper_hash
                    or existing["adapter_sha256"] != adapter_hash):
                raise ThemeError("generation identity collision")
            return destination, existing
        os.replace(work, destination)
        return destination, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--state-root", type=Path, default=Path.home() / ".local/state/omarchy/current")
    parser.add_argument("--user-themes", type=Path, default=Path.home() / ".config/omarchy/themes")
    parser.add_argument("--builtins", type=Path)
    parser.add_argument("--tools", type=Path, default=HOST_TOOLS)
    parser.add_argument("--prepare-only", action="store_true", required=True)
    args = parser.parse_args()
    destination, report = prepare(args.name, source=args.source, state_root=args.state_root,
                                  user_themes=args.user_themes, builtins=args.builtins, tools=args.tools)
    print(json.dumps({"generation_path": str(destination), "report": report}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
