"""Host-only remembered wallpaper and ACK/rollback consistency checks."""

from pathlib import Path
from contextlib import redirect_stdout
import io
import json
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import theme_activate as activation  # noqa: E402
import theme_preferences as preferences  # noqa: E402
import theme_transaction as transaction  # noqa: E402

COLORS = ('background="#101820"\nforeground="#e0e5e8"\naccent="#778899"\n'
          'red="#dd5555"\ngreen="#55dd55"\nyellow="#dddd55"\n'
          'blue="#5555dd"\nmagenta="#dd55dd"\ncyan="#55dddd"\n')


def make_theme(path):
    path.mkdir()
    (path / "colors.toml").write_text(COLORS)
    (path / "backgrounds").mkdir()
    (path / "backgrounds/default.png").write_bytes(b"fixture only")
    (path / "backgrounds/second.jpg").write_bytes(b"fixture only")
    return path


class WallpaperMemory(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.state = self.root / "state"
        self.first = make_theme(self.root / "first")
        self.second = make_theme(self.root / "second")

    def prepare(self, source, background=None):
        return activation.prepare(source.name, source=source, state_root=self.state,
                                  user_themes=self.root / "none", builtins=None,
                                  tools=activation.HOST_TOOLS,
                                  background_choice=background)

    def commit(self, generation, report, *, explicit=False, transport=None):
        intent = preferences.SelectionIntent(self.state, Path(report["source"]),
                                             report["selected_background"],
                                             report["backgrounds"], explicit)
        transaction.activate_generation(
            generation, state_root=self.state, endpoint=self.root / "fake.sock",
            transport=transport or (lambda *_: None), preference=intent)

    def test_switch_away_back_and_restart_use_source_relative_choice(self):
        chosen, report = self.prepare(self.first, "backgrounds/second.jpg")
        self.commit(chosen, report, explicit=True)
        self.assertEqual(preferences.choice(self.state, self.first), "backgrounds/second.jpg")
        other, other_report = self.prepare(self.second)
        self.commit(other, other_report)
        self.assertEqual(transaction._pointer(self.state), other)
        again, remembered = self.prepare(self.first)
        self.assertEqual(again, chosen)
        self.assertEqual(remembered["selected_background"], "backgrounds/second.jpg")
        self.commit(again, remembered)
        self.assertEqual(transaction._pointer(self.state), chosen)
        # A new process reads only persisted state, not an in-memory cursor.
        self.assertEqual(preferences.choice(self.state, self.first), "backgrounds/second.jpg")
        self.assertEqual(preferences.choice(self.state, self.second), "backgrounds/default.png")

    def test_removed_asset_is_diagnosed_and_default_replaces_memory_only_after_ack(self):
        chosen, report = self.prepare(self.first, "backgrounds/second.jpg")
        self.commit(chosen, report, explicit=True)
        (self.first / "backgrounds/second.jpg").unlink()
        fallback, fallback_report = self.prepare(self.first)
        self.assertEqual(fallback_report["selected_background"], "backgrounds/default.png")
        self.assertIn("remembered background removed; using theme default",
                      fallback_report["unavailable"])
        self.assertEqual(preferences.choice(self.state, self.first), "backgrounds/second.jpg")
        self.commit(fallback, fallback_report)
        self.assertEqual(preferences.choice(self.state, self.first), "backgrounds/default.png")

    def test_cached_default_generation_still_reports_removed_memory_fallback(self):
        default, _ = self.prepare(self.first)
        chosen, report = self.prepare(self.first, "backgrounds/second.jpg")
        self.commit(chosen, report, explicit=True)
        (self.first / "backgrounds/second.jpg").unlink()
        # A source update can produce an already-prepared default generation.
        fallback, first_report = self.prepare(self.first)
        self.assertNotEqual(fallback, default)
        again, second_report = self.prepare(self.first)
        self.assertEqual(again, fallback)
        for prepared in (first_report, second_report):
            self.assertIn("remembered background removed; using theme default",
                          prepared["unavailable"])

    def test_source_update_keeps_relative_choice_in_new_generation(self):
        chosen, report = self.prepare(self.first, "backgrounds/second.jpg")
        self.commit(chosen, report, explicit=True)
        (self.first / "colors.toml").write_text(COLORS.replace("#101820", "#202830"))
        updated, updated_report = self.prepare(self.first)
        self.assertNotEqual(updated, chosen)
        self.assertEqual(updated_report["selected_background"], "backgrounds/second.jpg")
        self.commit(updated, updated_report)
        self.assertEqual(preferences.choice(self.state, self.first), "backgrounds/second.jpg")

    def test_compatible_command_uses_the_same_preference_store(self):
        output = io.StringIO()
        def commit(generation, **kwargs):
            transaction.activate_generation(generation, **kwargs, transport=lambda *_: None)
        argv = ["omarchy-theme-set", "first", "--source", str(self.first),
                "--state-root", str(self.state), "--tools", str(activation.HOST_TOOLS),
                "--background", "backgrounds/second.jpg", "--activate",
                "--socket", str(self.root / "fake.sock")]
        with mock.patch.object(sys, "argv", argv), mock.patch.object(
                activation, "activate_generation", side_effect=commit), redirect_stdout(output):
            activation.main()
        result = json.loads(output.getvalue())
        self.assertEqual(result["report"]["selected_background"], "backgrounds/second.jpg")
        self.assertEqual(preferences.choice(self.state, self.first), "backgrounds/second.jpg")
        _, remembered = self.prepare(self.first)
        self.assertEqual(remembered["selected_background"], "backgrounds/second.jpg")

    def test_preview_cancel_and_rejected_ack_do_not_change_memory(self):
        original, original_report = self.prepare(self.first)
        self.commit(original, original_report)
        candidate, report = self.prepare(self.first, "backgrounds/second.jpg")
        self.assertEqual(preferences.choice(self.state, self.first), "backgrounds/default.png")
        def reject(_endpoint, phase, _generation):
            if phase == "commit":
                raise transaction.TransactionError("injected ACK failure")
        with self.assertRaisesRegex(transaction.TransactionError, "previous generation restored"):
            self.commit(candidate, report, explicit=True, transport=reject)
        self.assertEqual(transaction._pointer(self.state), original)
        self.assertEqual(preferences.choice(self.state, self.first), "backgrounds/default.png")

    def test_preference_write_after_ack_failure_restores_pointer_and_memory(self):
        original, original_report = self.prepare(self.first)
        self.commit(original, original_report)
        candidate, report = self.prepare(self.first, "backgrounds/second.jpg")
        old_bytes = (self.state / preferences.FILENAME).read_bytes()
        real_publish = preferences._publish
        calls = 0
        def fail_after_replace(root, contents):
            nonlocal calls
            calls += 1
            real_publish(root, contents)
            if calls == 1:
                raise OSError("injected after-replace failure")
        with mock.patch.object(preferences, "_publish", side_effect=fail_after_replace):
            with self.assertRaisesRegex(transaction.TransactionError, "previous generation restored"):
                self.commit(candidate, report, explicit=True)
        self.assertEqual(transaction._pointer(self.state), original)
        self.assertEqual((self.state / preferences.FILENAME).read_bytes(), old_bytes)

    def test_concurrent_explicit_activation_invalidates_older_implicit_preview(self):
        original, original_report = self.prepare(self.first)
        self.commit(original, original_report)
        stale, stale_report = self.prepare(self.first)
        chosen, chosen_report = self.prepare(self.first, "backgrounds/second.jpg")
        entered = threading.Event()
        release = threading.Event()
        outcomes = []
        def paused_ack(_endpoint, phase, _generation):
            if phase == "prepare":
                entered.set()
                if not release.wait(2):
                    raise RuntimeError("fixture timeout")
        def explicit_worker():
            try:
                self.commit(chosen, chosen_report, explicit=True, transport=paused_ack)
                outcomes.append("explicit-ok")
            except Exception as error:
                outcomes.append(f"explicit-{error}")
        def implicit_worker():
            try:
                self.commit(stale, stale_report)
                outcomes.append("implicit-ok")
            except preferences.PreferenceError:
                outcomes.append("implicit-stale")
        first = threading.Thread(target=explicit_worker)
        second = threading.Thread(target=implicit_worker)
        first.start()
        self.assertTrue(entered.wait(2))
        second.start()
        time.sleep(0.03)
        release.set()
        first.join(3); second.join(3)
        self.assertFalse(first.is_alive() or second.is_alive())
        self.assertCountEqual(outcomes, ["explicit-ok", "implicit-stale"])
        self.assertEqual(transaction._pointer(self.state), chosen)
        self.assertEqual(preferences.choice(self.state, self.first), "backgrounds/second.jpg")

    def test_refuses_foreign_preference_symlink(self):
        self.state.mkdir()
        foreign = self.root / "foreign.json"
        foreign.write_text(json.dumps({"version": 1, "choices": {}}))
        (self.state / preferences.FILENAME).symlink_to(foreign)
        with self.assertRaisesRegex(preferences.PreferenceError, "unsafe"):
            self.prepare(self.first)
        self.assertTrue((self.state / preferences.FILENAME).is_symlink())


if __name__ == "__main__":
    unittest.main()
