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
        action = argv[1]
        entries = [{"name": "catppuccin", "origin": "builtin", "id": "a" * 24},
                   {"name": "catppuccin-latte", "origin": "builtin", "id": "b" * 24}]
        if action == "list":
            pointer = _pointer(self.state)
            return {"schema": 1, "themes": entries,
                    "active": {"generation": pointer.name if pointer else None}}
        theme_id = argv[2]
        generation = self.dark if theme_id == "a" * 24 else self.light
        if action == "preview":
            if self.fail_role == "light" and generation == self.light:
                raise RuntimeError("private fake path should not enter result")
            return {"schema": 1, "generation": generation.name,
                    "backgrounds": [{"id": "d" * 24, "selected": True}]}
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

    def runner(self):
        return trial.Trial(self.manifest, call=self.call, capture=self.capture,
                           transport=self.transport,
                           app_sync=lambda *_args, **_kwargs: None)


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


if __name__ == "__main__":
    unittest.main()
