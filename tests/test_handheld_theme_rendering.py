"""Generated shell-token checks; physical scene captures remain a separate gate."""

from pathlib import Path
import json
import argparse
import subprocess
import re
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from theme_tokens import TokenError, compile_tokens, system_surface_coverage, SYSTEM_ROLES  # noqa: E402
from theme_field_inventory import field_status, inventory  # noqa: E402
import theme_activate as activation  # noqa: E402


class ThemeTokenRendering(unittest.TestCase):
    def test_every_active_upstream_shell_field_has_an_explicit_consumer_status(self):
        rows = inventory()
        self.assertEqual(len(rows), 102)
        self.assertTrue(all(row["status"] in {"applied", "adapted", "unavailable"}
                            for row in rows),
                        "new upstream fields must be classified before coverage is claimed")
        self.assertEqual(len({row["field"] for row in rows}), len(rows))
        self.assertIn({"field": "font.base-size", "status": "adapted",
                       "owner": "Rust Settings labels scale design sizes by base-size (defaults to 12), clamped per label to 11–24px."}, rows)
        self.assertTrue(any(row["field"] == "controls.focus-color" and
                            row["status"] == "unavailable" for row in rows))
        self.assertIsNone(field_status("launcher", "backgroun"), "misspelled roles must not be accepted")
        self.assertIsNone(field_status("launcher", "new-role"), "new roles need explicit review")
        self.assertEqual(field_status("image-picker", "selected-border")[0], "unavailable")

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


class SystemSurfaceCoverage(unittest.TestCase):
    def test_generated_system_roles_are_named_and_unsupported_states_are_unavailable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            (source / "colors.toml").write_text('background="#101820"\nforeground="#e0e5e8"\naccent="#778899"\n')
            generation, report = activation.prepare(
                "system", source=source, state_root=root / "state",
                user_themes=root / "none", builtins=None, tools=activation.HOST_TOOLS)
            payload = json.loads((generation / "appearance.json").read_text())
            coverage = system_surface_coverage(payload)
            for section, roles in SYSTEM_ROLES.items():
                for role in roles:
                    self.assertIn(role, payload["sections"][section])
            # Every authored system token has exactly one named status.
            for section in ("controls", "notifications"):
                for key in payload["sections"][section]:
                    prefix = f"{section}.{key}:"
                    found = [category for category, rows in coverage.items()
                             for row in rows if row.startswith(prefix)]
                    self.assertEqual(len(found), 1, prefix)
                    self.assertTrue(any(row.startswith(prefix) for row in report[found[0]]))
            self.assertTrue(any(row.startswith("controls.hover-cursor-color:")
                                for row in report["unavailable"]))
            self.assertTrue(any(row.startswith("notifications.border:")
                                for row in report["unavailable"]))
            self.assertTrue(any(row.startswith("notifications.text:")
                                for row in report["adapted"]))

    def test_missing_and_unknown_roles_are_not_advertised_as_painted(self):
        payload = compile_tokens({"controls": {"future-effect": "sparkle"}})
        coverage = system_surface_coverage(payload)
        self.assertTrue(any(row.startswith("controls.normal-color:") for row in coverage["unavailable"]))
        self.assertTrue(any(row.startswith("controls.future-effect:") for row in coverage["unknown"]))
        self.assertFalse(any(row.startswith("controls.future-effect:") for row in coverage["applied"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--surface", choices=("system",))
    args, remaining = parser.parse_known_args()
    program = unittest.main(argv=[sys.argv[0], *remaining], exit=False)
    if not program.result.wasSuccessful():
        return 1
    if args.surface == "system":
        # This deliberately fails when the actual renderer cannot build/run.
        # Merely generating tokens or inspecting source is insufficient proof.
        command = ["cargo", "test", "--offline", "--manifest-path",
                   str(ROOT / "nix/rust-shell-client/Cargo.toml"), "--lib",
                   "system_theme_", "--", "--nocapture"]
        try:
            result = subprocess.run(command, check=False, capture_output=True, text=True)
            print(result.stdout, end="")
            print(result.stderr, end="", file=sys.stderr)
            if result.returncode:
                return result.returncode
            match = re.search(r"test result: ok\. (\d+) passed", result.stdout)
            if not match or int(match[1]) < 2:
                print("actual system renderer checks did not execute", file=sys.stderr)
                return 1
            return 0
        except OSError as error:
            print(f"actual system renderer check unavailable: {error}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
