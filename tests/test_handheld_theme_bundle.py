#!/usr/bin/env python3
"""Check the pinned built-in theme package and its recoverable default."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from theme_sources import source_digest  # noqa: E402

THEME = ROOT / "nix/handheld-theme-default"


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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    check(parser.parse_args().package)
