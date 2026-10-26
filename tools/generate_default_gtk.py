#!/usr/bin/env python3
"""Regenerate or check the pinned default GTK keyfile and GTK3 settings/CSS."""

import argparse
import json
from pathlib import Path
import shutil
import tempfile

from app_appearance import gtk3_files, gtk_appearance, palette
from theme_gtk import render


ROOT = Path(__file__).resolve().parents[1] / "nix/handheld-theme-default"


def expected() -> dict[str, str]:
    report = ROOT / "default-report.json"
    identity = json.loads(report.read_text())["generation"]
    with tempfile.TemporaryDirectory() as temporary:
        generation = Path(temporary) / identity
        generation.mkdir()
        shutil.copyfile(report, generation / "report.json")
        mode, icon_theme = gtk_appearance(generation)
        colors = palette(generation)
    return {"gtk-settings.keyfile": render(mode, icon_theme)} | gtk3_files(colors, mode, icon_theme)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files = expected()
    for name, content in files.items():
        path = ROOT / name
        if args.check:
            if not path.is_file() or path.read_text() != content:
                raise SystemExit(f"stale pinned GTK file: {name}")
        else:
            path.parent.mkdir(exist_ok=True)
            path.write_text(content)


if __name__ == "__main__":
    main()
