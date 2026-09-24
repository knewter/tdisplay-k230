"""Host-only failure/recovery checks for the reserved-board theme procedure."""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from theme_preferences import _publish as publish_preferences  # noqa: E402
from theme_transaction import _pointer, _swap_pointer  # noqa: E402

spec = importlib.util.spec_from_file_location("theme_trial", ROOT / "tools/handheld-theme-trial.py")
trial = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trial)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / "state"
        (self.state / "generations").mkdir(parents=True)
        self.previous = self.state / "generations" / ("1" * 24)
        self.previous.mkdir()
        (self.previous / "report.json").write_text("{}\n")
        self.dark = self.state / "generations" / ("2" * 24)
        self.light = self.state / "generations" / ("3" * 24)
        for path in (self.dark, self.light):
            path.mkdir()
            (path / "report.json").write_text("{}\n")
        self.default = self.root / "default" / ("4" * 24)
        self.default.mkdir(parents=True)
        self.prefs = b'{"version":1,"choices":{}}\n'
        publish_preferences(self.state, self.prefs)
        app_generations = self.state / "app-appearance/generations"
        app_generations.mkdir(parents=True)
        self.app_before = app_generations / ("5" * 24)
        self.app_trial = app_generations / ("6" * 24)
        self.app_before.mkdir()
        self.app_trial.mkdir()
        (self.state / "app-appearance/active").symlink_to(self.app_before)
        self.out = self.root / "evidence"
        self.out.mkdir()
        self.raw = self.root / "raw"
        self.raw.mkdir(mode=0o700)
        self.endpoints = (self.root / "rust.sock", self.root / "deck.sock")
        self.workload = self.root / "workload.json"
        self.workload.write_text('{"schema":1,"id":"cards-shade-static-v1"}\n')
        self.events = []
        self.fail_role = None
        self.fail_rollback_default = False
        self.selected_kinds = []
        self.manifest = {"schema": 1, "source_revision": "a" * 40,
                         "system": "/nix/store/" + "a" * 32 + "-system",
                         "theme_command": "/nix/store/" + "a" * 32 + "-theme/bin/k230-theme",
                         "capture_command": "/nix/store/" + "a" * 32 + "-grim/bin/grim",
                         "default_generation": str(self.default), "state_root": str(self.state),
                         "rust_socket": str(self.endpoints[0]), "deck_socket": str(self.endpoints[1]),
                         "workload": {"id": "cards-shade-static-v1",
                                      "sha256": hashlib.sha256(self.workload.read_bytes()).hexdigest(),
                                      "artifact": str(self.workload)},
                         "themes": {"dark": "catppuccin", "light": "catppuccin-latte"}}

    def capture(self, role, raw):
        self.assertEqual(raw, self.raw)
        return {"kind": "native-unreviewed", "sha256": "c" * 64, "bytes": 4}

    def transport(self, endpoint, phase, generation):
        self.events.append((endpoint.name, phase, generation.name if generation else None))
        if (self.fail_rollback_default and phase == "rollback" and generation is None
                and endpoint == self.endpoints[1]):
            raise OSError("fake failed ACK")

    def call(self, argv):
        self.assertEqual(argv[argv.index("--state-root") + 1], str(self.state))
        self.assertEqual(argv[argv.index("--rust-socket") + 1], str(self.endpoints[0]))
        self.assertEqual(argv[argv.index("--deck-socket") + 1], str(self.endpoints[1]))
        action = next(value for value in argv if value in ("list", "preview", "activate"))
        entries = [{"name": "catppuccin", "origin": "builtin", "id": "a" * 24},
                   {"name": "catppuccin-latte", "origin": "builtin", "id": "b" * 24}]
        if action == "list":
            pointer = _pointer(self.state)
            return {"schema": 1, "themes": entries,
                    "active": {"generation": pointer.name if pointer else None}}
        theme_id = argv[argv.index(action) + 1]
        background = argv[argv.index("--background") + 1] if "--background" in argv else "d" * 24
        self.selected_kinds.append(background)
        generation = self.dark if theme_id == "a" * 24 else self.light
        if action == "preview":
            if self.fail_role == "light" and generation == self.light:
                raise RuntimeError("private fake path should not enter result")
            if background == "e" * 24:
                (generation / "report.json").write_text(json.dumps({
                    "generation": generation.name,
                    "backgrounds": ["backgrounds/trial.mp4"],
                    "selected_background": "backgrounds/trial.mp4"}))
            return {"schema": 1, "generation": generation.name,
                    "backgrounds": [{"id": background, "selected": True,
                                     "kind": "video" if background == "e" * 24 else "image"}]}
        self.assertEqual(action, "activate")
        self.assertEqual(argv[argv.index("--expected-generation") + 1], generation.name)
        _swap_pointer(self.state, generation)
        for name in ("theme", "theme.name", "background"):
            link = self.state / name
            if not link.exists() and not link.is_symlink():
                link.symlink_to("active/" + name)
        publish_preferences(self.state, b'{"version":1,"choices":{"' + b"a" * 64 + b'":"backgrounds/trial.webp"}}\n')
        (self.state / "app-appearance/active").unlink()
        (self.state / "app-appearance/active").symlink_to(self.app_trial)
        return {"schema": 1, "generation": generation.name, "activated": True,
                "app_appearance": {"state": "applied"}}

    def runner(self, **kwargs):
        return trial.Trial(self.manifest, call=self.call, capture=self.capture,
                           transport=self.transport,
                           app_sync=lambda *_args, **_kwargs: None,
                           resource_sample=lambda duration, interval: {
                               "elapsed_s": duration, "sample_count": 3,
                               "cpu_usage_usec": 400000, "process_rss_peak_bytes": 1024},
                           status_path=self.root / "k230-wallpaper-status.json",
                           status_wait_s=0, **kwargs)


