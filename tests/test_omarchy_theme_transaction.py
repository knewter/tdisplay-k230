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
    def test_two_receivers_commit_before_app_sync(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate = prepared(root, "candidate")
            rust, deck = root / "rust.sock", root / "deck.sock"
            events = []
            def ack(endpoint, phase, generation):
                events.append((endpoint.name, phase, generation))
            def app_sync(_root, *, expected_generation):
                self.assertEqual(tx._pointer(root), candidate)
                self.assertEqual(expected_generation, candidate.name)
                events.append(("app", "sync", candidate))
            result = tx.activate_generation(candidate, state_root=root, endpoint=rust,
                                            endpoints=(rust, deck), transport=ack,
                                            app_sync=app_sync)
            self.assertEqual(result, {"state": "applied", "generation": candidate.name})
            self.assertEqual(events, [("rust.sock", "prepare", candidate),
                                      ("deck.sock", "prepare", candidate),
                                      ("rust.sock", "commit", candidate),
                                      ("deck.sock", "commit", candidate),
                                      ("app", "sync", candidate)])

    def test_prepare_only_sends_prepare_to_both_receivers_without_committing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate = prepared(root, "candidate")
            rust, deck = root / "rust.sock", root / "deck.sock"
            events = []
            def ack(endpoint, phase, generation):
                events.append((endpoint.name, phase, generation))
            tx.prepare_only(candidate, state_root=root, endpoint=rust,
                            endpoints=(rust, deck), transport=ack)
            self.assertEqual(events, [("rust.sock", "prepare", candidate),
                                      ("deck.sock", "prepare", candidate)])
            # No pointer change, no lock file left held, no public links
            # created -- this is browsing, not activation.
            self.assertIsNone(tx._pointer(root))
            self.assertFalse((root / ".activation.lock").exists())

    def test_prepare_only_does_not_take_the_activation_lock(self):
        """A person still browsing (repeated prepare_only calls) must never
        be blocked by, or block, an unrelated in-flight
        activate_generation() -- prepare_only takes no lock at all."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate = prepared(root, "candidate")
            rust, deck = root / "rust.sock", root / "deck.sock"
            descriptor = os.open(root / ".activation.lock", os.O_CREAT | os.O_RDWR, 0o600)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                tx.prepare_only(candidate, state_root=root, endpoint=rust,
                                endpoints=(rust, deck), transport=lambda *a: None)
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)

    def test_prepare_only_rejects_a_generation_outside_the_prepared_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            prepared(root, "candidate")  # ensures root/generations exists
            outside = Path(temp) / "elsewhere"
            outside.mkdir()
            (outside / "report.json").write_text("{}")
            with self.assertRaises(tx.TransactionError):
                tx.prepare_only(outside, state_root=root, endpoint=root / "rust.sock")

    def test_second_prepare_failure_rolls_back_both_without_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate = prepared(root, "candidate")
            rust, deck = root / "rust.sock", root / "deck.sock"
            events = []
            def fail(endpoint, phase, generation):
                events.append((endpoint.name, phase, generation))
                if endpoint == deck and phase == "prepare":
                    raise tx.TransactionError("deck rejected")
            with self.assertRaisesRegex(tx.TransactionError, "prepare failed; both receivers restored"):
                tx.activate_generation(candidate, state_root=root, endpoint=rust,
                                       endpoints=(rust, deck), transport=fail,
                                       app_sync=lambda *_args, **_kwargs: self.fail("app sync before ACK"))
            self.assertIsNone(tx._pointer(root))
            self.assertEqual([item[:2] for item in events],
                             [("rust.sock", "prepare"), ("deck.sock", "prepare"),
                              ("rust.sock", "rollback"), ("deck.sock", "rollback")])

    def test_second_commit_failure_restores_pointer_and_both_receivers(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old, candidate = prepared(root, "old"), prepared(root, "candidate")
            (root / "active").symlink_to(old)
            rust, deck = root / "rust.sock", root / "deck.sock"
            events = []
            def fail(endpoint, phase, generation):
                events.append((endpoint.name, phase, generation))
                if endpoint == deck and phase == "commit":
                    raise tx.TransactionError("deck commit lost")
            with self.assertRaisesRegex(tx.TransactionError, "previous generation restored"):
                tx.activate_generation(candidate, state_root=root, endpoint=rust,
                                       endpoints=(rust, deck), transport=fail,
                                       app_sync=lambda *_args, **_kwargs: self.fail("app sync before both ACKs"))
            self.assertEqual(tx._pointer(root), old)
            self.assertEqual([item[:2] for item in events],
                             [("rust.sock", "prepare"), ("deck.sock", "prepare"),
                              ("rust.sock", "commit"), ("deck.sock", "commit"),
                              ("rust.sock", "rollback"), ("deck.sock", "rollback")])

    def test_rollback_failure_still_contacts_other_receiver(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate = prepared(root, "candidate")
            rust, deck = root / "rust.sock", root / "deck.sock"
            events = []
            def fail(endpoint, phase, generation):
                events.append((endpoint.name, phase))
                if phase == "commit" and endpoint == deck:
                    raise tx.TransactionError("commit failed")
                if phase == "rollback" and endpoint == rust:
                    raise tx.TransactionError("rust rollback failed")
            with self.assertRaisesRegex(tx.TransactionError, "fanout rollback was not acknowledged"):
                tx.activate_generation(candidate, state_root=root, endpoint=rust,
                                       endpoints=(rust, deck), transport=fail)
            self.assertIn(("deck.sock", "rollback"), events)
            self.assertIsNone(tx._pointer(root))

    def test_preference_failure_after_both_commits_rolls_back_every_surface(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old, candidate = prepared(root, "old"), prepared(root, "candidate")
            (root / "active").symlink_to(old)
            rust, deck = root / "rust.sock", root / "deck.sock"
            events = []
            class Preference:
                def guard(self):
                    events.append("guard")
                def commit(self):
                    events.append("preference-commit")
                    raise OSError("injected preference write failure")
                def rollback(self):
                    events.append("preference-rollback")
            def ack(endpoint, phase, _generation):
                events.append(f"{endpoint.name}-{phase}")
            with self.assertRaisesRegex(tx.TransactionError, "previous generation restored"):
                tx.activate_generation(candidate, state_root=root, endpoint=rust,
                                       endpoints=(rust, deck), transport=ack,
                                       preference=Preference(),
                                       app_sync=lambda *_args, **_kwargs: self.fail("app sync after failed preference"))
            self.assertEqual(tx._pointer(root), old)
            self.assertEqual(events, ["guard", "rust.sock-prepare", "deck.sock-prepare",
                                      "rust.sock-commit", "deck.sock-commit",
                                      "preference-commit", "preference-rollback",
                                      "rust.sock-rollback", "deck.sock-rollback"])

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
