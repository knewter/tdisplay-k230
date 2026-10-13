import importlib.util
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("keymap", ROOT / "tools/keyboard-base-keymap.py")
keymap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(keymap)

DTSI = ROOT / "nix/dts/k230-tdisplay-mainline-drm-common.dtsi"


class KeyboardBaseKeymap(unittest.TestCase):
    def test_vendor_codes_round_trip(self):
        # LILYGO's table names every code from 1 to 68 except 4, 30 and 31.
        self.assertEqual(set(keymap.KEYS), set(range(1, 69)) - {4, 30, 31})
        for code in keymap.KEYS:
            row, col = keymap.position(code)
            self.assertLess(row, keymap.ROWS)
            self.assertLess(col, keymap.COLS)
            self.assertEqual(keymap.code_at(row, col), code)

    def test_legends_map_to_matching_keys(self):
        for code, (legend, key) in keymap.KEYS.items():
            if len(legend) == 1 or re.fullmatch(r"F\d+", legend):
                self.assertEqual(key, "KEY_" + legend, code)
        self.assertEqual(keymap.KEYS[9][1], "KEY_RIGHTALT")
        self.assertEqual(keymap.KEYS[3][1], "KEY_RIGHTALT")
        self.assertEqual(keymap.KEYS[8][1], "KEY_LEFTMETA")
        self.assertEqual(keymap.KEYS[11][1], "KEY_MICMUTE")

    def test_positions_are_unique(self):
        positions = [keymap.position(c) for c in keymap.KEYS]
        self.assertEqual(len(positions), len(set(positions)))

    def test_device_tree_holds_generated_block(self):
        self.assertIn(keymap.block(), DTSI.read_text())


if __name__ == "__main__":
    unittest.main()
