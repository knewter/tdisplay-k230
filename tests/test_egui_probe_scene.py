#!/usr/bin/env python3
"""Host fixture: the egui probe's scene constants match the SHM baseline's, and
its event log keeps the schema tools/qtquick_analysis.py reads.

Evidence class: host source check only. It does not render anything.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCENE_H = (ROOT / "nix/qtquick-shm-baseline/scene.h").read_text()
MAIN_RS = (ROOT / "nix/egui-software-probe/src/main.rs").read_text()
NIX = (ROOT / "nix/egui-software-probe/default.nix").read_text()
CARGO = (ROOT / "nix/egui-software-probe/Cargo.toml").read_text()

# (egui constant, baseline constant, scale applied to the baseline's)
SAME = ["SC_WIDTH", "SC_HEIGHT", "SC_BG", "SC_HEADER_H", "SC_HEADER_COLOR", "SC_LIST_X", "SC_LIST_Y", "SC_LIST_W",
        "SC_LIST_H", "SC_ROW_COUNT", "SC_ROW_H", "SC_ROW_SPACING", "SC_ROW_COLOR", "SC_ROW_SELECTED", "SC_EDITOR_X",
        "SC_EDITOR_Y", "SC_EDITOR_W", "SC_EDITOR_H", "SC_MOVER_Y", "SC_MOVER_W", "SC_MOVER_H", "SC_MOVER_X_LEFT",
        "SC_MOVER_X_RIGHT", "SC_PANEL_X", "SC_PANEL_Y", "SC_PANEL_W", "SC_PANEL_H", "SC_SWATCH_X", "SC_SWATCH_Y",
        "SC_SWATCH_W", "SC_SWATCH_H", "SC_SWATCH_COLOR"]


def baseline(name):
    m = re.search(r"#define %s\s+(0x[0-9a-fA-F]+|-?\d+(?:\.\d+)?)\b" % name, SCENE_H)
    assert m, name
    return float(int(m.group(1), 16)) if m.group(1).startswith("0x") else float(m.group(1))


def egui(name):
    m = re.search(r"const %s: \w+ = (0x[0-9a-fA-F]+|-?\d+(?:\.\d+)?);" % name, MAIN_RS)
    assert m, name
    return float(int(m.group(1), 16)) if m.group(1).startswith("0x") else float(m.group(1))


class EguiScene(unittest.TestCase):
    def test_geometry_and_colors_match_the_baseline(self):
        for name in SAME:
            self.assertEqual(egui(name), baseline(name), name)

    def test_animation_duration_matches(self):
        self.assertAlmostEqual(egui("SC_ANIM_S") * 1000, baseline("SC_ANIM_MS"))

    def test_event_schema(self):
        for event in ("start", "first_frame", "input", "commit"):
            self.assertIn('"%s"' % event, MAIN_RS)
        for kind in ("press", "move", "release", "key"):
            self.assertIn('"%s"' % kind, MAIN_RS)

    def test_no_gl_or_window_toolkit_is_a_dependency(self):
        for banned in ("winit", "softbuffer", "wgpu", "glow", "eframe", "egui_glow"):
            self.assertNotIn(banned, CARGO)
        self.assertIn("default-features = false", CARGO)
        self.assertIn("egui_software_backend", CARGO)

    def test_package_is_cpu_only(self):
        args = NIX.split("\n", 1)[0]
        self.assertEqual(args.replace(" ", ""), "{lib,rustPlatform}:")


if __name__ == "__main__":
    unittest.main()
