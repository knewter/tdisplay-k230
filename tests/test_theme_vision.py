"""Host tests for the vision option: a larger text step and a high-contrast
palette, saved beside the theme state and baked into every generation."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import theme_activate as activation  # noqa: E402
import theme_catalog as catalog  # noqa: E402
import theme_helperd  # noqa: E402
import theme_vision  # noqa: E402
from theme_transaction import activate_generation  # noqa: E402


COLORS = ('background="#101820"\nforeground="#e0e5e8"\naccent="#778899"\n'
          'red="#dd5555"\ngreen="#55dd55"\nyellow="#dddd55"\n'
          'blue="#5555dd"\nmagenta="#dd55dd"\ncyan="#55dddd"\nmode="dark"\n')
LARGE = {"text_scale": "large", "contrast": "standard"}
HIGH = {"text_scale": "default", "contrast": "high"}


def theme(path):
    path.mkdir(parents=True)
    (path / "colors.toml").write_text(COLORS)
    (path / "backgrounds").mkdir()
    (path / "backgrounds/portrait.png").write_bytes(b"not decoded in this test")
    return path


class VisionPreference(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.state = Path(temporary.name)

    def test_nothing_saved_is_the_default_and_a_choice_round_trips(self):
        self.assertEqual(theme_vision.load(self.state), theme_vision.DEFAULT)
        theme_vision.save(self.state, LARGE)
        self.assertEqual(theme_vision.load(self.state), LARGE)
        self.assertEqual(json.loads((self.state / "vision.json").read_text()),
                         {"version": 1, **LARGE})

    def test_unknown_values_and_unsafe_files_are_refused(self):
        with self.assertRaises(theme_vision.VisionError):
            theme_vision.save(self.state, {"text_scale": "huge", "contrast": "standard"})
        self.assertFalse((self.state / "vision.json").exists())
        (self.state / "vision.json").write_text('{"version": 1, "text_scale": "large"}')
        with self.assertRaises(theme_vision.VisionError):
            theme_vision.load(self.state)
        (self.state / "vision.json").unlink()
        (self.state / "elsewhere.json").write_text(json.dumps({"version": 1, **LARGE}))
        (self.state / "vision.json").symlink_to(self.state / "elsewhere.json")
        with self.assertRaises(theme_vision.VisionError):
            theme_vision.load(self.state)

    def test_high_contrast_replaces_every_listed_colour_and_keeps_the_rest(self):
        self.assertEqual(theme_vision.palette_text(COLORS, theme_vision.DEFAULT), COLORS)
        text = theme_vision.palette_text(COLORS + 'hairline="#abcdef"\n', HIGH)
        self.assertIn('background = "#000000"', text)
        self.assertIn('foreground = "#ffffff"', text)
        self.assertNotIn("#101820", text)
        self.assertIn('hairline="#abcdef"', text)
        self.assertIn('mode="dark"', text)

    def test_the_four_text_steps_reach_two_hundred_percent(self):
        self.assertEqual(theme_vision.TEXT_SCALES,
                         {"default": 1.0, "large": 1.3, "larger": 1.6, "largest": 2.0})
        for name, value in theme_vision.TEXT_SCALES.items():
            choice = {"text_scale": name, "contrast": "standard"}
            self.assertEqual(theme_vision.tokens(choice)["text-scale"]["value"], value)

    def test_tokens_carry_the_text_step_and_contrast_for_both_renderers(self):
        self.assertEqual(theme_vision.tokens(LARGE), {
            "text-scale": {"kind": "number", "value": 1.3},
            "high-contrast": {"kind": "boolean", "value": False},
        })
        self.assertEqual(theme_vision.tokens(HIGH)["high-contrast"]["value"], True)


class VisionGeneration(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        self.theme, self.state = theme(base / "night"), base / "state"

    def prepare(self):
        return activation.prepare("night", source=self.theme, state_root=self.state,
                                  user_themes=self.state / "none", builtins=None,
                                  tools=activation.HOST_TOOLS)

    def sections(self, generation):
        return json.loads((generation / "appearance.json").read_text())["sections"]

    def test_the_default_choice_keeps_the_existing_generation_identity(self):
        before, _ = self.prepare()
        theme_vision.save(self.state, theme_vision.DEFAULT)
        again, report = self.prepare()
        self.assertEqual(before, again)
        self.assertEqual(report.get("vision", theme_vision.DEFAULT), theme_vision.DEFAULT)

    def test_larger_text_is_a_new_generation_with_the_accessibility_step(self):
        before, _ = self.prepare()
        self.assertEqual(self.sections(before)["accessibility"]["text-scale"]["value"], 1.0)
        theme_vision.save(self.state, LARGE)
        large, report = self.prepare()
        self.assertNotEqual(before, large)
        self.assertEqual(report["vision"], LARGE)
        self.assertEqual(self.sections(large)["accessibility"]["text-scale"]["value"], 1.3)
        self.assertEqual(report["palette"]["background"], self.prepare()[1]["palette"]["background"])
        self.assertEqual(self.prepare()[0], large)

    def test_high_contrast_swaps_the_palette_before_the_templates_run(self):
        theme_vision.save(self.state, HIGH)
        generation, report = self.prepare()
        self.assertTrue(self.sections(generation)["accessibility"]["high-contrast"]["value"])
        self.assertTrue(report["palette"]["background"].lower().startswith("#000000"))
        self.assertTrue(report["palette"]["foreground"].lower().startswith("#ffffff"))
        # The person's own theme source is untouched.
        self.assertIn("#101820", (self.theme / "colors.toml").read_text())


class VisionCatalogAction(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.user, self.state = self.base / "user", self.base / "state"
        theme(self.user / "night")

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        prefix = ["--user-themes", str(self.user), "--builtins", str(self.base / "none"),
                  "--overlays", str(self.base / "no-overlays"),
                  "--state-root", str(self.state), "--socket", str(self.base / "missing.sock")]
        before = set(threading.enumerate())
        with redirect_stdout(out), redirect_stderr(err):
            status = catalog.main(prefix + list(args))
        for thread in set(threading.enumerate()) - before:
            thread.join(timeout=10)
        return status, json.loads(out.getvalue() if status == 0 else err.getvalue())

    def committed(self):
        def commit(generation, **kwargs):
            activate_generation(generation, **kwargs, transport=lambda *_: None)
        return mock.patch.object(catalog, "activate_generation", side_effect=commit)

    def activate_night(self):
        _, listing = self.run_cli("list")
        entry = listing["themes"][0]["id"]
        _, preview = self.run_cli("preview", entry)
        with self.committed():
            status, result = self.run_cli("activate", entry, "--expected-generation",
                                          preview["generation"])
        self.assertEqual(status, 0, result)
        return entry, preview["generation"]

    def test_with_no_active_theme_the_choice_is_only_saved(self):
        status, result = self.run_cli("vision", "--text-scale", "large", "--contrast", "standard")
        self.assertEqual(status, 0, result)
        self.assertEqual(result, {"schema": 1, "vision": LARGE, "activated": False,
                                  "generation": None})
        self.assertEqual(self.run_cli("list")[1]["vision"], LARGE)

    def test_the_active_theme_is_reapplied_with_the_choice(self):
        entry, before = self.activate_night()
        self.assertEqual(self.run_cli("list")[1]["vision"], theme_vision.DEFAULT)
        with self.committed():
            status, result = self.run_cli("vision", "--text-scale", "default", "--contrast", "high")
        self.assertEqual(status, 0, result)
        self.assertTrue(result["activated"])
        self.assertEqual(result["vision"], HIGH)
        self.assertNotEqual(result["generation"], before)
        listing = self.run_cli("list")[1]
        self.assertEqual(listing["active"], {"id": entry, "generation": result["generation"]})
        self.assertEqual(listing["vision"], HIGH)

    def test_a_failed_reapply_restores_the_previous_choice(self):
        self.activate_night()
        # No receiver socket: the commit fails.
        status, result = self.run_cli("vision", "--text-scale", "large", "--contrast", "high")
        self.assertEqual(status, 1)
        self.assertFalse(result["activated"])
        self.assertEqual(theme_vision.load(self.state), theme_vision.DEFAULT)

    def test_unknown_options_are_refused_before_anything_is_saved(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            catalog.main(["--state-root", str(self.state), "vision",
                          "--text-scale", "huge", "--contrast", "high"])
        self.assertFalse((self.state / "vision.json").exists())


class VisionHelperRequest(unittest.TestCase):
    def test_the_daemon_passes_only_the_two_vision_flags(self):
        self.assertEqual(
            theme_helperd.request_argv(["--state-root", "/s"],
                                       {"action": "vision", "text_scale": "large",
                                        "contrast": "standard", "id": "ignored"}),
            ["--state-root", "/s", "vision", "--text-scale", "large", "--contrast", "standard"])
        for bad in ({"action": "vision", "text_scale": 2, "contrast": "high"},
                    {"action": "vision", "text_scale": "large"}):
            with self.assertRaises(ValueError):
                theme_helperd.request_argv([], bad)


if __name__ == "__main__":
    unittest.main()
