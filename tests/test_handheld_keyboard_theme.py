"""Host checks for generated wvkbd colour flags and restart triggering.

No panel, touch, or focus-preservation claim: those need the reserved board.
"""

import fcntl
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import keyboard_appearance as kbd  # noqa: E402
import theme_activate  # noqa: E402
import theme_transaction as tx  # noqa: E402


COLORS = ('background="#101820"\nforeground="#e0e5e8"\naccent="#778899"\n'
          'red="#dd5555"\ngreen="#55dd55"\nyellow="#dddd55"\n'
          'blue="#5555dd"\nmagenta="#dd55dd"\ncyan="#55dddd"\n'
          'color1="#123456"\nmode="dark"\n')


def prepared(base: Path):
    source = base / "source"
    source.mkdir()
    (source / "colors.toml").write_text(COLORS)
    state = base / "state"
    generation, _ = theme_activate.prepare(
        "test", source=source, state_root=state, user_themes=base / "missing",
        builtins=None, tools=theme_activate.HOST_TOOLS)
    return source, state, generation


def fake_pkill(returncode: int, log: Path):
    """A tiny script standing in for procps' pkill, recording its argv."""
    script = log.parent / "pkill"
    script.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$@\" >> {log}\n"
        f"exit {returncode}\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


class KeyboardAppearance(unittest.TestCase):
    def test_colors_resolves_exactly_the_seven_wvkbd_roles(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, generation = prepared(Path(temporary))
            resolved = kbd.colors(generation)
            self.assertEqual(set(resolved), {flag for flag, _ in kbd.ROLES})
            self.assertEqual(resolved["bg"], "#101820")
            self.assertEqual(resolved["text"], "#e0e5e8")

    def test_args_file_is_fourteen_lines_without_hash_prefixes(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, generation = prepared(Path(temporary))
            content = kbd.args_file(kbd.colors(generation))
            lines = content.splitlines()
            self.assertEqual(len(lines), 14)
            self.assertEqual(lines[0], "--bg")
            self.assertEqual(lines[1], "101820")
            self.assertNotIn("#", content)

    def test_prepare_is_idempotent_and_rejects_foreign_generation(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            _, state, generation = prepared(base)
            target = kbd.prepare(generation, state)
            self.assertEqual(kbd.prepare(generation, state), target)
            args = (target / "wvkbd.args").read_text()
            self.assertEqual(args, kbd.args_file(kbd.colors(generation)))
            coverage = json.loads((target / "coverage.json").read_text())
            self.assertTrue(any("wvkbd" in item for item in coverage["applied"]))

            foreign = base / ("a" * 24)
            foreign.mkdir()
            (foreign / "report.json").write_bytes((generation / "report.json").read_bytes())
            with self.assertRaisesRegex(kbd.KeyboardAppearanceError, "outside theme cache"):
                kbd.prepare(foreign, state)

    def test_prepare_rejects_invalid_resolved_color(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, state, generation = prepared(Path(temporary))
            report = json.loads((generation / "report.json").read_text())
            report["palette"]["dark_background"] = "not-a-color"
            (generation / "report.json").write_text(json.dumps(report))
            with self.assertRaisesRegex(kbd.KeyboardAppearanceError, "invalid resolved color"):
                kbd.prepare(generation, state)

    def test_sync_tracks_only_acknowledged_pointer_and_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, state, generation = prepared(Path(temporary))
            with self.assertRaisesRegex(kbd.KeyboardAppearanceError, "no acknowledged"):
                kbd.sync(state)
            (state / "active").symlink_to(generation)
            target, changed, theme_generation = kbd.sync(state)
            self.assertTrue(changed)
            self.assertEqual(theme_generation, generation.name)
            self.assertEqual((state / "keyboard-appearance/active").resolve(), target)
            target2, changed2, _ = kbd.sync(state)
            self.assertEqual(target2, target)
            self.assertFalse(changed2)

    def test_sync_rejects_foreign_pointer(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            _, state, generation = prepared(base)
            (state / "active").symlink_to(generation)
            kbd.sync(state)
            (state / "keyboard-appearance/active").unlink()
            (state / "keyboard-appearance/active").symlink_to(base / "outside")
            with self.assertRaisesRegex(kbd.KeyboardAppearanceError, "foreign"):
                kbd.sync(state)

    def test_sync_supersession_never_publishes_stale_generation(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            _, state, first = prepared(base)
            other = state / "generations" / ("b" * 24)
            other.mkdir()
            second_report = json.loads((first / "report.json").read_text())
            second_report["generation"] = other.name
            (other / "report.json").write_text(json.dumps(second_report))
            (state / "active").symlink_to(other)
            with self.assertRaisesRegex(kbd.KeyboardAppearanceSuperseded, "newer generation"):
                kbd.sync(state, expected_generation=first.name)
            self.assertFalse((state / "keyboard-appearance/active").exists())

    def test_sync_wait_is_bounded_by_activation_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, state, generation = prepared(Path(temporary))
            (state / "active").symlink_to(generation)
            with (state / ".activation.lock").open("w") as held:
                fcntl.flock(held, fcntl.LOCK_EX)
                with self.assertRaisesRegex(kbd.KeyboardAppearanceError, "lock timed out"):
                    kbd.sync(state, lock_timeout=0.02)
            self.assertFalse((state / "keyboard-appearance/active").exists())

    def test_restart_skips_unsupervised_keyboard(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary)
            log = runtime / "pkill.log"
            script = fake_pkill(0, log)
            outcome = kbd.restart(runtime, pkill_path=str(script))
            self.assertEqual(outcome, {"restarted": False, "reason": "not-supervised"})
            self.assertFalse(log.exists())

    def test_restart_signals_only_when_sentinel_present(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary)
            (runtime / "k230-keyboard-supervised").write_text("1")
            log = runtime / "pkill.log"
            script = fake_pkill(0, log)
            outcome = kbd.restart(runtime, pkill_path=str(script))
            self.assertEqual(outcome, {"restarted": True})
            recorded = log.read_text().splitlines()
            self.assertEqual(recorded, ["-TERM", "-u", str(os.getuid()), "-x", "wvkbd-mobintl"])

    def test_restart_not_running_is_not_an_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary)
            (runtime / "k230-keyboard-supervised").write_text("1")
            script = fake_pkill(1, runtime / "pkill.log")
            self.assertEqual(kbd.restart(runtime, pkill_path=str(script)),
                             {"restarted": False, "reason": "not-running"})

    def test_restart_raises_on_pkill_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary)
            (runtime / "k230-keyboard-supervised").write_text("1")
            script = fake_pkill(2, runtime / "pkill.log")
            with self.assertRaisesRegex(kbd.KeyboardAppearanceError, "pkill failed"):
                kbd.restart(runtime, pkill_path=str(script))

    def test_sync_and_restart_skips_restart_when_colours_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            _, state, generation = prepared(base)
            (state / "active").symlink_to(generation)
            runtime = base / "runtime"
            runtime.mkdir()
            (runtime / "k230-keyboard-supervised").write_text("1")
            log = runtime / "pkill.log"
            script = fake_pkill(0, log)
            first = kbd.sync_and_restart(state, runtime_dir=runtime, pkill_path=str(script))
            self.assertEqual(first, {"state": "applied", "generation": generation.name,
                                     "restarted": True})
            second = kbd.sync_and_restart(state, runtime_dir=runtime, pkill_path=str(script))
            self.assertEqual(second, {"state": "applied", "generation": generation.name,
                                      "restarted": False})
            self.assertEqual(len(log.read_text().splitlines()), 5)  # one pkill call only

    def test_sync_and_restart_reports_superseded_and_failure_without_raising(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            _, state, generation = prepared(base)
            (state / "active").symlink_to(generation)
            result = kbd.sync_and_restart(state, expected_generation="0" * 24)
            self.assertEqual(result, {"state": "superseded", "error": "newer-generation-active"})

            broken = base / "missing-state"
            failed = kbd.sync_and_restart(broken)
            self.assertEqual(failed["state"], "failed")
            self.assertEqual(failed["error"], "keyboard-sync-failed")

    def test_full_activation_publishes_keyboard_colours_and_restarts(self):
        """theme_activate.py's --activate path calls keyboard sync after the
        shell ack, independent of app_appearance, exactly like the existing
        app_appearance post-commit convention."""
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source"
            source.mkdir()
            (source / "colors.toml").write_text(COLORS)
            state = base / "state"
            runtime = base / "runtime"
            runtime.mkdir()
            (runtime / "k230-keyboard-supervised").write_text("1")
            log = runtime / "pkill.log"
            script = fake_pkill(0, log)

            def ack(_endpoint, phase, _generation):
                pass

            generation, report = theme_activate.prepare(
                "test", source=source, state_root=state, user_themes=base / "missing",
                builtins=None, tools=theme_activate.HOST_TOOLS)
            shell_status = tx.activate_generation(generation, state_root=state,
                                                  endpoint=state / "unused.sock", transport=ack)
            self.assertEqual(shell_status["state"], "applied")
            keyboard_status = kbd.sync_and_restart(state, expected_generation=generation.name,
                                                   runtime_dir=runtime, pkill_path=str(script))
            self.assertEqual(keyboard_status, {"state": "applied", "generation": generation.name,
                                               "restarted": True})
            published = (state / "keyboard-appearance/active/wvkbd.args").read_text()
            self.assertEqual(published, kbd.args_file(kbd.colors(generation)))


if __name__ == "__main__":
    unittest.main()
