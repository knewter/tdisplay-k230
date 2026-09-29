#!/usr/bin/env python3
"""Regenerate or check the pinned default GTK settings keyfile."""

import argparse
import json
from pathlib import Path
import shutil
import tempfile

from app_appearance import gtk_appearance
from theme_gtk import render


ROOT = Path(__file__).resolve().parents[1] / "nix/handheld-theme-default"


def expected() -> str:
    report = ROOT / "default-report.json"
    identity = json.loads(report.read_text())["generation"]
    with tempfile.TemporaryDirectory() as temporary:
        generation = Path(temporary) / identity
        generation.mkdir()
        shutil.copyfile(report, generation / "report.json")
        mode, icon_theme = gtk_appearance(generation)
    return render(mode, icon_theme)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = expected()
    path = ROOT / "gtk-settings.keyfile"
    if args.check:
        if not path.is_file() or path.read_text() != content:
            raise SystemExit("stale pinned GTK settings keyfile")
    else:
        path.write_text(content)


if __name__ == "__main__":
    main()