class ThemeTrialTests(Fixture):
    def test_failed_second_preview_restores_previous_generation_and_private_preferences(self):
        _swap_pointer(self.state, self.previous)
        self.fail_role = "light"
        with self.assertRaisesRegex(RuntimeError, "trial failed"):
            self.runner().run(self.out, self.raw)
        result = json.loads((self.out / "result.json").read_text())
        self.assertEqual(result["restoration"], "passed")
        self.assertEqual(result["trial"], "failed")
        self.assertEqual(result["failure_stage"], "preview-light")
        self.assertEqual(len(result["arms"]), 1)
        self.assertEqual(_pointer(self.state), self.previous)
        self.assertEqual((self.state / "background-selections.json").read_bytes(), self.prefs)
        self.assertEqual(trial.app_pointer(self.state), self.app_before)
        self.assertFalse((self.state / "theme").is_symlink())
        self.assertNotIn("private fake path", (self.out / "result.json").read_text())
        self.assertNotIn(str(self.workload), (self.out / "result.json").read_text())
        self.assertEqual([(name, phase) for name, phase, _ in self.events[-4:]],
                         [("rust.sock", "prepare"), ("deck.sock", "prepare"),
                          ("rust.sock", "commit"), ("deck.sock", "commit")])

    def test_no_prior_pointer_returns_both_receivers_to_pinned_default(self):
        result = self.runner().run(self.out, self.raw)
        self.assertEqual(result["restoration"], "passed")
        self.assertIsNone(_pointer(self.state))
        self.assertEqual((self.state / "background-selections.json").read_bytes(), self.prefs)
        self.assertEqual(trial.app_pointer(self.state), self.app_before)
        self.assertFalse((self.state / "theme").exists())
        self.assertIn(("rust.sock", "rollback", None), self.events)
        self.assertIn(("deck.sock", "rollback", None), self.events)
        self.assertEqual(result["baseline"]["workload"], result["arms"][0]["workload"])

    def test_failed_default_ack_flags_uncertain_state_and_keeps_current_pointer(self):
        self.fail_rollback_default = True
        with self.assertRaisesRegex(RuntimeError, "trial failed"):
            self.runner().run(self.out, self.raw)
        result = json.loads((self.out / "result.json").read_text())
        self.assertEqual(result["restoration"], "FAILED")
        self.assertEqual(_pointer(self.state), self.light)
        self.assertIn(("rust.sock", "rollback", self.light.name), self.events)
        self.assertIn(("deck.sock", "rollback", self.light.name), self.events)

    def test_candidate_rejects_unpinned_or_missing_workload_identity(self):
        data = self.manifest.copy()
        data["default_generation"] = "/nix/store/" + "a" * 32 + "-default/generations/" + "4" * 24
        data["system"] = "/tmp/system"
        path = self.root / "candidate.json"
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "Nix store"):
            trial.candidate(path)
        data["system"] = self.manifest["system"]
        data["workload"] = {"id": "cards-shade-static-v1", "sha256": "bad",
                            "artifact": str(self.workload)}
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "workload"):
            trial.candidate(path)

    def test_mutated_workload_refuses_before_theme_or_output_mutation(self):
        self.workload.write_text("changed\n")
        with self.assertRaisesRegex(RuntimeError, "workload artifact changed"):
            self.runner().run(self.out, self.raw)
        self.assertFalse((self.out / "result.json").exists())
        self.assertIsNone(_pointer(self.state))

    def test_backgrounds_samples_static_then_fails_closed_without_video_status(self):
        self.manifest["background_trial"] = {
            "duration_seconds": 2, "interval_seconds": .5,
            "choices": {
                "static": {"theme_name": "catppuccin", "origin": "builtin",
                           "background_id": "d" * 24},
                "video": {"theme_name": "catppuccin-latte", "origin": "builtin",
                          "background_id": "e" * 24}}}
        with self.assertRaisesRegex(RuntimeError, "trial failed"):
            self.runner().run(self.out, self.raw, workload_mode="backgrounds")
        result = json.loads((self.out / "result.json").read_text())
        self.assertEqual(result["workload_mode"], "backgrounds")
        self.assertEqual(result["failure_stage"], "measure-video")
        self.assertEqual([arm["role"] for arm in result["arms"]], ["static"])
        self.assertEqual(result["baseline"]["resources"]["sample_count"], 3)
        self.assertEqual(result["arms"][0]["resources"]["cpu_usage_usec"], 400000)
        self.assertEqual(self.selected_kinds, ["d" * 24, "d" * 24, "e" * 24, "e" * 24])
        self.assertEqual(result["restoration"], "passed")
        self.assertIsNone(_pointer(self.state))

    def test_background_video_needs_real_frame_progress_and_distinct_native_captures(self):
        self.manifest["background_trial"] = {
            "duration_seconds": 2, "interval_seconds": .5,
            "choices": {
                "static": {"theme_name": "catppuccin", "origin": "builtin",
                           "background_id": "d" * 24},
                "video": {"theme_name": "catppuccin-latte", "origin": "builtin",
                          "background_id": "e" * 24}}}
        observations = [0]

        def status_reader(_path, generation, fingerprint):
            observations[0] += 1
            step = observations[0] * 3
            return {"generation": generation, "background_fingerprint": fingerprint,
                    "decoder_pid": 123, "frames_decoded": step,
                    "frames_submitted": step, "frame_callbacks": step,
                    "last_decoded_monotonic_ms": step,
                    "last_submitted_monotonic_ms": step,
                    "last_callback_monotonic_ms": step}

        def capture(role, _raw):
            return {"kind": "native-unreviewed",
                    "sha256": ("d" if role == "video-second" else "c") * 64,
                    "bytes": 4}

        runner = self.runner(status_reader=status_reader)
        runner.capture = capture
        result = runner.run(self.out, self.raw, workload_mode="backgrounds")
        self.assertEqual(result["trial"], "completed-needs-operator-review")
        self.assertEqual(result["arms"][1]["playback"]["frame_deltas"]["frames_decoded"], 3)
        self.assertTrue(result["arms"][1]["playback"]["native_captures_distinct"])
        self.assertEqual(result["restoration"], "passed")

    def test_backgrounds_refuses_unpinned_choices_before_mutation(self):
        with self.assertRaisesRegex(ValueError, "pinned trial choices"):
            self.runner().run(self.out, self.raw, workload_mode="backgrounds")
        self.assertFalse((self.out / "result.json").exists())
        self.manifest["background_trial"] = {"duration_seconds": 99, "interval_seconds": .5,
                                            "choices": {}}
        self.manifest["default_generation"] = (
            "/nix/store/" + "a" * 32 + "-theme/generations/" + "4" * 24)
        path = self.root / "candidate.json"
        path.write_text(json.dumps(self.manifest))
        with self.assertRaisesRegex(ValueError, "bound"):
            trial.candidate(path)


if __name__ == "__main__":
    unittest.main()
