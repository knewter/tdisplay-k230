"""Host-only transaction tests; no installed shell receiver is implied."""

import json
from pathlib import Path
import os
import socket
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
import fcntl


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import theme_transaction as tx  # noqa: E402


def prepared(root, name):
    path = root / "generations" / name
    path.mkdir(parents=True)
    (path / "report.json").write_text(json.dumps({"generation": name}))
    return path


class ThemeTransaction(unittest.TestCase):
    def test_commit_ack_publishes_and_repeat_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate = prepared(root, "candidate")
            phases = []

            def ack(_endpoint, phase, generation):
                phases.append((phase, generation))

            tx.activate_generation(candidate, state_root=root, endpoint=root / "shell.sock", transport=ack)
            tx.activate_generation(candidate, state_root=root, endpoint=root / "shell.sock", transport=ack)
            self.assertEqual(tx._pointer(root), candidate)
            for name in ("theme", "theme.name", "background"):
                self.assertEqual((root / name).readlink().as_posix(), "active/" + name)
            # A palette-only generation has no usable background media; the
            # compatibility link advertises absence via failed dereference.
            self.assertTrue((root / "background").is_symlink())
            self.assertFalse((root / "background").exists())
            self.assertEqual(phases, [("prepare", candidate), ("commit", candidate),
                                      ("prepare", candidate), ("commit", candidate)])

    def test_prepare_rejection_preserves_previous_pointer(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old, new = prepared(root, "old"), prepared(root, "new")
            tx.activate_generation(old, state_root=root, endpoint=root / "shell.sock",
                                   transport=lambda *args: None)

            def reject(_endpoint, phase, _generation):
                if phase == "prepare":
                    raise tx.TransactionError("rejected")

            with self.assertRaisesRegex(tx.TransactionError, "rejected"):
                tx.activate_generation(new, state_root=root, endpoint=root / "shell.sock", transport=reject)
            self.assertEqual(tx._pointer(root), old)

    def test_failed_commit_restores_previous_pointer_and_requires_rollback_ack(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old, new = prepared(root, "old"), prepared(root, "new")
            tx.activate_generation(old, state_root=root, endpoint=root / "shell.sock",
                                   transport=lambda *args: None)
            phases = []

            def fail(_endpoint, phase, generation):
                phases.append((phase, generation))
                if phase == "commit":
                    raise tx.TransactionError("lost commit ack")

            with self.assertRaisesRegex(tx.TransactionError, "previous generation restored"):
                tx.activate_generation(new, state_root=root, endpoint=root / "shell.sock", transport=fail)
            self.assertEqual(tx._pointer(root), old)
            self.assertEqual(phases, [("prepare", new), ("commit", new), ("rollback", old)])

    def test_unacknowledged_rollback_is_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate = prepared(root, "candidate")

            def fail(_endpoint, phase, _generation):
                if phase != "prepare":
                    raise tx.TransactionError("unacknowledged")

            with self.assertRaisesRegex(tx.TransactionError, "rollback was not acknowledged"):
                tx.activate_generation(candidate, state_root=root, endpoint=root / "shell.sock", transport=fail)
            self.assertIsNone(tx._pointer(root))
            self.assertFalse((root / "theme").is_symlink())

    def test_real_socket_rejects_mismatched_ack(self):
        with tempfile.TemporaryDirectory() as temp:
            endpoint = Path(temp) / "shell.sock"
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            listener.bind(str(endpoint))
            listener.listen(1)

            def serve():
                with listener:
                    connection, _ = listener.accept()
                    with connection:
                        while connection.recv(1) != b"\n":
                            pass
                        connection.sendall(b'{"protocol":1,"phase":"prepare","generation":"wrong","status":"ok"}\n')

            worker = threading.Thread(target=serve)
            worker.start()
            with self.assertRaisesRegex(tx.TransactionError, "shell rejected prepare"):
                tx.exchange(endpoint, "prepare", Path(temp) / "expected")
            worker.join(timeout=2)
            self.assertFalse(worker.is_alive())

    def test_outside_generation_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            prepared(root, "valid")
            outsider = root / "outside"
            outsider.mkdir()
            (outsider / "report.json").write_text("{}")
            with self.assertRaisesRegex(tx.TransactionError, "outside"):
                tx.activate_generation(outsider, state_root=root, endpoint=root / "shell.sock")

    def test_existing_public_theme_path_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate = prepared(root, "candidate")
            (root / "theme").mkdir()
            with self.assertRaisesRegex(tx.TransactionError, "incompatible public theme path"):
                tx.activate_generation(candidate, state_root=root, endpoint=root / "shell.sock",
                                       transport=lambda *args: None)
            self.assertIsNone(tx._pointer(root))

    def test_broken_active_pointer_can_be_replaced(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate = prepared(root, "candidate")
            (root / "active").symlink_to(root / "generations" / "removed")
            tx.activate_generation(candidate, state_root=root, endpoint=root / "shell.sock",
                                   transport=lambda *args: None)
            self.assertEqual(tx._pointer(root), candidate)

    def test_dangling_foreign_active_pointer_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate = prepared(root, "candidate")
            foreign = root / "elsewhere" / "removed"
            (root / "active").symlink_to(foreign)
            with self.assertRaisesRegex(tx.TransactionError, "escapes cache"):
                tx.activate_generation(candidate, state_root=root, endpoint=root / "shell.sock",
                                       transport=lambda *args: None)
            self.assertEqual((root / "active").readlink(), foreign)

    def test_relative_state_root_is_normalized(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate = prepared(root, "candidate")
            relative_root = Path(os.path.relpath(root))
            tx.activate_generation(candidate, state_root=relative_root, endpoint=root / "shell.sock",
                                   transport=lambda *args: None)
            self.assertEqual(tx._pointer(root), candidate)

    def test_post_replace_sync_failure_restores_previous_pointer(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old, new = prepared(root, "old"), prepared(root, "new")
            tx.activate_generation(old, state_root=root, endpoint=root / "shell.sock",
                                   transport=lambda *args: None)
            real_fsync = tx.os.fsync
            calls = 0
            phases = []

            def fail_once(fd):
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise OSError("injected post-replace sync failure")
                return real_fsync(fd)

            def ack(_endpoint, phase, generation):
                phases.append((phase, generation))

            with mock.patch.object(tx.os, "fsync", side_effect=fail_once):
                with self.assertRaisesRegex(tx.TransactionError, "previous generation restored"):
                    tx.activate_generation(new, state_root=root, endpoint=root / "shell.sock", transport=ack)
            self.assertEqual(tx._pointer(root), old)
            self.assertEqual(phases, [("prepare", new), ("rollback", old)])

    def test_activation_lock_has_total_wait_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate = prepared(root, "candidate")
            lock = os.open(root / ".activation.lock", os.O_CREAT | os.O_RDWR, 0o600)
            try:
                fcntl.flock(lock, fcntl.LOCK_EX)
                with self.assertRaisesRegex(tx.TransactionError, "lock timed out"):
                    tx.activate_generation(candidate, state_root=root, endpoint=root / "shell.sock",
                                           transport=lambda *args: None, lock_timeout=0.02)
            finally:
                os.close(lock)

    def test_socket_reply_uses_total_deadline_not_per_byte_timeout(self):
        with tempfile.TemporaryDirectory() as temp:
            endpoint = Path(temp) / "shell.sock"
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            listener.bind(str(endpoint))
            listener.listen(1)

            def drip():
                with listener:
                    connection, _ = listener.accept()
                    with connection:
                        while connection.recv(1) != b"\n":
                            pass
                        for byte in b'{"protocol":1':
                            try:
                                connection.sendall(bytes([byte]))
                            except BrokenPipeError:
                                break
                            time.sleep(0.03)

            worker = threading.Thread(target=drip)
            worker.start()
            started = time.monotonic()
            with self.assertRaises((socket.timeout, tx.TransactionError)):
                tx.exchange(endpoint, "prepare", Path(temp) / "candidate", timeout=0.08)
            self.assertLess(time.monotonic() - started, 0.3)
            worker.join(timeout=1)
            self.assertFalse(worker.is_alive())


if __name__ == "__main__":
    unittest.main()
