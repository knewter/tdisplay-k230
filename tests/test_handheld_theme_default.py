"""Host identity checks for the deliberately media-free pinned default."""

import hashlib
import json
from pathlib import Path
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1] / "nix/handheld-theme-default"
SOURCE_HASHES = {
    "colors.toml": "a7eddcf3342ee0bee5df5ed7aad71c0e8c07ba5549bba7e040064fc5abc09eea",
    "icons.theme": "fabce71aa1d6dff7a151d3ac1ce842c22ee11399e0279b311f97cfcfca30f7ad",
    "LICENSE": "717ba1949502290f8e47688ae2e323acd06c8ca47aec9f7596b15f678c1af4a2",
}


class PinnedThemeDefault(unittest.TestCase):
    def test_source_subset_and_report_identity(self):
        colors = (ROOT / "catppuccin/colors.toml").read_bytes()
        icons = (ROOT / "catppuccin/icons.theme").read_bytes()
        for name, path in (("colors.toml", ROOT / "catppuccin/colors.toml"),
                           ("icons.theme", ROOT / "catppuccin/icons.theme"),
                           ("LICENSE", ROOT / "LICENSE")):
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), SOURCE_HASHES[name])
        report = json.loads((ROOT / "default-report.json").read_text())
        identity = hashlib.sha256(b"catppuccin-colors\0" + colors
                                  + b"catppuccin-icons\0" + icons).hexdigest()[:24]
        self.assertEqual(report["generation"], identity)
        self.assertEqual(report["source_revision"],
                         "28ceaae70ebac3a0edcc21f2faa77a90dc6d404c")
        self.assertEqual(report["palette"], tomllib.loads(colors.decode()))
        self.assertEqual(report["icon_theme"], icons.decode().strip())
        self.assertEqual(report["backgrounds"], [])
        self.assertEqual(report["source_file_sha256"],
                         {"colors.toml": SOURCE_HASHES["colors.toml"],
                          "icons.theme": SOURCE_HASHES["icons.theme"]})


if __name__ == "__main__":
    unittest.main()
