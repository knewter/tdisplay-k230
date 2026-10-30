#!/usr/bin/env python3
"""Host fixtures: the SHM baseline scene must match the Qt Quick probe scene.

Evidence class: host build/test only. It proves the layout constants and the
scripted gestures behave identically in the two clients' source, not that
either renders correctly on the board.
"""
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
QML = (ROOT / "nix/qtquick-software-probe/Probe.qml").read_text()
SCENE_H = (ROOT / "nix/qtquick-shm-baseline/scene.h").read_text()
BASELINE_C = (ROOT / "nix/qtquick-shm-baseline/baseline.c").read_text()
PROBE_CPP = (ROOT / "nix/qtquick-software-probe/main.cpp").read_text()


def define(name):
    match = re.search(r"#define %s\s+(0x[0-9a-fA-F]+|-?\d+(?:\.\d+)?)\b" % name, SCENE_H)
    assert match, name
    return match.group(1)


def num(name):
    return int(define(name), 0)


def color(name):
    return define(name).lower().replace("0x", "")


class SceneParity(unittest.TestCase):
    def test_root_geometry_and_colors(self):
        self.assertIn("width: %d" % num("SC_WIDTH"), QML)
        self.assertIn("height: %d" % num("SC_HEIGHT"), QML)
        self.assertIn('color: "#%s"' % color("SC_BG"), QML)
        self.assertIn('color: "#%s"' % color("SC_HEADER_COLOR"), QML)
        self.assertIn("height: %d" % num("SC_HEADER_H"), QML)
        self.assertIn('"#%s"' % color("SC_ROW_COLOR"), QML)
        self.assertIn('"#%s"' % color("SC_ROW_SELECTED"), QML)
        self.assertIn('"#%s"' % color("SC_SWATCH_COLOR"), QML)

    def test_list_and_editor_geometry(self):
        flick = re.search(r"Flickable \{.*?height: (\d+)", QML, re.S)
        self.assertEqual(int(flick.group(1)), num("SC_LIST_H"))
        self.assertIn("x: %d\n" % num("SC_LIST_X"), QML)
        self.assertIn("y: %d\n" % num("SC_LIST_Y"), QML)
        self.assertIn("width: %d\n        height: %d" % (num("SC_LIST_W"), num("SC_LIST_H")), QML)
        self.assertIn("width: %d; height: %d" % (num("SC_EDITOR_W"), num("SC_EDITOR_H")), QML)
        self.assertIn("model: %d" % num("SC_ROW_COUNT"), QML)
        self.assertIn("height: %d\n                    radius: 12" % num("SC_ROW_H"), QML)
        self.assertIn("spacing: %d" % num("SC_ROW_SPACING"), QML)
        self.assertIn("x: %d; y: %d" % (num("SC_EDITOR_X"), num("SC_EDITOR_Y")), QML)
        self.assertIn("height: %d" % num("SC_EDITOR_H"), QML)
        self.assertEqual(num("SC_ROW_COUNT") * num("SC_ROW_H") + 19 * num("SC_ROW_SPACING"), 1708)

    def test_mover_and_panel_geometry(self):
        self.assertIn("y: %d\n" % num("SC_MOVER_Y"), QML)
        self.assertIn("width: %d; height: %d" % (num("SC_MOVER_W"), num("SC_MOVER_H")), QML)
        self.assertEqual(num("SC_MOVER_X_RIGHT"), num("SC_WIDTH") - num("SC_MOVER_W") - 20)
        self.assertIn(": %d\n        y: %d" % (num("SC_MOVER_X_LEFT"), num("SC_MOVER_Y")), QML)
        self.assertIn("duration: %d" % num("SC_ANIM_MS"), QML)
        self.assertIn("x: %d; y: %d; width: %d; height: %d"
                      % (num("SC_PANEL_X"), num("SC_PANEL_Y"), num("SC_PANEL_W"), num("SC_PANEL_H")), QML)
        self.assertIn("x: %d; y: %d" % (num("SC_SWATCH_X"), num("SC_SWATCH_Y")), QML)
        self.assertIn("width: %d; height: %d" % (num("SC_SWATCH_W"), num("SC_SWATCH_H")), QML)

    def test_strings_are_shared(self):
        for text in ("Qt Quick software probe", "Scroll row ", "Tap to edit", "Tap / retarget",
                     "Software-safe solid rectangle"):
            self.assertIn(text, QML)
            self.assertIn(text, SCENE_H)

    def test_event_schema_is_shared(self):
        for name in ("start", "first_frame", "commit", "input", "exit"):
            self.assertIn(name, BASELINE_C)
            self.assertIn(name, PROBE_CPP)
        for kind in ("press", "move", "release", "key"):
            self.assertIn('"%s"' % kind, BASELINE_C)
            self.assertIn('"%s"' % kind, PROBE_CPP)
        self.assertIn("client_commit", BASELINE_C)
        self.assertIn("client_commit", PROBE_CPP)
        self.assertIn("--exit-after-ms", BASELINE_C)
        self.assertIn("--exit-after-ms", PROBE_CPP)


