#!/usr/bin/env python3
"""Prepare an unchanged Omarchy theme for an acknowledged handheld swap.

This host-side coordinator deliberately fails closed without a shell receiver.
The normal service integration is a later OpenSpec task.
"""

import argparse
import fcntl
import hashlib
import errno
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import tomllib

from theme_sources import source_dir, source_digest
from theme_preferences import SelectionIntent, choice as remembered_choice
from theme_tokens import TokenError, compile_tokens
from theme_transaction import TransactionError, activate_generation
import keyboard_appearance
import theme_timing


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
# The panel is a fixed 568x1232 portrait AMOLED (see AGENTS.md); the Rust
# shell always decodes a still wallpaper to exactly this size with a Crop
# fit (background_decode.rs). A generation's wallpaper cache is therefore
# always built at this one geometry.
PANEL_WIDTH = 568
PANEL_HEIGHT = 1232
# A cache build is advisory: a slow or failing decoder must never turn into
# a failed or slower theme activation than before this feature existed.
WALLPAPER_CACHE_TIMEOUT_S = 15
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


def build_wallpaper_cache(wallpaper_cache_tool: Path, background_path: Path, work: Path) -> None:
    """Precompute `work`'s panel-sized wallpaper decode via the installed
    Rust shell binary's hidden `--write-wallpaper-cache` verb, so a later
    commit, restart, or rollback onto this same (immutable, hash-identified)
    generation loads a small pre-cropped file instead of decoding the
    full-size source again (background_decode.rs).

    This is strictly an optimization: any failure here is swallowed. A
    missing or unreadable cache file is exactly the same, slower, fully
    correct path this activation would have taken before this feature
    existed.
    """
    try:
        subprocess.run(
            [str(wallpaper_cache_tool), "--write-wallpaper-cache", str(background_path),
             str(work), str(PANEL_WIDTH), str(PANEL_HEIGHT)],
            capture_output=True, timeout=WALLPAPER_CACHE_TIMEOUT_S, check=False)
    except (OSError, subprocess.TimeoutExpired):
        pass


def background_listing(theme: Path) -> list[str]:
    """The theme's background asset *names* only (a directory listing, no
    file content read) -- exactly the `report["backgrounds"]` value
    `prepare()`'s staging loop below would build from copying every asset,
    used by `prepare()`'s fast path to pick `selected_background` (and so
    compute the generation identity) without paying that loop's real cost.
    Safe to skip the loop's own symlink/suffix bookkeeping here: `prepare()`
    always calls `source_digest(theme)` first, which already walks the
    whole tree and raises on any symlink, so nothing under `theme` --
    `backgrounds/` included -- can be a symlink by the time this runs.
    """
    directory = theme / "backgrounds"
    if not directory.is_dir():
        return []
    return sorted(
        f"backgrounds/{asset.name}" for asset in directory.iterdir()
        if asset.suffix.lower() in STILLS | VIDEOS
    )


def select_background(backgrounds: list[str], background_choice: str | None,
                      remembered: str | None) -> tuple[str | None, bool]:
    """`report["selected_background"]` and whether the remembered choice was
    unavailable and silently replaced -- the one piece of `prepare()`'s
    report that depends on request-time state (`remembered_choice()`) rather
    than the theme's own content, so a cache hit still has to recompute it
    (cheaply) rather than trusting an on-disk report from a possibly
    different request."""
    if background_choice is not None:
        if background_choice not in backgrounds:
            raise ThemeError("selected background is not a staged theme asset")
        return background_choice, False
    if remembered is not None and remembered in backgrounds:
        return remembered, False
    fallback = next((asset for asset in backgrounds if Path(asset).suffix.lower() in STILLS),
                    next(iter(backgrounds), None))
    return fallback, remembered is not None


def generation_identity(*, source_hash: str, source_path: str, helper_hash: str,
                        adapter_hash: str, name: str, selected_background: str | None) -> str:
    return hashlib.sha256(
        json.dumps({"source": source_hash, "source_path": source_path,
                    "helpers": helper_hash, "adapter": adapter_hash,
                    "name": name, "selected_background": selected_background,
                    "version": 1}, sort_keys=True).encode()
    ).hexdigest()[:24]


