"""Host PTY/lifecycle checks for session-owned Foot color following."""

import io
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import subprocess
import sys
import tempfile
import termios
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import app_appearance as app
import foot_color_session as follower


def generation(root: Path, name: str, background: str) -> Path:
    path = root / "generations" / name
    path.mkdir(parents=True)
    report = json.loads((ROOT / "nix/handheld-theme-default/default-report.json").read_text())
    report["generation"] = name
    report["palette"]["background"] = background
    (path / "report.json").write_text(json.dumps(report))
    return path


class FootSession(unittest.TestCase):
    def test_observer_emits_only_generation_changes_and_restores_default(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = generation(root, "a" * 24, "#111111")
            second = generation(root, "b" * 24, "#222222")
            stream = io.BytesIO()
            last = follower.observe(root, first, None, stream)
            self.assertEqual(stream.getvalue(), app.osc_sequences(app.palette(first)))
            size = len(stream.getvalue())
            self.assertEqual(follower.observe(root, first, last, stream), last)
            self.assertEqual(len(stream.getvalue()), size)
            (root / "active").symlink_to(second)
            last = follower.observe(root, first, last, stream)
            self.assertEqual(stream.getvalue()[size:], app.osc_sequences(app.palette(second)))
            (root / "active").unlink()
            size = len(stream.getvalue())
            follower.observe(root, first, last, stream)
            self.assertEqual(stream.getvalue()[size:], app.osc_sequences(app.palette(first)))

    def test_exec_preserves_app_args_and_follower_dies_with_parent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            default = generation(root, "a" * 24, "#111111")
            master, slave = pty.openpty()
            app_code = ('import os,time; '
                        'print("APP-READY", flush=True); '
                        'print("FOREGROUND=" + str(os.tcgetpgrp(0) == os.getpgrp()), flush=True); '
                        'time.sleep(1.0); print("APP-DONE", flush=True)')
            command = [sys.executable, str(ROOT / "tools/foot_color_session.py"),
                       "--state-root", str(root), "--default-generation", str(default),
                       "--interval", "0.25", "--", sys.executable, "-c", app_code]
            def controlling_tty():
                os.setsid()
                fcntl.ioctl(slave, termios.TIOCSCTTY, 0)
            process = subprocess.Popen(command, stdin=slave, stdout=slave, stderr=slave,
                                       preexec_fn=controlling_tty,
                                       env=os.environ | {"TERM": "foot"})
            os.close(slave)
            output = bytearray()
            deadline = time.monotonic() + 3
            follower_pid = None
            follower_rss_kib = None
            try:
                while time.monotonic() < deadline:
                    ready, _, _ = select.select([master], [], [], 0.1)
                    if ready:
                        try:
                            chunk = os.read(master, 4096)
                        except OSError:
                            break
                        if not chunk:
                            break
                        output.extend(chunk)
                    if b"APP-READY" in output and follower_pid is None:
                        children = Path(f"/proc/{process.pid}/task/{process.pid}/children")
                        if children.exists():
                            ids = children.read_text().split()
                            if ids:
                                follower_pid = int(ids[0])
                                status = Path(f"/proc/{follower_pid}/status").read_text()
                                rss = next((line for line in status.splitlines()
                                            if line.startswith("VmRSS:")), None)
                                if rss:
                                    follower_rss_kib = int(rss.split()[1])
                    if process.poll() is not None and b"APP-DONE" in output:
                        break
                self.assertEqual(process.wait(timeout=1), 0)
                self.assertIn(b"APP-READY", output)
                self.assertIn(b"FOREGROUND=True", output)
                self.assertIn(b"APP-DONE", output)
                self.assertIn(app.osc_sequences(app.palette(default)), output)
                self.assertIsNotNone(follower_pid)
                self.assertIsNotNone(follower_rss_kib)
                print(f"HOST_FOOT_FOLLOWER_RSS_KIB={follower_rss_kib}", file=sys.stderr)
                exit_deadline = time.monotonic() + 1.5
                while time.monotonic() < exit_deadline:
                    status = Path(f"/proc/{follower_pid}/status")
                    if not status.exists() or "State:\tZ" in status.read_text():
                        break
                    time.sleep(0.02)
                else:
                    self.fail("Foot color follower outlived the terminal app")
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=1)
                os.close(master)

    def test_non_tty_refuses_to_launch_app(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            default = generation(root, "a" * 24, "#111111")
            command = [sys.executable, str(ROOT / "tools/foot_color_session.py"),
                       "--state-root", str(root), "--default-generation", str(default),
                       "--", "/bin/sh", "-c", "printf SHOULD-NOT-RUN"]
            result = subprocess.run(command, capture_output=True, env=os.environ | {"TERM": "foot"})
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn(b"SHOULD-NOT-RUN", result.stdout)

    def test_fast_parent_exit_is_observed_by_prefork_pidfd(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            default = generation(root, "a" * 24, "#111111")
            read_fd, write_fd = os.pipe()
            parent = os.fork()
            if parent == 0:
                os.close(read_fd)
                pidfd = os.pidfd_open(os.getpid())
                child = os.fork()
                if child == 0:
                    time.sleep(0.05)  # the exec'd app has already exited
                    follower.follow(pidfd, root, default, 0.25, io.BytesIO())
                    os.write(write_fd, b"EXITED")
                    os._exit(0)
                os._exit(0)
            os.close(write_fd)
            try:
                os.waitpid(parent, 0)
                ready, _, _ = select.select([read_fd], [], [], 1)
                self.assertTrue(ready, "follower watched an adopted PID instead of its parent")
                self.assertEqual(os.read(read_fd, 32), b"EXITED")
            finally:
                os.close(read_fd)

    def test_full_pty_write_has_deadline_and_releases_activation_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            default = generation(root, "a" * 24, "#111111")
            master, slave = pty.openpty()
            flags = fcntl.fcntl(slave, fcntl.F_GETFL)
            pidfd = os.pidfd_open(os.getpid())
            try:
                writer = follower.BoundedTTYWriter(pidfd, slave, timeout=0.03)
                self.assertEqual(fcntl.fcntl(slave, fcntl.F_GETFL), flags)
                fcntl.fcntl(slave, fcntl.F_SETFL, flags | os.O_NONBLOCK)
                try:
                    while True:
                        os.write(slave, b"x" * 65536)
                except BlockingIOError:
                    pass
                fcntl.fcntl(slave, fcntl.F_SETFL, flags)
                started = time.monotonic()
                real_write = follower.os.write
                def blocked_write(fd, payload):
                    if fd == writer.fd:
                        raise BlockingIOError("stopped PTY output")
                    return real_write(fd, payload)
                # Some host PTYs accept one more short write after EAGAIN;
                # inject persistent backpressure at the exact follower OFD.
                with mock.patch.object(follower.os, "write", side_effect=blocked_write):
                    with self.assertRaises(TimeoutError):
                        follower.observe(root, default, None, writer)
                self.assertLess(time.monotonic() - started, 0.25)
                with (root / ".activation.lock").open("r") as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.assertEqual(fcntl.fcntl(slave, fcntl.F_GETFL), flags)
            finally:
                writer.close()
                os.close(pidfd)
                os.close(master)
                os.close(slave)


if __name__ == "__main__":
    unittest.main()
