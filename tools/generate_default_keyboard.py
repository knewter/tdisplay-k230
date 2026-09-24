#!/usr/bin/env python3
"""Regenerate or check the pinned wvkbd colour args using the production adapter."""

import argparse
import json
from pathlib import Path
import shutil
import tempfile

from keyboard_appearance import args_file, colors


ROOT = Path(__file__).resolve().parents[1] / "nix/handheld-theme-default"


def expected() -> str:
    report = ROOT / "default-report.json"
    identity = json.loads(report.read_text())["generation"]
    with tempfile.TemporaryDirectory() as temporary:
        generation = Path(temporary) / identity
        generation.mkdir()
        shutil.copyfile(report, generation / "report.json")
        return args_file(colors(generation))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = expected()
    path = ROOT / "wvkbd.args"
    if args.check:
        if not path.is_file() or path.read_text() != content:
            raise SystemExit("stale pinned wvkbd colour args")
    else:
        path.write_text(content)


if __name__ == "__main__":
    main()
