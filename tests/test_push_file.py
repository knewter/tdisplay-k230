#!/usr/bin/env python3
"""Host console replay: a failed copy must not report success or reboot."""
import contextlib
import hashlib
import importlib.util
import io
from pathlib import Path
import shlex
import tempfile
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location(
    "push_file", Path(__file__).resolve().parents[1] / "tools/push-file.py"
)
push_file = importlib.util.module_from_spec(spec)
spec.loader.exec_module(push_file)


class TransferAck(unittest.TestCase):
    def replay(self, acknowledged):
        payload = b"sample public artifact"
        port = Mock()
        commands = []
        destination = "/run/shell/missing dir/file; literal $(text)"

        def send(_port, command, _settle=0.05):
            commands.append(command)
            echo = ("root@nixos:~# " + command + "\r\n").encode()
            if command.startswith("base64 -d"):
                return echo + hashlib.md5(payload).hexdigest().encode() + b"\r\n"
            if command.startswith("cp "):
                marker = command.rsplit(" ", 1)[1].encode()
                if acknowledged:
                    return echo + marker + b"\r\nroot@nixos:~# "
                return echo + b"cp: cannot create regular file: No such file or directory\r\n"
            return echo

        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "artifact"
            source.write_bytes(payload)
            with patch.object(push_file.serial, "Serial", return_value=port), \
                 patch.object(push_file, "wait_prompt", return_value=True), \
                 patch.object(push_file, "send", side_effect=send), \
                 patch.object(push_file.time, "sleep"), \
                 patch("sys.argv", ["push-file", "--src", str(source),
                                    "--dest", destination, "--reboot"]), \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                if acknowledged:
                    push_file.main()
                else:
                    with self.assertRaisesRegex(SystemExit, "copy to destination failed"):
                        push_file.main()
        copy = next(c for c in commands if c.startswith("cp "))
        self.assertEqual(shlex.split(copy)[:4], ["cp", "--", "/tmp/push.bin", destination])
        reboots = [call for call in port.write.call_args_list if call.args == (b"reboot\r\n",)]
        self.assertEqual(bool(reboots), acknowledged)
        self.assertEqual("installed ->" in output.getvalue(), acknowledged)

    def test_echoed_success_command_after_copy_failure_cannot_reboot(self):
        self.replay(False)

    def test_separate_acknowledgement_allows_success_and_reboot(self):
        self.replay(True)


if __name__ == "__main__":
    unittest.main()