#: Per-process cache of `source_digest(tools)`, keyed by the tools
#: directory's own resolved path. Board evidence (2026-09-24,
#: `theme-helper.service` reachable): `prepare_entry` cost 73 ms per
#: `preview`/`activate` even on a cache hit for the generation itself,
#: because both digests below were still recomputed from scratch every
#: call. `tools` is `theme_helperd.py`'s own fixed `--tools` startup flag
#: (a Nix store path in production, or `theme_catalog.py`'s own
#: `--tools`/`HOST_TOOLS` default for a bare CLI run) -- immutable for the
#: life of *this* process either way, so caching it indefinitely, keyed by
#: its resolved path, is safe: a bare CLI process only ever calls this
#: once anyway (empty cache, no behavior change), and the daemon's `tools`
#: value never changes between requests without a restart. Unlike the
#: theme's own `source_hash` just above (a person can edit their own
#: theme's files while the daemon keeps running), there is no plausible
#: mid-process change to miss here.
_helper_hash_cache: dict[str, str] = {}


def helper_digest(tools: Path) -> str:
    key = str(tools.resolve(strict=True))
    cached = _helper_hash_cache.get(key)
    if cached is not None:
        return cached
    digest = source_digest(tools)
    _helper_hash_cache[key] = digest
    return digest


