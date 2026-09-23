#!/usr/bin/env python3
"""Policy + real Unix peer/pidfd/descriptor transport; no VG-Lite device."""
import array
import importlib.util
import os
from pathlib import Path
import socket
import struct
import unittest
from unittest.mock import patch

source = Path(__file__).resolve().parents[2] / "nix/vglite-access/broker.py"
spec = importlib.util.spec_from_file_location("broker", source)
broker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(broker)


class BrokerTests(unittest.TestCase):
    def policy(self):
        policy = broker.Policy("shell.service", "/expected/sway", os.getuid())
        policy.ptrace_scope = lambda: 1
        policy.main_pid = os.getpid
        policy.process = lambda _: {"uids": [os.getuid()] * 4, "parent": 1, "tracer": 0,
                                    "executable": "/expected/sway", "fd_owner": 0}
        self.addCleanup(lambda: os.close(policy.granted_pidfd) if policy.granted_pidfd is not None else None)
        return policy

    def exchange(self, policy, request=b"VG1\n"):
        opened = []
        def opener():
            opened.append(True)
            return os.open("/dev/null", os.O_RDWR | os.O_CLOEXEC)
        client, server = socket.socketpair()
        with client, server:
            client.sendall(request)
            client.shutdown(socket.SHUT_WR)
            success = broker.serve_connection(server, policy, opener)
            server.close()
            reply, ancillary, flags, _ = client.recvmsg(1, socket.CMSG_SPACE(4), socket.MSG_CMSG_CLOEXEC)
            descriptors = []
            for level, kind, data in ancillary:
                if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                    descriptors.extend(array.array("i", data))
            for fd in descriptors:
                self.assertFalse(os.get_inheritable(fd))
                self.assertEqual(os.read(fd, 1), b"")
                os.close(fd)
            self.assertEqual(bool(descriptors), success)
            self.assertEqual(reply, b"G" if success else b"")
            self.assertFalse(flags & socket.MSG_CTRUNC)
            return success, len(opened)

    def test_grant_uses_real_credentials_pidfd_and_cloexec_scm(self):
        policy = self.policy()
        self.assertEqual(self.exchange(policy), (True, 1))
        # drv_open resets the real GPU, so a live compositor gets one grant.
        self.assertEqual(self.exchange(policy), (False, 0))

    def test_same_uid_does_not_authorize_a_client(self):
        policy = self.policy()
        policy.main_pid = lambda: os.getpid() + 1
        self.assertEqual(self.exchange(policy), (False, 0))

    def test_every_policy_field_is_required_before_open(self):
        changes = {"uids": [os.getuid(), 0, os.getuid(), os.getuid()], "parent": 42,
                   "tracer": 42, "executable": "/other/sway", "fd_owner": os.getuid()}
        for field, value in changes.items():
            with self.subTest(field=field):
                policy = self.policy()
                snapshot = policy.process(0)
                snapshot[field] = value
                policy.process = lambda _, s=snapshot: s
                self.assertEqual(self.exchange(policy), (False, 0))
        for scope in [0, 99]:
            policy = self.policy()
            policy.ptrace_scope = lambda: scope
            self.assertEqual(self.exchange(policy), (False, 0))

    def test_restart_between_mainpid_checks_denies(self):
        policy = self.policy()
        answers = iter([os.getpid(), os.getpid() + 1])
        policy.main_pid = lambda: next(answers)
        self.assertEqual(self.exchange(policy), (False, 0))

    def test_protocol_and_missing_evidence_fail_closed(self):
        self.assertEqual(self.exchange(self.policy(), b"bad!"), (False, 0))
        policy = self.policy()
        policy.process = lambda _: (_ for _ in ()).throw(PermissionError("no proc access"))
        self.assertEqual(self.exchange(policy), (False, 0))

    def test_expired_socket_creator_is_not_reauthenticated_by_pid_number(self):
        # A child creates the connection, transfers it back, then exits. The
        # socket's peer pidfd must still identify that dead creator.
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            listener = socket.socket(socket.AF_UNIX)
            self.addCleanup(listener.close)
            listener.bind(temp + "/listener")
            listener.listen(1)
            parent, transfer = socket.socketpair()
            child = os.fork()
            if child == 0:
                parent.close()
                connection = socket.socket(socket.AF_UNIX)
                connection.connect(temp + "/listener")
                transfer.sendmsg([b"S"], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array("i", [connection.fileno()]))])
                os._exit(0)
            transfer.close()
            _, control, _, _ = parent.recvmsg(1, socket.CMSG_SPACE(4))
            parent.close()
            fd = array.array("i", control[0][2])[0]
            inherited = socket.socket(fileno=fd)
            server, _ = listener.accept()
            os.waitpid(child, 0)
            with inherited, server:
                inherited.sendall(b"VG1\n")
                policy = self.policy()
                policy.main_pid = lambda: child
                self.assertFalse(broker.serve_connection(server, policy, lambda: self.fail("must not open")))

    def test_device_opener_rejects_permissive_or_non_device_paths(self):
        for mode, uid in [(0o100600, 0), (0o20666, 0), (0o20600, os.getuid())]:
            fake = type("Stat", (), {"st_mode": mode, "st_uid": uid})()
            fd = os.open("/dev/null", os.O_RDWR)
            with patch.object(broker.os, "open", return_value=fd), patch.object(broker.os, "fstat", return_value=fake):
                with self.assertRaises(broker.Denied):
                    broker.open_device()
            with self.assertRaises(OSError):
                os.fstat(fd)


if __name__ == "__main__":
    unittest.main()