@unittest.skipUnless(shutil.which("cc"), "needs a host C compiler")
class ScriptedScene(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        cls.exe = Path(cls.dir.name) / "fixture"
        subprocess.run(["cc", "-std=gnu11", "-O1", "-Wall", "-Wextra", "-Werror",
                        "-I", str(ROOT / "nix/qtquick-shm-baseline"), "-o", str(cls.exe),
                        str(ROOT / "tests/fixtures/qtquick_baseline_fixture.c")], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def run_fixture(self, *actions, ppm=None):
        argv = [str(self.exe)]
        if ppm:
            argv += ["--ppm", str(ppm)]
        out = subprocess.run(argv + list(actions), check=True, capture_output=True, text=True).stdout
        return json.loads(out)

    def test_initial_frame(self):
        r = self.run_fixture()
        self.assertEqual((r["width"], r["height"]), (1232, 568))
        self.assertEqual(r["bg"], "161b28")
        self.assertEqual(r["header"], "26344c")
        self.assertEqual(r["row1"], "31415d")
        self.assertEqual(r["swatch"], "ff5b79")
        self.assertEqual(r["mover_left"], "f9c67a")
        self.assertFalse(r["selected"] or r["moved"] or r["focused"])

    def test_tap_row_selects_first_row_colour(self):
        r = self.run_fixture("tap:100,120")
        self.assertTrue(r["selected"])
        self.assertEqual(r["row1"], "4b6ea8")
        self.assertEqual(self.run_fixture("tap:100,120", "tap:100,120")["row1"], "31415d")

    def test_gap_between_rows_is_not_a_tap(self):
        # row 1 spans y=96..170; the 12 px gap follows it.
        self.assertFalse(self.run_fixture("tap:100,176")["selected"])

    def test_drag_scrolls_and_clamps(self):
        self.assertEqual(self.run_fixture("drag:300,400,300,300,200")["scroll"] > 0, True)
        r = self.run_fixture("drag:300,500,300,110,120", "drag:300,500,300,110,120",
                             "drag:300,500,300,110,120", "drag:300,500,300,110,120")
        self.assertEqual(r["scroll"], r["max_scroll"])
        r = self.run_fixture("drag:300,110,300,500,120")
        self.assertEqual(r["scroll"], 0)

    def test_drag_beyond_threshold_is_not_a_tap(self):
        self.assertFalse(self.run_fixture("drag:100,120,100,190,100")["selected"])

    def test_mover_animates_and_retargets(self):
        r = self.run_fixture("tap:700,240")
        self.assertTrue(r["moved"])
        self.assertEqual(r["mover_left"], "161b28")  # it left the left edge
        self.assertEqual(r["mover_right"][:2] != "f9", True)
        self.assertEqual(self.run_fixture("tap:700,240", "tap:700,240")["moved"], False)

    def test_editor_focus_and_typing(self):
        r = self.run_fixture("tap:700,130", "type:ab", "back")
        self.assertTrue(r["focused"])
        self.assertEqual(r["text"], "Tap to edita")
        self.assertEqual(self.run_fixture("type:zz")["text"], "Tap to edit")  # not focused

    def test_frame_has_text_pixels(self):
        with tempfile.TemporaryDirectory() as tmp:
            ppm = Path(tmp) / "f.ppm"
            self.run_fixture(ppm=ppm)
            data = ppm.read_bytes()
            header_end = data.index(b"255\n") + 4
            pixels = data[header_end:]
            self.assertEqual(len(pixels), 1232 * 568 * 3)
            row = lambda y: pixels[y * 1232 * 3:(y + 1) * 1232 * 3]
            self.assertGreater(len(set(row(40))), 2)  # title glyphs differ from the bar colour


@unittest.skipUnless(shutil.which("wayland-scanner") and shutil.which("cc"), "needs wayland-scanner")
class ClientSyntax(unittest.TestCase):
    def test_baseline_compiles_with_werror(self):
        xdg = next((p for p in ("/usr/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml",)
                    if Path(p).is_file()), None)
        ti = "/usr/share/wayland-protocols/unstable/text-input/text-input-unstable-v3.xml"
        if not xdg or not Path(ti).is_file():
            self.skipTest("wayland-protocols XML not installed")
        with tempfile.TemporaryDirectory() as tmp:
            for kind, xml, out in (("client-header", xdg, "xdg-shell-client-protocol.h"),
                                   ("client-header", ti, "text-input-unstable-v3-client-protocol.h")):
                subprocess.run(["wayland-scanner", kind, xml, str(Path(tmp) / out)], check=True)
            subprocess.run(["cc", "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror", "-fsyntax-only",
                            "-I", tmp, "-I", str(ROOT / "nix/qtquick-shm-baseline"),
                            str(ROOT / "nix/qtquick-shm-baseline/baseline.c")], check=True)


if __name__ == "__main__":
    unittest.main()
