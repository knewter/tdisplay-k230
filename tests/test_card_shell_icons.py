#!/usr/bin/env python3
"""Exercise card-shell's production icon inheritance and theme switch on host."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CardShellIcons(unittest.TestCase):
    def test_selected_theme_local_asset_inheritance_and_switch(self):
        with tempfile.TemporaryDirectory(prefix="card-shell-icons-",
                                         dir=os.environ.get("TMPDIR")) as temp:
            root = Path(temp)
            include = root / "include/sway"
            include.mkdir(parents=True)
            (include / "card_shell_icon.h").symlink_to(ROOT / "nix/card-shell/icon.h")
            build = root / "probe"
            flags = shlex.split(subprocess.check_output(
                ["pkg-config", "--cflags", "--libs", "cairo", "librsvg-2.0"],
                text=True))
            subprocess.run([
                "cc", "-std=c11", "-D_POSIX_C_SOURCE=200809L", "-Wall", "-Wextra", "-Werror",
                "-I", str(root / "include"), str(ROOT / "nix/card-shell/icon.c"),
                str(ROOT / "tests/fixtures/card_shell_icon_probe.c"), *flags,
                "-lm", "-o", str(build),
            ], check=True)

            icons = root / "share/icons"
            for name in ("ThemeA", "ThemeB", "Base"):
                directory = icons / name / "scalable/apps"
                directory.mkdir(parents=True)
                (icons / name / "index.theme").write_text(
                    "[Icon Theme]\nName=" + name +
                    "\nDirectories=scalable/apps\n" +
                    ("Inherits=Base\n" if name == "ThemeA" else "") +
                    "[scalable/apps]\nSize=48\nType=Scalable\nMinSize=16\nMaxSize=128\n")
            (icons / "ThemeA/scalable/apps/marker.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48">'
                '<rect width="48" height="48" fill="#20b050"/></svg>')
            (icons / "ThemeB/scalable/apps/marker.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48">'
                '<rect width="48" height="48" fill="#2850e0"/></svg>')
            (icons / "Base/scalable/apps/inherited-marker.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48">'
                '<rect width="48" height="48" fill="#dd4422"/></svg>')
            env = dict(os.environ, XDG_DATA_HOME="", XDG_DATA_DIRS=str(root / "share"))
            result = subprocess.run([str(build)], env=env, check=False,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("PASS: card icon theme selection", result.stdout)


if __name__ == "__main__":
    unittest.main()
