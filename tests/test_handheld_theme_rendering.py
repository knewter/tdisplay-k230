"""Generated shell-token checks; physical scene captures remain a separate gate."""

from pathlib import Path
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from theme_tokens import TokenError, compile_tokens  # noqa: E402
import theme_activate as activation  # noqa: E402


class ThemeTokenRendering(unittest.TestCase):
    def test_gradient_reference_alpha_and_per_side_widths(self):
        source = {
            "hyprland": {"active-border": "rgba(10, 20, 30, .5) #112233 45deg"},
            "launcher": {"border": "hyprland.active-border", "border-alpha": 0.4,
                         "border-width": "1 2 3 4", "border-width-left": 5},
        }
        tokens = compile_tokens(source)["sections"]["launcher"]
        self.assertEqual(tokens["border"]["stops"], [
            {"argb": "#800a141e", "offset": 0.0},
            {"argb": "#ff112233", "offset": 1.0},
        ])
        self.assertEqual(tokens["border"]["angle_degrees"], 45)
        self.assertEqual(tokens["border"]["alpha"], 0.4)
        self.assertEqual(tokens["border-width"]["value"], [1, 2, 3, 5])

    def test_hyprland_hex_gradient_and_bare_rgb_are_distinct_from_css_decimal_form(self):
        # Built-in Omarchy themes hackerman/last-horizon/solitude spell
        # hyprland_active_border/hyprland_inactive_border as a compact hex
        # rgba(RRGGBBAA)/rgb(RRGGBB) run, not the CSS decimal rgba(r, g, b, a)
        # form covered above. Both must resolve, and a length that does not
        # match its own prefix must still fail closed.
        source = {
            "hyprland": {"active-border": "rgba(26a269ee) rgba(2ec27eee) 45deg",
                         "inactive-border": "rgb(1e1e1e)"},
        }
        tokens = compile_tokens(source)["sections"]["hyprland"]
        self.assertEqual(tokens["active-border"]["stops"], [
            {"argb": "#ee26a269", "offset": 0.0},
            {"argb": "#ee2ec27e", "offset": 1.0},
        ])
        self.assertEqual(tokens["active-border"]["angle_degrees"], 45)
        self.assertEqual(tokens["inactive-border"]["stops"],
                         [{"argb": "#ff1e1e1e", "offset": 0.0}])
        for bad in ("rgba(1e1e1e)", "rgb(26a269ee)", "rgba(26a269)"):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(TokenError, "invalid color"):
                    compile_tokens({"hyprland": {"active-border": bad}})

    def test_cycle_missing_reference_and_invalid_alpha_fail_closed(self):
        for source, problem in (
            ({"launcher": {"border": "menu.border"}, "menu": {"border": "launcher.border"}}, "cycle"),
            ({"launcher": {"border": "menu.missing"}}, "missing appearance reference"),
            ({"launcher": {"background": "#112233", "background-alpha": 1.2}}, "out of range"),
            ({"launcher": {"border-width": "1 2 3 4 5"}}, "width arity"),
            ({"other": 3, "launcher": {"background": "other.value"}}, "invalid shell section"),
        ):
            with self.subTest(problem=problem):
                with self.assertRaisesRegex(TokenError, problem):
                    compile_tokens(source)

    def test_real_helper_output_becomes_bounded_native_payload(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            (source / "colors.toml").write_text(
                'background = "#101820"\nforeground = "#e0e5e8"\n'
                'accent = "#778899"\nred = "#dd5555"\n')
            generation, report = activation.prepare(
                "sample", source=source, state_root=root / "state",
                user_themes=root / "none", builtins=None, tools=activation.HOST_TOOLS)
            payload = json.loads((generation / "appearance.json").read_text())
            self.assertEqual(payload["generation"], report["generation"])
            self.assertEqual(payload["version"], 1)
            self.assertIn("launcher", payload["sections"])
            self.assertIn("notifications", payload["sections"])
            self.assertIn("controls", payload["sections"])
            self.assertEqual(payload["sections"]["launcher"]["background"]["stops"][0]["argb"],
                             "#ff101820")
            self.assertLess((generation / "appearance.json").stat().st_size, 256 * 1024)
            self.assertEqual((source / "colors.toml").read_text().splitlines()[0],
                             'background = "#101820"')


if __name__ == "__main__":
    unittest.main()
