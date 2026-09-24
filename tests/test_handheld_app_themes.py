"""Host checks for generated installed-app appearance; no panel claim."""

import json
import fcntl
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import app_appearance as app
import theme_activate
import theme_transaction as tx


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


class AppAppearance(unittest.TestCase):
    def test_preparation_preserves_source_and_explicit_ansi(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, state, generation = prepared(Path(temporary))
            before = theme_activate.source_digest(source)
            target = app.prepare(generation, state)
            self.assertEqual(before, theme_activate.source_digest(source))
            terminal = (target / "terminal-foot.ini").read_text()
            monitor = (target / "monitor-foot.ini").read_text()
            self.assertIn("app-id=k230-terminal", terminal)
            self.assertIn("app-id=k230-monitor", monitor)
            self.assertIn("regular1=123456", terminal)
            self.assertIn("[colors-light]", terminal)
            self.assertEqual(app.prepare(generation, state), target)
            coverage = json.loads((target / "coverage.json").read_text())
            self.assertEqual(coverage["inherited"], ["htop", "nano", "nnn"])
            self.assertTrue(any("mpv" in item for item in coverage["limited"]))

    def test_sync_tracks_only_acknowledged_pointer_and_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, state, generation = prepared(Path(temporary))
            with self.assertRaisesRegex(app.AppAppearanceError, "no acknowledged"):
                app.sync(state)
            (state / "active").symlink_to(generation)
            target = app.sync(state)
            self.assertEqual((state / "app-appearance/active").resolve(), target)
            (state / "app-appearance/active").unlink()
            (state / "app-appearance/active").symlink_to(Path(temporary) / "outside")
            with self.assertRaisesRegex(app.AppAppearanceError, "foreign"):
                app.sync(state)
            self.assertEqual(os.readlink(state / "app-appearance/active"), str(Path(temporary) / "outside"))

    def test_malformed_report_and_foreign_generation_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            _, state, generation = prepared(base)
            foreign = base / ("a" * 24)
            foreign.mkdir()
            (foreign / "report.json").write_bytes((generation / "report.json").read_bytes())
            with self.assertRaisesRegex(app.AppAppearanceError, "outside theme cache"):
                app.prepare(foreign, state)
            report = json.loads((generation / "report.json").read_text())
            report["palette"]["color1"] = "red;evil"
            (generation / "report.json").write_text(json.dumps(report))
            with self.assertRaisesRegex(app.AppAppearanceError, "invalid resolved color"):
                app.prepare(generation, state)

    def test_osc_is_exactly_upstream_order_and_never_contains_commands(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, generation = prepared(Path(temporary))
            sequence = app.osc_sequences(app.palette(generation))
            self.assertEqual(sequence.count(b"\x1b]"), 21)
            self.assertIn(b"\x1b]4;1;#123456\x07", sequence)
            self.assertTrue(sequence.startswith(b"\x1b]10;#e0e5e8\x07"))
            upstream = subprocess.run(
                [str(theme_activate.HOST_TOOLS / "bin/omarchy-theme-osc"),
                 str(generation / "theme/colors.toml")], check=True, capture_output=True,
                env=os.environ | {"PATH": str(theme_activate.HOST_TOOLS / "bin")
                                  + os.pathsep + os.environ["PATH"]})
            self.assertEqual(sequence, upstream.stdout)

    def test_pinned_default_palette_subset_is_supported(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary) / "generations" / json.loads(
                (ROOT / "nix/handheld-theme-default/default-report.json").read_text())["generation"]
            base.mkdir(parents=True)
            (base / "report.json").write_bytes((ROOT / "nix/handheld-theme-default/default-report.json").read_bytes())
            colors = app.palette(base)
            self.assertEqual(colors["cursor"], colors["foreground"])
            self.assertEqual(colors["color1"], colors["red"])

    def test_sync_wait_is_bounded_by_activation_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, state, generation = prepared(Path(temporary))
            (state / "active").symlink_to(generation)
            with (state / ".activation.lock").open("w") as held:
                fcntl.flock(held, fcntl.LOCK_EX)
                with self.assertRaisesRegex(app.AppAppearanceError, "lock timed out"):
                    app.sync(state, lock_timeout=0.02)
            self.assertFalse((state / "app-appearance/active").exists())

    def test_live_osc_holds_activation_lock_through_flush(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, state, generation = prepared(Path(temporary))
            (state / "active").symlink_to(generation)

            class CheckedStream(io.BytesIO):
                def flush(self):
                    with (state / ".activation.lock").open("r") as contender:
                        with self_test.assertRaises(BlockingIOError):
                            fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    super().flush()

            self_test = self
            stream = CheckedStream()
            app.emit_current(state, stream)
            self.assertEqual(stream.getvalue(), app.osc_sequences(app.palette(generation)))

    def test_post_ack_app_sync_reports_separate_success_and_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, state, generation = prepared(Path(temporary))
            phases = []
            def ack(_endpoint, phase, _generation):
                phases.append(phase)
            success = tx.activate_generation(generation, state_root=state,
                                             endpoint=state / "unused.sock", transport=ack)
            self.assertEqual(success, {"state": "applied", "generation": generation.name})
            self.assertEqual((state / "app-appearance/active").resolve().name,
                             app.sync(state).name)
            self.assertEqual(phases, ["prepare", "commit"])
            def fail_app(_root, *, expected_generation):
                self.assertEqual(expected_generation, generation.name)
                raise OSError("injected adapter failure")
            failure = tx.activate_generation(generation, state_root=state,
                                             endpoint=state / "unused.sock", transport=ack,
                                             app_sync=fail_app)
            self.assertEqual(failure["state"], "failed")
            self.assertEqual(failure["error"], "app-sync-failed")
            self.assertEqual(tx._pointer(state), generation)
            self.assertEqual(phases, ["prepare", "commit", "prepare", "commit"])

    def test_late_app_sync_never_reselects_prior_generation(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            _, state, first = prepared(base)
            other = state / "generations" / ("a" * 24)
            other.mkdir()
            second_report = json.loads((first / "report.json").read_text())
            second_report["generation"] = other.name
            (other / "report.json").write_text(json.dumps(second_report))
            (state / "active").symlink_to(other)
            with self.assertRaisesRegex(app.AppAppearanceSuperseded, "newer generation"):
                app.sync(state, expected_generation=first.name)
            self.assertFalse((state / "app-appearance/active").exists())


if __name__ == "__main__":
    unittest.main()
