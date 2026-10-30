"""The Settings time helper: only two requests, only from the shell user."""
import importlib.util
import os
import socket
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("k230_time_helper", ROOT / "tools/k230_time_helper.py")
TH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TH)

TAB = "# comment\nGB\t+513030-0000731\tEurope/London\nUS\t+415100-0873900\tAmerica/Chicago\n"


class Fixture:
    def __init__(self):
        self.dir = tempfile.TemporaryDirectory()
        root = Path(self.dir.name)
        self.zoneinfo = root / "zoneinfo"
        for zone in ("Europe/London", "America/Chicago", "UTC", "Etc/GMT+5"):
            (self.zoneinfo / zone).parent.mkdir(parents=True, exist_ok=True)
            (self.zoneinfo / zone).write_bytes(b"TZif2")
        (self.zoneinfo / "zone1970.tab").write_text(TAB)
        self.flag = root / "state/network-time-off"
        self.ran = []

    def run(self, argv):
        self.ran.append(argv)
        return True

    def ask(self, line):
        return TH.handle(line, self.zoneinfo, self.flag, self.run)


class Requests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()

    def tearDown(self):
        self.f.dir.cleanup()

    def test_a_listed_zone_goes_through_timedated(self):
        self.assertEqual(self.f.ask("zone Europe/London"), "ok")
        self.assertEqual(self.f.ran, [["timedatectl", "set-timezone", "Europe/London"]])

    def test_utc_is_allowed(self):
        self.assertEqual(self.f.ask("zone UTC"), "ok")

    def test_unlisted_or_odd_zones_are_refused_without_running_anything(self):
        for line in ("zone Etc/GMT+5", "zone ../../etc/shadow", "zone Europe/../UTC", "zone /etc/passwd",
                     "zone Mars/Olympus", "zone", "zone Europe/London extra", "zone -rf"):
            self.assertEqual(self.f.ask(line), "error zone" if line in ("zone Etc/GMT+5", "zone Mars/Olympus")
                             else "error request", line)
        self.assertEqual(self.f.ran, [])

    def test_a_listed_zone_missing_on_disk_is_refused(self):
        (self.f.zoneinfo / "Europe/London").unlink()
        self.assertEqual(self.f.ask("zone Europe/London"), "error zone")
        self.assertEqual(self.f.ran, [])

    def test_network_time_off_writes_the_flag_and_stops_timesyncd(self):
        self.assertEqual(self.f.ask("network-time off"), "ok")
        self.assertTrue(self.f.flag.exists())
        self.assertEqual(self.f.ran, [["systemctl", "stop", "systemd-timesyncd.service"]])

    def test_network_time_on_removes_the_flag_and_starts_timesyncd(self):
        self.f.ask("network-time off")
        self.assertEqual(self.f.ask("network-time on"), "ok")
        self.assertFalse(self.f.flag.exists())
        self.assertEqual(self.f.ran[-1], ["systemctl", "start", "systemd-timesyncd.service"])
        self.assertEqual(self.f.ask("network-time on"), "ok")

    def test_anything_else_is_refused(self):
        for line in ("network-time maybe", "reboot now", "time 12:00", "", "zone  ", "set-ntp off"):
            self.assertEqual(self.f.ask(line), "error request", line)
        self.assertEqual(self.f.ran, [])

    def test_a_failed_command_is_reported(self):
        self.assertEqual(TH.handle("zone UTC", self.f.zoneinfo, self.f.flag, lambda argv: False), "error apply")


class Socket(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()

    def tearDown(self):
        self.f.dir.cleanup()

    def exchange(self, payload, uid):
        server, client = socket.socketpair()
        with server, client:
            client.sendall(payload)
            client.shutdown(socket.SHUT_WR)
            answer = TH.serve(server, uid, self.f.zoneinfo, self.f.flag, self.f.run)
            self.assertEqual(client.recv(64).decode(), answer + "\n")
        return answer

    def test_the_configured_user_is_answered(self):
        self.assertEqual(self.exchange(b"zone UTC\n", os.getuid()), "ok")

    def test_another_peer_is_refused_before_reading(self):
        self.assertEqual(self.exchange(b"zone UTC\n", os.getuid() + 1), "error peer")
        self.assertEqual(self.f.ran, [])

    def test_an_oversized_request_is_refused(self):
        self.assertEqual(self.exchange(b"zone " + b"A" * 200 + b"\n", os.getuid()), "error request")
        self.assertEqual(self.f.ran, [])


if __name__ == "__main__":
    unittest.main()
