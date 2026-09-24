"""Differentially exercise pinned Omarchy palette and template semantics."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "nix/omarchy-theme-tools/upstream"
COLOR = TOOLS / "bin/omarchy-theme-color"
TEMPLATES = TOOLS / "bin/omarchy-theme-set-templates"


def palette(text, *, marker=False):
    with tempfile.TemporaryDirectory() as temp:
        directory = Path(temp)
        source = directory / "colors.toml"
        source.write_text(text)
        if marker:
            (directory / "light.mode").touch()
        result = subprocess.check_output(["bash", str(COLOR), "--file", str(source), "--all"], text=True)
        return dict(line.split("\t", 1) for line in result.splitlines())


def generate(colors, *, full_shell=None, section=None, user_template=None):
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        stage, user = base / "stage", base / "user"
        stage.mkdir()
        user.mkdir()
        (stage / "colors.toml").write_text(colors)
        if full_shell is not None:
            (stage / "shell.toml").write_text(full_shell)
        if section is not None:
            (stage / "shell.menu.toml").write_text(section)
        if user_template is not None:
            (user / "probe.txt.tpl").write_text(user_template)
        env = os.environ | {
            "OMARCHY_THEME_TEMPLATES_DIR": str(TOOLS / "default/themed"),
            "OMARCHY_THEME_USER_TEMPLATES_DIR": str(user),
            "OMARCHY_THEME_STAGING_DIR": str(stage),
            "PATH": str(TOOLS / "bin") + os.pathsep + os.environ["PATH"],
        }
        subprocess.run(["bash", str(TEMPLATES)], env=env, check=True)
        return {p.name: p.read_text() for p in stage.iterdir() if p.is_file()}


class OmarchyResolution(unittest.TestCase):
    BASE = ('background = "#101820"\nforeground = "#e0e5e8"\n'
            'accent = "#808080"\nred = "#d86666"\nblue = "#6389d8"\n'
            'magenta = "#aabbcc"\n')

    def test_explicit_ansi_selection_custom_and_aliases(self):
        values = palette(self.BASE + 'color4 = "#112233"\n'
                         'selection_foreground = "#ffcc00"\nhairline = "#123456"\nmode = "dark"\n')
        self.assertEqual(values["blue"], "#6389d8")
        self.assertEqual(values["color4"], "#112233")
        self.assertEqual(values["selection_foreground"], "#ffcc00")
        self.assertEqual(values["hairline"], "#123456")
        self.assertEqual(values["purple"], "#aabbcc")
        self.assertEqual(values["bg"], values["background"])

    def test_mode_precedence_and_luminance_fallback(self):
        self.assertEqual(palette(self.BASE + 'mode = "dark"\ntheme_type = "light"\n', marker=True)["mode"], "dark")
        self.assertEqual(palette(self.BASE + 'theme_type = "light"\n')["mode"], "light")
        self.assertEqual(palette(self.BASE, marker=True)["mode"], "light")
        self.assertEqual(palette(self.BASE)["mode"], "dark")
        self.assertEqual(palette('background = "#ffffff"\nforeground = "#000000"\n')["mode"], "light")

    def test_mix_gradient_and_full_file_section_precedence(self):
        colors = self.BASE + 'hyprland_active_border = "accent background 45deg"\n'
        generated = generate(colors, full_shell='[menu]\nold = 1\n[launcher]\nkept = 2\n',
                             section='[menu]\nnew = "#334455"\n',
                             user_template=('accent={{ accent }}\nstrip={{ accent_strip }}\n'
                                            'rgb={{ accent_rgb }}\nmix={{ mix accent background 50% }}\n'
                                            'gradient={{ shell_gradient hyprland_active_border accent }}\n'))
        shell = generated["shell.toml"]
        self.assertNotIn("old = 1", shell)
        self.assertIn('new = "#334455"', shell)
        self.assertIn("[launcher]\nkept = 2", shell)
        probe = generated["probe.txt"]
        self.assertIn("accent=#808080", probe)
        self.assertIn("strip=808080", probe)
        self.assertIn("rgb=128,128,128", probe)
        self.assertIn("mix=#484c50", probe)
        self.assertIn("gradient=#808080 #101820 45deg", probe)

    def test_theme_full_file_wins_template_and_section_replaces_generated(self):
        colors = self.BASE
        defaulted = generate(colors, section='background = "#123456"\n')
        self.assertIn('[menu]', defaulted["shell.toml"])
        self.assertIn('background = "#123456"', defaulted["shell.toml"])
        self.assertEqual(defaulted["shell.toml"].splitlines().count('[menu]'), 1)
        explicit = generate(colors, full_shell='[menu]\nbackground = "#111111"\n',
                            section='background = "#222222"\n')
        self.assertIn('background = "#222222"', explicit["shell.toml"])
        self.assertNotIn('background = "#111111"', explicit["shell.toml"])


if __name__ == "__main__":
    unittest.main()
