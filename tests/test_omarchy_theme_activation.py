"""Host preparation checks; no shell receiver or physical activation is claimed."""

from pathlib import Path
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import theme_activate as activation  # noqa: E402


COLORS = ('background="#101820"\nforeground="#e0e5e8"\naccent="#778899"\n'
          'red="#dd5555"\ngreen="#55dd55"\nyellow="#dddd55"\n'
          'blue="#5555dd"\nmagenta="#dd55dd"\ncyan="#55dddd"\nmode="dark"\n')


def source(path):
    path.mkdir()
    (path / "colors.toml").write_text(COLORS + 'hairline="#abcdef"\n')
    (path / "icons.theme").write_text("Yaru-blue\n")
    (path / "shell.menu.toml").write_text('[menu]\nbackground = "#123456"\n')
    (path / "backgrounds").mkdir()
    (path / "backgrounds" / "portrait.png").write_bytes(b"not decoded during prepare")
    (path / "README.md").write_text("Unchanged source\n")


def call(name, theme, state, *, background_choice=None):
    return activation.prepare(name, source=theme, state_root=state,
                              user_themes=state / "no-user-themes", builtins=None,
                              tools=activation.HOST_TOOLS,
                              background_choice=background_choice)


class ThemePreparation(unittest.TestCase):
    def test_direct_source_is_unchanged_and_generated_outputs_are_curated(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            theme, state = base / "theme", base / "state"
            source(theme)
            before = activation.source_digest(theme)
            generation, report = call("Fuchsblau", theme, state)
            self.assertEqual(before, activation.source_digest(theme))
            self.assertEqual(report["source_sha256"], before)
            self.assertEqual(report["name"], "fuchsblau")
            self.assertEqual(report["icon_theme"], "Yaru-blue")
            self.assertIn("palette.hairline: preserved; no current role mapping", report["unknown"])
            self.assertIn("README.md: not an appearance input", report["unknown"])
            self.assertEqual(report["backgrounds"], ["backgrounds/portrait.png"])
            self.assertEqual((generation / "background").readlink().as_posix(), "theme/backgrounds/portrait.png")
            self.assertIn('background = "#123456"', (generation / "theme/shell.toml").read_text())
            self.assertEqual(sorted(path.name for path in (generation / "theme").iterdir()),
                             ["backgrounds", "colors.toml", "foot.ini", "icons.theme",
                              "shell.menu.toml", "shell.toml"])
            again, _ = call("Fuchsblau", theme, state)
            self.assertEqual(again, generation)

    def test_concurrent_identical_preparation_is_adopted_not_failed(self):
        # Chooser prepare-ahead, the helper daemon and a client fallback can
        # prepare the same theme at once; the slow wallpaper-cache build sits
        # between the existence check and the publish. The loser must adopt
        # the winner's identical generation instead of failing with ENOTEMPTY.
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            theme, state = base / "theme", base / "state"
            source(theme)
            original = activation.build_wallpaper_cache
            raced = {}

            def concurrent_winner(tool, background, work):
                if not raced:
                    raced["generation"], _ = call("Fuchsblau", theme, state)
            activation.build_wallpaper_cache = concurrent_winner
            try:
                generation, report = activation.prepare(
                    "Fuchsblau", source=theme, state_root=state,
                    user_themes=state / "no-user-themes", builtins=None,
                    tools=activation.HOST_TOOLS, wallpaper_cache_tool=Path("/nonexistent"))
            finally:
                activation.build_wallpaper_cache = original
            self.assertEqual(generation, raced["generation"])
            self.assertEqual(report["name"], "fuchsblau")
            self.assertFalse([p for p in generation.parent.iterdir() if p.name.startswith(".prepare-")])

    def test_legacy_palette_is_converted_only_in_scratch(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            theme, state = base / "legacy", base / "state"
            theme.mkdir()
            (theme / "alacritty.toml").write_text(
                '[colors.primary]\nbackground = "#101820"\nforeground = "#e0e5e8"\n'
                '[colors.normal]\nblack = "#101820"\nred = "#dd5555"\n'
                'green = "#55dd55"\nyellow = "#dddd55"\nblue = "#5555dd"\n'
                'magenta = "#dd55dd"\ncyan = "#55dddd"\nwhite = "#e0e5e8"\n'
            )
            before = activation.source_digest(theme)
            generation, report = call("Legacy", theme, state)
            self.assertEqual(before, activation.source_digest(theme))
            self.assertFalse((theme / "colors.toml").exists())
            self.assertFalse((generation / "theme/alacritty.toml").exists())
            self.assertIn("colors.toml: legacy scratch conversion", report["applied"])
            self.assertIn('background = "#101820"', (generation / "theme/colors.toml").read_text())

    def test_explicit_background_choice_is_validated_and_changes_generation(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            theme, state = base / "theme", base / "state"
            source(theme)
            (theme / "backgrounds" / "second.jpg").write_bytes(b"host still fixture")
            (theme / "backgrounds" / "a-video.mp4").write_bytes(b"host video fixture")
            original = activation.source_digest(theme)
            default, default_report = call("theme", theme, state)
            self.assertEqual(default_report["selected_background"], "backgrounds/portrait.png")
            chosen, report = call("theme", theme, state,
                                  background_choice="backgrounds/second.jpg")
            self.assertNotEqual(chosen, default)
            self.assertEqual(report["selected_background"], "backgrounds/second.jpg")
            self.assertEqual((chosen / "background").readlink().as_posix(),
                             "theme/backgrounds/second.jpg")
            self.assertEqual(json.loads((chosen / "appearance.json").read_text())["background"],
                             "background")
            video, _ = call("theme", theme, state,
                            background_choice="backgrounds/a-video.mp4")
            self.assertIsNone(json.loads((video / "appearance.json").read_text())["background"])
            self.assertNotEqual(video, chosen)
            with self.assertRaisesRegex(activation.ThemeError, "not a staged theme asset"):
                call("theme", theme, state, background_choice="../elsewhere.png")
            with self.assertRaisesRegex(activation.ThemeError, "not a staged theme asset"):
                call("theme", theme, state, background_choice="backgrounds/missing.png")
            self.assertEqual(activation.source_digest(theme), original)

    def test_rejects_escape_malformed_palette_and_oversized_input(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            theme, state = base / "theme", base / "state"
            source(theme)
            with self.assertRaisesRegex(activation.ThemeError, "invalid theme name"):
                call("../escape", theme, state)
            (theme / "bad").symlink_to(base)
            with self.assertRaisesRegex(ValueError, "symlink"):
                call("safe", theme, state)
            (theme / "bad").unlink()
            (theme / "colors.toml").write_text('background = "broken\n')
            with self.assertRaisesRegex(activation.ThemeError, "invalid palette"):
                call("safe", theme, state)
            (theme / "colors.toml").write_text(COLORS)
            oversized = theme / "backgrounds" / "huge.mp4"
            with oversized.open("wb") as stream:
                stream.truncate(activation.MAX_ASSET + 1)
            with self.assertRaisesRegex(ValueError, "source bytes exceed bound"):
                call("safe", theme, state)
            self.assertEqual(list((state / "generations").glob("[0-9a-f]*")), [])

    def test_changed_source_creates_new_generation_without_erasing_old(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            theme, state = base / "theme", base / "state"
            source(theme)
            old, _ = call("theme", theme, state)
            (theme / "colors.toml").write_text(COLORS.replace("#101820", "#202830"))
            new, _ = call("theme", theme, state)
            self.assertNotEqual(old, new)
            self.assertTrue((old / "theme/colors.toml").is_file())
            theme.rename(base / "removed")
            self.assertTrue((new / "theme/colors.toml").is_file())

    def test_helper_update_and_same_bytes_new_clone_invalidate_generation(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            theme, state = base / "theme", base / "state"
            source(theme)
            first, _ = call("theme", theme, state)
            clone = base / "same-bytes-clone"
            shutil.copytree(theme, clone)
            second, second_report = call("theme", clone, state)
            self.assertNotEqual(first, second)
            self.assertEqual(second_report["source"], str(clone))
            tools = base / "updated-trusted-tools"
            shutil.copytree(activation.HOST_TOOLS, tools)
            template = tools / "default/themed/shell.toml.tpl"
            template.write_text(template.read_text() + "\n# Trusted template revision\n")
            third, third_report = activation.prepare(
                "theme", source=clone, state_root=state, user_themes=state / "none",
                builtins=None, tools=tools)
            self.assertNotEqual(second, third)
            self.assertNotEqual(second_report["helper_sha256"], third_report["helper_sha256"])

    def test_source_changed_during_preparation_is_not_published(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            theme, state = base / "theme", base / "state"
            source(theme)
            original_invoke = activation.invoke
            changed = False

            def mutate_during_helper(*args, **kwargs):
                nonlocal changed
                if not changed:
                    (theme / "colors.toml").write_text(COLORS.replace("#101820", "#202830"))
                    changed = True
                return original_invoke(*args, **kwargs)

            with mock.patch.object(activation, "invoke", side_effect=mutate_during_helper):
                with self.assertRaisesRegex(activation.ThemeError, "changed during preparation"):
                    call("theme", theme, state)
            self.assertTrue(changed)
            self.assertEqual(list((state / "generations").glob("[0-9a-f]*")), [])

    def test_compatible_command_fails_closed_without_receiver(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            theme, state = base / "theme", base / "state"
            source(theme)
            command = [sys.executable, str(ROOT / "tools/omarchy-theme-set"), "theme",
                       "--source", str(theme), "--state-root", str(state),
                       "--socket", str(base / "missing.sock")]
            result = subprocess.run(command, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 1)
            self.assertIn("omarchy-theme-set:", result.stderr)
            self.assertFalse((state / "active").exists())
            prepared = subprocess.run(command + ["--prepare-only"], capture_output=True,
                                      text=True, timeout=20)
            self.assertEqual(prepared.returncode, 0, prepared.stderr)
            self.assertFalse((state / "active").exists())

    def test_selected_generation_and_public_paths_survive_removed_clone(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            theme, state = base / "theme", base / "state"
            source(theme)
            generation, _ = call("theme", theme, state)
            activation.activate_generation(generation, state_root=state,
                                           endpoint=base / "shell.sock",
                                           transport=lambda *args: None)
            theme.rename(base / "removed-clone")
            self.assertEqual((state / "theme.name").read_text(), "theme\n")
            self.assertEqual((state / "theme/colors.toml").read_text(),
                             (generation / "theme/colors.toml").read_text())
            self.assertEqual((state / "background").resolve(),
                             (generation / "theme/backgrounds/portrait.png").resolve())

    def test_repeated_preparation_of_an_existing_generation_skips_staging_and_helpers(self):
        # Board evidence (2026-09-24, `theme-helper.service` reachable):
        # `preview`/`activate` of an already-prepared catppuccin/-latte still
        # took 3.95-4.26 s each, because this function used to check whether
        # the destination already existed only at the very end, after
        # staging every asset again and re-invoking the external
        # omarchy-theme-* helpers -- all of it discarded once the check
        # finally ran. This proves the fast path now taken for an existing
        # generation touches neither `checked_copy` (no asset bytes are
        # copied) nor `invoke` (no external helper is spawned), and returns
        # the exact same report a full re-preparation would.
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            theme, state = base / "theme", base / "state"
            source(theme)
            first, first_report = call("theme", theme, state)
            with mock.patch.object(activation, "checked_copy",
                                   side_effect=AssertionError("must not stage on a cache hit")), \
                 mock.patch.object(activation, "invoke",
                                   side_effect=AssertionError("must not spawn a helper on a cache hit")):
                second, second_report = call("theme", theme, state)
            self.assertEqual(first, second)
            self.assertEqual(first_report, second_report)

    def test_repeated_preparation_reports_a_newly_missing_remembered_background(self):
        # The one field a cache hit still has to (cheaply) recompute rather
        # than trust verbatim from the on-disk report: whether *this*
        # request's remembered background choice is still one of the
        # generation's own assets, without mutating the shared, immutable,
        # on-disk report.json other callers may also be reading. `source()`
        # ships a single background (portrait.png), so a `None` remembered
        # choice and a *missing* remembered choice both fall back to the
        # exact same `selected_background` -- and therefore the exact same
        # (cached, content-addressed) generation -- letting this test change
        # only the remembered preference between the two calls, not the
        # theme content, and still land on the same generation both times.
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            theme, state = base / "theme", base / "state"
            state.mkdir()
            source(theme)
            first, first_report = call("theme", theme, state)
            self.assertEqual(first_report["selected_background"], "backgrounds/portrait.png")
            self.assertNotIn("remembered background removed; using theme default",
                            first_report["unavailable"])
            # Simulate a background remembered from a theme revision that no
            # longer exists (the theme itself is unchanged here, only the
            # remembered preference references an asset it never had).
            intent = activation.SelectionIntent(
                state, theme, "backgrounds/second.jpg",
                {"backgrounds/second.jpg"}, explicit=True)
            intent.guard()
            intent.commit()
            self.assertEqual(activation.remembered_choice(state, theme), "backgrounds/second.jpg")
            with mock.patch.object(activation, "invoke",
                                   side_effect=AssertionError("must not spawn a helper on a cache hit")):
                again, report = call("theme", theme, state)
            self.assertEqual(again, first)
            self.assertEqual(report["selected_background"], "backgrounds/portrait.png")
            self.assertIn("remembered background removed; using theme default",
                          report["unavailable"])
            on_disk = json.loads((first / "report.json").read_text())
            self.assertNotIn("remembered background removed; using theme default",
                             on_disk["unavailable"])


if __name__ == "__main__":
    unittest.main()
