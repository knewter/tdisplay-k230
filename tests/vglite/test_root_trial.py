#!/usr/bin/env python3
"""Behavior tests without board/system-manager operations.

The adapter models systemd unit credentials and jobs, executes the generated
recovery script against a command recorder, and checks actual file permissions.
A real multi-UID root/client isolation check is supplied separately; these
unprivileged tests do not claim that privileged host/board observation.
"""
import importlib.util
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[2] / "tools/vglite-root-scene-trial.py"
spec = importlib.util.spec_from_file_location("trial", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Manager:
    def __init__(self, failure=None):
        self.failure = failure
        self.events = []
        self.units = {"shell.service"}
        self.armed = False
        self.client_seen = False

    def active(self, unit):
        return unit in self.units

    def wait_active(self, unit):
        return self.active(unit)

    def run(self, args, **kwargs):
        self.events.append(args)
        if args[0] == "systemd-run":
            unit = next(arg.split("=", 1)[1] for arg in args if arg.startswith("--unit="))
            if "recovery" in unit:
                if self.failure == "watchdog":
                    raise RuntimeError("watchdog creation failed")
                self.armed = True
                self.units.add(unit + ".timer")
            elif "scene" in unit:
                assert self.armed
                self.units.discard("shell.service")
                if self.failure == "compositor":
                    raise RuntimeError("compositor start failed after conflicting shell stop")
                self.units.add(unit + ".service")
            else:
                assert "--property=User=shell" in args and "--property=Group=shell" in args
                assert "--property=NoNewPrivileges=yes" in args and "--property=CapabilityBoundingSet=" in args
                assert "--property=PrivateDevices=yes" in args
                assert not any(arg == "--property=User=root" for arg in args)
                self.client_seen = True
                self.units.add(unit + ".service")
                if self.failure == "client":
                    raise subprocess.TimeoutExpired(args, 1)
                self.units.discard(unit + ".service")
        elif args[:2] == ["systemctl", "stop"]:
            for unit in args[2:]:
                self.units.discard(unit)
            if self.failure == "stop":
                self.failure = None
                raise subprocess.TimeoutExpired(args, 1)
        elif args[:2] == ["systemctl", "start"]:
            if self.failure != "restore":
                self.units.add("shell.service")
        return subprocess.CompletedProcess(args, 0)

    def wait_socket(self, directory):
        if self.failure == "socket":
            raise RuntimeError("socket timeout")
        return directory / "wayland-1"

    def share_socket(self, path, gid):
        self.events.append(["share-wayland", str(path), gid])
        if self.failure == "share":
            raise RuntimeError("socket permissions failed")


class RootTrial(unittest.TestCase):
    def make_trial(self, path, manager):
        return module.Trial(path, "/nix/store/test/bin/sway", ["/nix/store/test/bin/probe", "--seconds", "1"], 1, 999,
                            commands=manager, token="hosttest")

    def test_lifetime_and_all_failure_stages_restore(self):
        for failure in [None, "watchdog", "compositor", "socket", "share", "client", "stop"]:
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temp:
                manager = Manager(failure)
                trial = self.make_trial(Path(temp) / "trial", manager)
                if failure and failure != "stop":
                    with self.assertRaises((RuntimeError, subprocess.TimeoutExpired)):
                        trial.run()
                else:
                    trial.run()
                self.assertTrue(trial.restored)
                self.assertEqual(manager.units, {"shell.service"})
                self.assertFalse(trial.directory.exists())
                if failure != "watchdog":
                    stop = next(i for i, e in enumerate(manager.events) if e[:2] == ["systemctl", "stop"])
                    restart = next(i for i, e in enumerate(manager.events) if e[:2] == ["systemctl", "start"])
                    self.assertLess(stop, restart)

    def test_restore_failure_keeps_watchdog_and_private_files(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = Manager("restore")
            trial = self.make_trial(Path(temp) / "trial", manager)
            with self.assertRaises(RuntimeError):
                trial.run()
            self.assertFalse(trial.restored)
            self.assertTrue((trial.control / "recover.py").exists())
            self.assertIn(trial.watchdog + ".timer", manager.units)

    def test_configuration_has_no_privileged_client_launch(self):
        expected = ["swaynag_command -", "swaybg_command -", "xwayland disable",
                    "output DSI-1 mode 568x1232 transform normal scale 1 render_bit_depth 6", "default_border none"]
        self.assertEqual(module.CONFIG.splitlines(), expected)
        with tempfile.TemporaryDirectory() as temp:
            trial = self.make_trial(Path(temp) / "trial", Manager())
            old_umask = os.umask(0o077)
            try:
                trial.prepare()
            finally:
                os.umask(old_umask)
            self.assertEqual(stat.S_IMODE(trial.directory.stat().st_mode), 0o711)
            self.assertEqual(stat.S_IMODE(trial.display.stat().st_mode), 0o711)
            self.assertEqual(stat.S_IMODE(trial.control.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((trial.control / "sway.conf").stat().st_mode), 0o600)
            compositor = trial.compositor_command()
            self.assertIn("--property=User=root", compositor)
            self.assertIn("--property=KillMode=control-group", compositor)
            self.assertIn("--property=Conflicts=shell.service", compositor)
            self.assertIn("--property=RuntimeMaxSec=16s", compositor)
            self.assertIn("--setenv=SWAYSOCK=" + str(trial.control / "sway-ipc.sock"), compositor)
            client = trial.client_command(trial.display / "wayland-1")
            self.assertIn("--property=User=shell", client)
            self.assertIn("--property=Group=shell", client)
            self.assertIn("--property=PrivateDevices=yes", client)
            self.assertIn("--property=AmbientCapabilities=", client)
            self.assertIn("--property=UnsetEnvironment=SWAYSOCK WLR_RENDERER K230_VGLITE_ALLOW_UNPROVEN_CACHE DBUS_SESSION_BUS_ADDRESS DISPLAY XAUTHORITY WAYLAND_SOCKET", client)
            self.assertEqual(client[-4:], ["--", *trial.client])

    def test_generated_watchdog_and_stop_hook_run_expected_jobs(self):
        # Execute the actual generated script with a recorder replacing only
        # systemctl. It cannot touch host services and exposes job ordering.
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            trial = self.make_trial(temp / "trial", Manager())
            trial.prepare()
            recorder = temp / "systemctl"
            recorder.write_text("#!/bin/sh\nprintf '%s\\n' \"$*\" >> \"$TRIAL_RECORD\"\n")
            recorder.chmod(0o755)
            log = temp / "jobs"
            env = dict(os.environ, PATH=str(temp), TRIAL_RECORD=str(log))
            for mode, expected in [([], ["stop " + trial.client_unit + ".service", "--no-block start shell.service"]),
                                   (["watchdog"], ["stop " + trial.client_unit + ".service " + trial.unit + ".service", "start shell.service"])]:
                log.unlink(missing_ok=True)
                subprocess.run([sys.executable, str(trial.control / "recover.py"), *mode], env=env, check=True)
                self.assertEqual(log.read_text().splitlines(), expected)

    def test_inactive_shell_is_not_started(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = Manager()
            manager.units.clear()
            trial = self.make_trial(Path(temp) / "trial", manager)
            with self.assertRaises(RuntimeError):
                trial.run()
            self.assertFalse(manager.events)

    def test_no_program_or_argument_shell_interpolation(self):
        with tempfile.TemporaryDirectory() as temp:
            trial = self.make_trial(Path(temp) / "trial", Manager())
            trial.client += ["$(do-not-run); `do-not-run`"]
            self.assertEqual(trial.client_command(Path("/run/trial/wayland-1"))[-1], "$(do-not-run); `do-not-run`")
            with self.assertRaises(ValueError):
                module.trusted_program("/bin/sh")


if __name__ == "__main__":
    unittest.main()
