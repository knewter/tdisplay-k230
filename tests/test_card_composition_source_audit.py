#!/usr/bin/env python3
"""Host checks for the repeatable source-audit tool."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def source_fixture(root: Path) -> Path:
    sway = root / "sway"
    (sway / "sway/tree").mkdir(parents=True)
    (sway / "sway/input").mkdir(parents=True)
    (sway / "sway/tree/view.c").write_text(
        "view->scene_tree; view_close(); wlr_scene_node_set_position();\n")
    (sway / "sway/input/seat.c").write_text(
        "seatop_touch_motion(); seat_set_focus_container();\n")
    (sway / "sway/input/seatop_default.c").write_text("seatop_begin_down();\n")
    return sway


def main() -> int:
    with tempfile.TemporaryDirectory() as directory:
        tmp = Path(directory)
        fixture = source_fixture(tmp)
        output = tmp / "audit.md"
        subprocess.run(["python3", "tools/audit-card-composition-sources.py",
                        "--sway-source", str(fixture), "--output", str(output)],
                       cwd=ROOT, check=True)
        text = output.read_text()
        for required in ("TEST-shell-compositor.drv", "Client/protocol boundary",
                         "Sway/wlroots boundary", "does **not** prove",
                         "whole scene subtree", "image-capture sources"):
            assert required in text, required
        (fixture / "sway/input/seat.c").write_text("seat_set_focus_container();\n")
        failed = subprocess.run(["python3", "tools/audit-card-composition-sources.py",
                                 "--sway-source", str(fixture), "--output", str(output)],
                                cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        assert failed.returncode != 0
        assert "seatop_touch_motion" in failed.stderr
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
