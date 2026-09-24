#!/usr/bin/env python3
"""Regenerate or check pinned Foot configs using the production app adapter."""

import argparse
import json
from pathlib import Path
import shutil
import tempfile

from app_appearance import foot_config, palette


ROOT = Path(__file__).resolve().parents[1] / "nix/handheld-theme-default"


def expected() -> dict[str, str]:
    report = ROOT / "default-report.json"
    identity = json.loads(report.read_text())["generation"]
    with tempfile.TemporaryDirectory() as temporary:
        generation = Path(temporary) / identity
        generation.mkdir()
        shutil.copyfile(report, generation / "report.json")
        colors = palette(generation)
    return {"terminal-foot.ini": foot_config(colors, monitor=False),
            "monitor-foot.ini": foot_config(colors, monitor=True)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for name, content in expected().items():
        path = ROOT / name
        if args.check:
            if not path.is_file() or path.read_text() != content:
                raise SystemExit(f"stale pinned Foot config: {name}")
        else:
            path.write_text(content)


if __name__ == "__main__":
    main()