def prepare(name: str, *, source: Path | None, state_root: Path,
            user_themes: Path, builtins: Path | None, tools: Path,
            background_choice: str | None = None,
            wallpaper_cache_tool: Path | None = None) -> tuple[Path, dict]:
    name = normalize_name(name)
    root, theme = choose_source(name, source, user_themes, builtins)
    remembered = remembered_choice(state_root, theme) if background_choice is None else None
    stopwatch = theme_timing.Stopwatch()
    source_hash = source_digest(theme)
    stopwatch.lap("source_hash")
    helper_hash = helper_digest(tools)
    stopwatch.lap("helper_hash")
    adapter_hash = hashlib.sha256(Path(__file__).read_bytes()
                                  + (Path(__file__).with_name("theme_tokens.py")).read_bytes()).hexdigest()
    generations = state_root / "generations"
    generations.mkdir(parents=True, exist_ok=True)

    # Fast path: this exact (content-addressed) generation may already be
    # prepared. Everything needed to know that is cheap -- the two digests
    # above and a plain directory listing, never a copy of any asset's
    # bytes or a real (subprocess-spawning) omarchy-theme-tools invocation
    # -- so check it *before* paying for the staging/build work below, not
    # after (board evidence: an already-prepared catppuccin/-latte still
    # took 3.95-4.26 s per `preview`/`activate` before this change, because
    # that check used to run only at the very end of this function).
    backgrounds = background_listing(theme)
    selected_background, remembered_missing = select_background(
        backgrounds, background_choice, remembered)
    stopwatch.lap("background_listing")
    generation_id = generation_identity(
        source_hash=source_hash, source_path=str(theme), helper_hash=helper_hash,
        adapter_hash=adapter_hash, name=name, selected_background=selected_background)
    destination = generations / generation_id
    if destination.exists():
        existing = json.loads((destination / "report.json").read_text())
        if (existing["source_sha256"] != source_hash or existing["name"] != name
                or existing["source"] != str(theme)
                or existing.get("selected_background") != selected_background
                or existing["helper_sha256"] != helper_hash
                or existing["adapter_sha256"] != adapter_hash):
            raise ThemeError("generation identity collision")
        if remembered_missing:
            # Request-specific, not a property of the (immutable, shared)
            # generation itself: do not mutate the cached on-disk report.
            existing = {**existing, "unavailable": [
                *existing["unavailable"],
                "remembered background removed; using theme default",
            ]}
        stopwatch.lap("cache_hit")
        theme_timing.log("prepare", name, stopwatch, generation=generation_id[:12], cache="hit")
        return destination, existing
    stopwatch.lap("cache_miss_check")

    with tempfile.TemporaryDirectory(prefix=".prepare-", dir=generations) as temporary:
        work = Path(temporary)
        staged = work / "theme"
        staged.mkdir()
        report = {"source": str(theme), "source_sha256": source_hash,
                  "helper_sha256": helper_hash, "adapter_sha256": adapter_hash,
                  "name": name, "applied": [], "unavailable": [], "unknown": [],
                  "backgrounds": [], "selected_background": None,
                  "icon_theme": None}
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
        # `selected_background`/`remembered_missing` were already resolved
        # (and, for an invalid `background_choice`, already raised) from
        # `background_listing()`'s cheap pre-pass above; `report["backgrounds"]`,
        # just built by this loop's own copies, is the same set of names by
        # construction. Reusing them here (rather than re-deriving from a
        # second copy of this same selection logic) keeps a single source of
        # truth; the unconditional `source_digest(theme) != source_hash`
        # recheck below still catches a real theme content change during
        # staging and refuses to publish, exactly as before.
        stopwatch.lap("staging_copy")
        if remembered_missing:
            report["unavailable"].append("remembered background removed; using theme default")
        report["selected_background"] = selected_background
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
        stopwatch.lap("omarchy_theme_color")
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
        stopwatch.lap("omarchy_theme_set_templates")
        for filename in ("shell.toml", "foot.ini"):
            path = staged / filename
            if not path.is_file() or path.stat().st_size > MAX_CONFIG:
                raise ThemeError(f"missing or oversized generated {filename}")
            if b"{{" in path.read_bytes():
                raise ThemeError(f"unresolved template reference in {filename}")
        try:
            with (staged / "shell.toml").open("rb") as stream:
                resolved_shell = tomllib.load(stream)
            tokens = compile_tokens(resolved_shell)
        except (tomllib.TOMLDecodeError, TokenError) as error:
            raise ThemeError(f"invalid shell appearance: {error}") from error
        icon_file = staged / "icons.theme"
        if icon_file.exists():
            selected = icon_file.read_text().strip()
            if not ICON_NAME.fullmatch(selected):
                raise ThemeError("invalid icon theme selector")
            report["icon_theme"] = selected
        # `generation_id`/`destination` were already computed in the fast-path
        # prelude above from the same inputs (`selected_background` is the
        # exact value just assigned to `report["selected_background"]`), and
        # `destination` was confirmed not to exist yet at that point -- no
        # need to recompute the identical hash a second time.
        report["generation"] = generation_id
        tokens["generation"] = report["generation"]
        tokens["icon_theme"] = report["icon_theme"]
        tokens["background"] = ("background" if report["selected_background"]
                                and Path(report["selected_background"]).suffix.lower() in STILLS else None)
        serialized = json.dumps(tokens, indent=2, sort_keys=True) + "\n"
        if len(serialized.encode()) > 256 * 1024:
            raise ThemeError("appearance payload exceeds bound")
        (work / "theme.name").write_text(name + "\n")
        (work / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        (work / "appearance.json").write_text(serialized)
        if report["selected_background"]:
            (work / "background").symlink_to("theme/" + report["selected_background"])
        if source_digest(theme) != source_hash:
            raise ThemeError("theme source changed during preparation")
        stopwatch.lap("recheck_source")
        def reuse_existing():
            existing = json.loads((destination / "report.json").read_text())
            if (existing["source_sha256"] != source_hash or existing["name"] != name
                    or existing["source"] != str(theme)
                    or existing.get("selected_background") != report["selected_background"]
                    or existing["helper_sha256"] != helper_hash
                    or existing["adapter_sha256"] != adapter_hash):
                raise ThemeError("generation identity collision")
            # Memory diagnostics are request-specific: a previously prepared
            # immutable generation can have the same selected default while
            # a remembered asset is now missing. Return this preparation's
            # report so the chooser sees that fallback without rewriting the
            # cached generation.
            return destination, report
        if destination.exists():
            # Lost a race against a concurrent preparer of the identical
            # (content-addressed) generation between the fast-path check
            # above and here -- adopt their result instead of failing.
            result = reuse_existing()
            theme_timing.log("prepare", name, stopwatch, generation=generation_id[:12], cache="race")
            return result
        if wallpaper_cache_tool is not None and tokens["background"] == "background":
            build_wallpaper_cache(wallpaper_cache_tool, staged / report["selected_background"], work)
        stopwatch.lap("wallpaper_cache")
        try:
            os.replace(work, destination)
        except OSError as error:
            # A concurrent preparation of the same theme (chooser prepare-
            # ahead, the helper daemon and a client fallback can overlap, and
            # the wallpaper-cache build above widens the window to seconds on
            # the K230) may publish the identical generation first. Generation
            # directories are immutable and content-addressed, so adopt it
            # after the same identity check instead of failing the preview.
            if error.errno not in (errno.ENOTEMPTY, errno.EEXIST) or not destination.is_dir():
                raise
            result = reuse_existing()
            theme_timing.log("prepare", name, stopwatch, generation=generation_id[:12], cache="race")
            return result
        stopwatch.lap("publish")
        theme_timing.log("prepare", name, stopwatch, generation=generation_id[:12], cache="miss")
        return destination, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--state-root", type=Path, default=Path.home() / ".local/state/omarchy/current")
    parser.add_argument("--user-themes", type=Path, default=Path.home() / ".config/omarchy/themes")
    parser.add_argument("--builtins", type=Path)
    parser.add_argument("--tools", type=Path, default=HOST_TOOLS)
    parser.add_argument("--wallpaper-cache-tool", type=Path,
                        help="k230-shell-rust binary, for precomputing a panel-sized wallpaper cache")
    parser.add_argument("--background", help="exact source-relative backgrounds/NAME in this theme")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare-only", action="store_true")
    mode.add_argument("--activate", action="store_true")
    parser.add_argument("--socket", type=Path, default=Path("/run/shell/appearance.sock"))
    parser.add_argument("--rust-socket", type=Path,
                        help="Rust shell appearance receiver (requires --deck-socket)")
    parser.add_argument("--deck-socket", type=Path,
                        help="Sway deck appearance receiver (requires --rust-socket)")
    parser.add_argument("--keyboard-runtime-dir", type=Path, default=Path("/run/shell"),
                        help="Supervised keyboard's XDG_RUNTIME_DIR, for its restart sentinel")
    parser.add_argument("--pkill", default="pkill",
                        help="Trusted pkill executable used to restart a supervised wvkbd")
    args = parser.parse_args()
    if (args.rust_socket is None) != (args.deck_socket is None):
        parser.error("--rust-socket and --deck-socket must be supplied together")
    destination, report = prepare(args.name, source=args.source, state_root=args.state_root,
                                  user_themes=args.user_themes, builtins=args.builtins, tools=args.tools,
                                  background_choice=args.background,
                                  wallpaper_cache_tool=args.wallpaper_cache_tool)
    app_status = None
    keyboard_status = None
    if args.activate:
        preference = SelectionIntent(args.state_root.resolve(), Path(report["source"]),
                                     report["selected_background"], report["backgrounds"],
                                     explicit=args.background is not None)
        app_status = activate_generation(destination, state_root=args.state_root, endpoint=args.socket,
                                         preference=preference,
                                         endpoints=(args.rust_socket, args.deck_socket)
                                         if args.rust_socket is not None else None)
        # Independent of app_status: a keyboard colour failure never revisits
        # the already-acknowledged shell generation, same as app_appearance.
        keyboard_status = keyboard_appearance.sync_and_restart(
            args.state_root, expected_generation=destination.name,
            runtime_dir=args.keyboard_runtime_dir, pkill_path=args.pkill)
    print(json.dumps({"generation_path": str(destination), "report": report,
                      "app_appearance": app_status,
                      "keyboard_appearance": keyboard_status}, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (ThemeError, TransactionError, OSError, ValueError, TimeoutError) as error:
        print(f"omarchy-theme-set: {error}", file=sys.stderr)
        sys.exit(1)
