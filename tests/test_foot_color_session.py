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


if __name__ == "__main__":
    unittest.main()
