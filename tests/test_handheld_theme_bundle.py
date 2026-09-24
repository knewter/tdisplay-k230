#!/usr/bin/env python3
"""Check the pinned built-in theme package and its recoverable default."""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from theme_sources import source_digest  # noqa: E402
import theme_activate as activation  # noqa: E402
import theme_catalog  # noqa: E402

THEME = ROOT / "nix/handheld-theme-default"

# All omacom/omarchy `themes/` collection members at the pinned revision
# (nix/handheld-theme-default/SOURCE.md); every one is installed as a
# built-in by nix/handheld-theme-default/default.nix.
ALL_BUILTIN_THEMES = (
    "catppuccin", "catppuccin-latte", "ethereal", "everforest",
    "flexoki-light", "gruvbox", "hackerman", "kanagawa", "last-horizon",
    "lumon", "lupine", "matte-black", "miasma", "nord", "osaka-jade",
    "retro-82", "ristretto", "rose-pine", "solitude", "tokyo-night",
    "vantablack", "white",
)
# catppuccin/catppuccin-latte ship at full upstream resolution (their
# generation identities are pinned to those exact bytes); every other
# built-in ships a bounded-height background derivative. A small margin
# above the panel's 1232px long edge is allowed.
BOUNDED_BACKGROUND_MAX_HEIGHT = 1300


def read(path):
    return json.loads(path.read_text())


def check(package: Path) -> None:
    inventory = read(THEME / "source-inventory.json")
    assert inventory["revision"] == "28ceaae70ebac3a0edcc21f2faa77a90dc6d404c"
    source = package / "share/omarchy/themes"
    actual_files = {
        str(path.relative_to(package / "share/omarchy")): hashlib.sha256(path.read_bytes()).hexdigest()
        for name in ("catppuccin", "catppuccin-latte")
        for path in (source / name).rglob("*") if path.is_file()
    }
    assert actual_files == inventory["files"], "built-in theme files differ from pinned upstream"
    for name, expected in inventory["source_sha256"].items():
        assert source_digest(source / name) == expected

    bundled = read(THEME / "bundled-report.json")
    appearance = read(THEME / "bundled-appearance.json")
    recovery = read(THEME / "default-report.json")
    generation = bundled["generation"]
    digest_input = {
        "base_generation": recovery["generation"],
        "source_revision": inventory["revision"],
        "source_sha256": inventory["source_sha256"]["catppuccin"],
        "selected_background": bundled["selected_background"],
        "format": 1,
    }
    assert generation == hashlib.sha256(json.dumps(digest_input, sort_keys=True).encode()).hexdigest()[:24]
    assert bundled["source_sha256"] == inventory["source_sha256"]["catppuccin"]
    assert bundled["backgrounds"] == sorted(
        f"backgrounds/{path.name}" for path in (source / "catppuccin/backgrounds").iterdir()
        if path.is_file()
    )
    assert bundled["selected_background"] in bundled["backgrounds"]
    assert appearance["background"] == "background"
    assert appearance["generation"] == generation
    assert (package / "generations" / generation / "report.json").read_bytes() == (THEME / "bundled-report.json").read_bytes()
    assert (package / "generations" / generation / "appearance.json").read_bytes() == (THEME / "bundled-appearance.json").read_bytes()
    assert source_digest(package / "generations" / generation / "theme") == inventory["source_sha256"]["catppuccin"]
    assert (package / "generations" / recovery["generation"] / "appearance.json").is_file()
    for gen_id in (generation, recovery["generation"]):
        assert (package / "generations" / gen_id / "wvkbd.args").read_bytes() == (THEME / "wvkbd.args").read_bytes()
    assert (package / "share/doc/handheld-theme-default/LICENSE").is_file()
    print(f"PASS: 20 unchanged source files, two generations, selected {bundled['selected_background']}")


def check_all_builtins_resolve(package: Path) -> None:
    """Every bundled built-in must parse and resolve through the real
    theme_catalog/theme_activate path, not just the pinned default.
    """
    from PIL import Image

    builtins_dir = package / "share/omarchy/themes"
    on_disk = sorted(path.name for path in builtins_dir.iterdir() if path.is_dir())
    assert on_disk == sorted(ALL_BUILTIN_THEMES), (
        f"installed built-ins {on_disk} do not match the expected set")

    entries = theme_catalog.discover(Path("/nonexistent-user-themes"), builtins_dir)
    discovered = {entry.name for entry in entries}
    assert discovered == set(ALL_BUILTIN_THEMES), (
        f"catalog discovery {sorted(discovered)} missed a built-in")

    for name in ALL_BUILTIN_THEMES:
        with tempfile.TemporaryDirectory() as temp:
            state_root = Path(temp) / "state"
            generation, report = activation.prepare(
                name, source=builtins_dir / name, state_root=state_root,
                user_themes=Path(temp) / "user", builtins=None,
                tools=activation.HOST_TOOLS,
            )
            assert (generation / "appearance.json").is_file(), name
            assert report["backgrounds"], f"{name} has no background candidates"
            bounded = name not in ("catppuccin", "catppuccin-latte")
            for asset in report["backgrounds"]:
                if Path(asset).suffix.lower() not in activation.STILLS:
                    continue
                with Image.open(generation / "theme" / asset) as image:
                    if bounded:
                        assert image.height <= BOUNDED_BACKGROUND_MAX_HEIGHT, (
                            f"{name}/{asset} is {image.width}x{image.height}, "
                            f"exceeds the bounded-background height")
    print(f"PASS: all {len(ALL_BUILTIN_THEMES)} built-ins resolve and stage "
          "through theme_activate.prepare(); bounded backgrounds stay "
          f"<= {BOUNDED_BACKGROUND_MAX_HEIGHT}px tall")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    args = parser.parse_args()
    check(args.package)
    check_all_builtins_resolve(args.package)
