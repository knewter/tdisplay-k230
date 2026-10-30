#!/usr/bin/env python3
"""Host simulation of the Qt Quick trial runner's launch, loss, focus and timeout paths.

Evidence class: host simulation only. It proves the runner's cleanup logic against a
modelled systemd/Sway, not that a real board was restored; the board trial's own
restoration records are the physical-session proof.
"""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import qtquick_board_runner as runner  # noqa: E402

BINARY = "/nix/store/" + "a" * 32 + "-qtquick-software-probe-0.1/bin/qtquick-software-probe"
APP = "qtquick-software-probe"


class Crashed(BaseException):
    """Stands in for SIGKILL of the controller: nothing after it may run."""


class FakeTouch:
    def __init__(self):
        self.calls = 0

    def tap(self, *a, **k):
        self.calls += 1

    def drag(self, *a, **k):
        self.calls += 1

    def close(self):
        pass


class FakeSystem:
    python = "/fake/python3"

    def __init__(self, root, **flags):
        self.root = Path(root)
        self.flags = flags
        self.now = 1000.0
        self.units = {}        # name -> {"start": t, "max": s}
        self.timers = {}       # guard unit -> fire time
        self.window = False
        self.focus = "shell-bar"
        self.log = []
        self.files = {"/proc/meminfo": "MemTotal: 900000 kB\nMemAvailable: 600000 kB\n",
                      "/proc/uptime": "100.0 90.0\n", "/proc/sys/kernel/random/boot_id": "boot-1\n",
                      "/proc/123/stat": "123 (sway) S " + " ".join(["0"] * 11) + " 5 5 " + " ".join(["0"] * 30)}
        self.on_sleep = None

    # -- System interface --
    def shell_env(self, argv):
        return ["runuser-shell"] + argv

    def read(self, path, default=None):
        p = str(path)
        if p in self.files:
            return self.files[p]
        if p.endswith("client.jsonl"):
            if any(u.startswith("qtq-") and not u.startswith("qtq-guard") for u in self.units) or self.flags.get("emit_after_exit"):
                if self.flags.get("no_first_frame"):
                    return '{"e":"start","t":1}\n'
                return '{"e":"start","t":1}\n{"e":"first_frame","t":2}\n{"e":"commit","t":3}\n'
        try:
            return Path(path).read_text()
        except OSError:
            return default

    def write(self, path, text):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(text)

    def exists(self, path):
        p = str(path)
        return Path(path).exists() or (p.endswith(".png") and not self.flags.get("no_grim"))

    def mono(self):
        return self.now

    def cpu_seconds(self):
        return self.now * 0.001

    def tick_hz(self):
        return 100

    def sleep(self, seconds):
        self.now += max(0.0, seconds)
        self.tick()
        if self.on_sleep:
            self.on_sleep(self)

    def tick(self):
        for name, info in list(self.units.items()):
            if info.get("max") and self.now - info["start"] >= info["max"]:
                self.kill_unit(name)
        for guard, fire in list(self.timers.items()):
            if self.now >= fire:
                del self.timers[guard]
                self.guard_fired(guard)

    def guard_fired(self, guard):
        spec_id = guard.replace("qtq-guard-", "")
        args = runner.argparse.Namespace(id=spec_id, reason="guard-deadline")
        runner.cmd_restore(args, system=self)
        self.log.append("guard-ran")

    def kill_unit(self, name):
        self.units.pop(name, None)
        if not self.flags.get("window_survives"):
            self.window = False

    def run(self, argv, timeout=30, check=False):
        cmd = argv[0]
        if cmd == "systemd-run":
            unit = next(a.split("=", 1)[1] for a in argv if a.startswith("--unit="))
            if "--on-active" in " ".join(argv):
                secs = int(next(a.split("=", 1)[1] for a in argv if a.startswith("--on-active=")).rstrip("s"))
                self.timers[unit] = self.now + secs
                return 0, ""
            if self.flags.get("launch_fails"):
                return 1, ""
            maxs = next((int(a.rsplit("=", 1)[1]) for a in argv if a.startswith("--property=RuntimeMaxSec=")), None)
            self.units[unit] = {"start": self.now, "max": maxs}
            self.window = not self.flags.get("no_window")
            if self.flags.get("steals_focus"):
                self.focus = APP
            return 0, ""
        if cmd == "systemctl":
            sub = argv[1]
            if sub == "is-active":
                name = argv[2]
                if name == "shell":
                    return 0, "active\n"
                return 0, ("active\n" if name in self.units else "inactive\n")
            if sub == "stop":
                name = argv[2]
                if name.endswith(".timer"):
                    self.timers.pop(name[:-6], None)
                else:
                    self.kill_unit(name)
                return 0, ""
            if sub == "reset-failed":
                return 0, ""
            if sub == "list-units":
                return 0, "".join(f"{u} loaded active running x\n" for u in self.units)
            if sub == "show":
                return 0, "321\n"
        if cmd == "pgrep":
            return 0, "123\n"
        if cmd == "runuser-shell":
            rest = argv[1:]
            if rest[0] == "swaymsg":
                if "get_tree" in rest:
                    return 0, json.dumps(self.tree())
                if rest[-1] == "kill":
                    self.window = False
                    if self.focus == APP:
                        self.focus = "shell-bar"
                    return 0, "[]"
                if rest[-1] == "focus":
                    self.focus = "shell-bar"
                    return 0, "[]"
            if rest[0] == "grim":
                return 0, ""
        return 0, ""

    def tree(self):
        nodes = [{"id": 5, "app_id": "shell-bar", "focused": self.focus == "shell-bar", "nodes": [],
                  "rect": {"x": 0, "y": 0, "width": 1232, "height": 40}}]
        if self.window:
            nodes.append({"id": 9, "app_id": APP, "focused": self.focus == APP, "nodes": [], "type": "con",
                          "rect": {"x": 0, "y": 40, "width": 1232, "height": 528}})
        return {"nodes": nodes, "floating_nodes": []}


def spec(run_id="trial-unit-1", **over):
    base = {"id": run_id, "toolkit": "qt", "app_id": APP, "binary": BINARY, "pair": 1, "order": 1,
            "manifest_hash": "h" * 64, "artifact": "/nix/store/" + "a" * 32 + "-qtquick-software-probe-0.1",
            "deadline_s": 60, "exit_after_s": 40, "idle_s": 6, "active_s": 8, "startup_timeout_s": 5}
    base.update(over)
    return base


class RunnerRecovery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.orig = runner.STATE_DIR
        runner.STATE_DIR = Path(self.tmp.name) / "qtq"
        self.addCleanup(setattr, runner, "STATE_DIR", self.orig)

    def arm(self, system, **over):
        s = spec(**over)
        a = runner.Arm(system, s, touch_factory=FakeTouch)
        system.write(runner.STATE_DIR / s["id"] / "spec.json", json.dumps(s))
        return a

    def assertClean(self, system):
        self.assertEqual(system.units, {})
        self.assertEqual(system.timers, {})
        self.assertFalse(system.window)
        self.assertEqual(system.focus, "shell-bar")

    def test_normal_run_is_bounded_and_restored(self):
        system = FakeSystem(self.tmp.name)
        a = self.arm(system)
        # The fake client exits by its own --exit-after-ms.
        system.on_sleep = lambda s: (s.units.clear(), setattr(s, "window", False)) if s.now > 1030 else None
        record = a.run()
        self.assertEqual(record["status"], "ok")
        self.assertTrue(record["functional"]["restored"])
        self.assertTrue(record["functional"]["bounded_lifetime"])
        self.assertGreaterEqual(len(record["interactions"]), 6)
        self.assertEqual(record["interactions"][0]["kind"], "drag")
        self.assertIn("idle", record["phases"])
        self.assertTrue((runner.STATE_DIR / a.id / "run.json").exists())
        self.assertClean(system)

    def test_launch_failure_disarms_the_guard(self):
        system = FakeSystem(self.tmp.name, launch_fails=True)
        a = self.arm(system)
        with self.assertRaises(RuntimeError):
            a.run()
        self.assertEqual(a.record["status"], "error")
        self.assertTrue(a.record["restoration"]["ok"])
        self.assertClean(system)

    def test_no_first_frame_times_out_and_stops_the_client(self):
        system = FakeSystem(self.tmp.name, no_first_frame=True)
        a = self.arm(system)
        with self.assertRaises(RuntimeError):
            a.run()
        self.assertEqual(a.record["status"], "no-first-frame")
        self.assertTrue(a.record["restoration"]["ok"])
        self.assertClean(system)

    def test_missing_window_is_a_failure_not_a_pass(self):
        system = FakeSystem(self.tmp.name, no_window=True)
        a = self.arm(system)
        with self.assertRaises(RuntimeError):
            a.run()
        self.assertEqual(a.record["status"], "no-window")
        self.assertClean(system)

    def test_focus_capture_and_surviving_window_are_cleaned_up(self):
        system = FakeSystem(self.tmp.name, steals_focus=True, window_survives=True)
        a = self.arm(system)
        system.on_sleep = lambda s: s.units.clear() if s.now > 1030 else None
        record = a.run()
        actions = record["restoration"]["actions"]
        self.assertIn("window-killed", actions)
        self.assertTrue(record["functional"]["restored"])
        self.assertClean(system)

    def test_controller_loss_is_recovered_by_the_independent_guard(self):
        system = FakeSystem(self.tmp.name, steals_focus=True, window_survives=True)
        a = self.arm(system)

        class Dies(runner.Arm):
            def restore(self, reason):
                if reason == "arm-finally":      # a SIGKILLed controller runs nothing
                    return {"ok": False, "reason": reason, "actions": []}
                return super().restore(reason)

        dying = Dies(system, spec(), touch_factory=FakeTouch)
        crashed = {"at": 1012}

        def crash(s):
            if s.now > crashed["at"] and not s.log:
                raise Crashed()
        system.on_sleep = crash
        with self.assertRaises(Crashed):
            dying.run()
        # The controller is gone, the unit still runs and the guard timer is armed.
        self.assertTrue(any(u.startswith("qtq-") for u in system.units))
        self.assertIn("qtq-guard-trial-unit-1", system.timers)
        system.on_sleep = None
        system.sleep(40)                       # guard deadline = 60 + 25 s after arming
        system.sleep(40)
        self.assertEqual(system.log, ["guard-ran"])
        self.assertClean(system)
        restore = json.loads((runner.STATE_DIR / "trial-unit-1/restore.json").read_text())
        self.assertTrue(restore["ok"])
        self.assertEqual(restore["reason"], "guard-deadline")

    def test_runtime_max_sec_ends_the_client_even_without_a_guard(self):
        system = FakeSystem(self.tmp.name)
        rc, _ = system.run(["systemd-run", "--unit=qtq-x.service", "--property=RuntimeMaxSec=30"])
        self.assertEqual(rc, 0)
        system.sleep(31)
        self.assertEqual(system.units, {})

    def test_sigterm_on_the_controller_runs_restoration(self):
        import os
        import signal
        system = FakeSystem(self.tmp.name, steals_focus=True)
        a = self.arm(system)
        fired = {"done": False}

        def term(s):
            if s.now > 1015 and not fired["done"]:
                fired["done"] = True
                os.kill(os.getpid(), signal.SIGTERM)
        system.on_sleep = term
        old = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)}
        try:
            runner.install_signal_handlers()
            with self.assertRaises(KeyboardInterrupt):
                a.run()
        finally:
            for sig, handler in old.items():
                signal.signal(sig, handler)
        self.assertTrue(a.record["restoration"]["ok"])
        self.assertClean(system)

    def test_inputs_are_validated(self):
        system = FakeSystem(self.tmp.name)
        with self.assertRaises(ValueError):
            runner.Arm(system, spec(run_id="Bad Id;"))
        with self.assertRaises(ValueError):
            runner.Arm(system, spec(binary="/tmp/evil"))

    def test_restore_without_state_fails_closed(self):
        system = FakeSystem(self.tmp.name)
        rc = runner.cmd_restore(runner.argparse.Namespace(id="unknown-run", reason="manual"), system=system)
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
