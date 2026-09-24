"""Synthetic Wi-Fi broker checks: never use the board or real credentials."""
import importlib.util
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "tools/wifi_settings_broker.py"
spec = importlib.util.spec_from_file_location("wifi_settings_broker", MODULE)
wifi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wifi)


class FakeRadio:
    def __init__(self):
        self.calls = []
    def status(self):
        return {"current": None, "saved": None, "error": None}
    def scan(self):
        return [{"ssid": "Example Guest", "security": "open"}]
    def connect(self, ssid, security, password, cancelled=lambda: False):
        self.calls.append((ssid, security, password))
        return {"result": "saved", "ssid": ssid}
    def forget(self, ssid):
        self.calls.append(("forget", ssid))
        return {"result": "forgotten"}


class FakeProcess:
    def __init__(self, argv, **_):
        self.argv = argv
        self.terminated = False
    def poll(self):
        return None
    def terminate(self):
        self.terminated = True
    def wait(self, **_):
        return 0


class TrialRadio(wifi.Radio):
    def __init__(self, root):
        super().__init__(credential=root / "wifi" / "wpa_supplicant.conf",
                         runtime=root / "runtime", owner_uid=os.getuid())
        (root / "wifi").mkdir(mode=0o700)
        self.commands = []
        self.connected = False
        self.fail_start = False
    def fixed(self, argv, timeout=5):
        self.commands.append(tuple(argv))
        if argv[:2] == [self.systemctl, "start"] and self.fail_start:
            raise wifi.WifiError("radio-unavailable")
        if argv[0] == self.wpa_cli:
            return b"wpa_state=COMPLETED\nssid=Example Secure\n" if self.connected else b"wpa_state=SCANNING\n"
        return b""


class BrokerTests(unittest.TestCase):
    def test_config_never_contains_plain_password_and_bounds(self):
        data = wifi.config_for("Example Secure", "wpa2-psk", "examplepass")
        self.assertNotIn(b"examplepass", data)
        self.assertIn(b"psk=", data)
        self.assertEqual(wifi.parse_saved(data)[0][0], {"ssid": "Example Secure", "security": "wpa2-psk"})
        for password in ("short", "x" * 64, "a\npassword"):
            with self.assertRaises(wifi.WifiError):
                wifi.config_for("Example Secure", "wpa2-psk", password)
        with self.assertRaises(wifi.WifiError):
            wifi.config_for("Example Secure\n", "open")

    def test_scan_filters_unsupported_hidden_and_deduplicates(self):
        text = b"""BSS aa(on wlan0)\n\tSSID: Example Guest\n\tcapability: ESS\nBSS bb(on wlan0)\n\tSSID: Example Secure\n\tcapability: ESS Privacy\n\tRSN:\n\t * Authentication suites: PSK\nBSS cc(on wlan0)\n\tSSID: Legacy WEP\n\tcapability: ESS Privacy\nBSS dd(on wlan0)\n\tSSID: Example Guest\n"""
        self.assertEqual(wifi.parse_scan(text), [
            {"ssid": "Example Guest", "security": "open"},
            {"ssid": "Example Secure", "security": "wpa2-psk"},
            {"ssid": "Legacy WEP", "security": "unsupported"},
        ])
        self.assertFalse(wifi.candidate_completed(b"wpa_state=ASSOCIATING\nssid=Example Secure", "Example Secure"))
        self.assertTrue(wifi.candidate_completed(b"wpa_state=COMPLETED\nssid=Example Secure", "Example Secure"))

    def test_peer_idle_is_not_cancelled_and_close_is(self):
        a, b = socket.socketpair()
        try:
            a.settimeout(3)
            self.assertFalse(wifi.peer_closed(a))
            b.close()
            self.assertTrue(wifi.peer_closed(a))
        finally:
            a.close()

    def test_operator_saved_identity_and_bounded_fixed_output(self):
        operator = b'ctrl_interface=DIR=/run/k230-wifi/wpa_supplicant GROUP=root\nnetwork={\n ssid="Example Secure"\n psk="examplepass"\n}\n'
        self.assertEqual(wifi.parse_saved(operator)[0][0],
                         {"ssid": "Example Secure", "security": "wpa2-psk"})
        radio = wifi.Radio()
        with self.assertRaisesRegex(wifi.WifiError, "response-too-large"):
            radio.fixed([sys.executable, "-c", "import sys;sys.stdout.write('x'*300000)"], timeout=2)
        with self.assertRaisesRegex(wifi.WifiError, "radio-timeout"):
            radio.fixed([sys.executable, "-c", "import time;time.sleep(1)"], timeout=0.03)

    def test_protocol_denies_other_user_bounds_and_no_secret_echo(self):
        radio = FakeRadio()
        broker = wifi.Broker(radio, allowed_uid=1000)
        request = b'{"schema":1,"op":"connect","ssid":"Example Secure","security":"wpa2-psk","password":"examplepass"}'
        self.assertEqual(broker.handle(1001, request)["error"], "denied")
        self.assertFalse(radio.calls)
        self.assertEqual(broker.handle(1000, b"{" )["error"], "invalid-request")
        self.assertEqual(broker.handle(1000, b"x" * 4097)["error"], "request-too-large")
        answer = broker.handle(1000, request)
        self.assertEqual((answer["state"], answer["result"]), ("ok", "saved"))
        self.assertNotIn("examplepass", str(answer))
        self.assertEqual(radio.calls, [("Example Secure", "wpa2-psk", "examplepass")])

    def test_connect_arms_recovery_before_stop_and_only_persists_after_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            radio = TrialRadio(Path(tmp))
            radio.connected = True
            fake_process = FakeProcess([])
            with patch.object(wifi.subprocess, "Popen", return_value=fake_process):
                answer = radio.connect("Example Secure", "wpa2-psk", "examplepass")
            self.assertEqual(answer["result"], "saved")
            self.assertTrue(fake_process.terminated)
            args = [" ".join(row) for row in radio.commands]
            self.assertIn("systemd-run", args[0])
            self.assertIn("systemctl stop k230-wifi.service", args[1])
            self.assertIn("systemctl start k230-wifi.service", args[-2])
            self.assertIn("systemctl stop k230-wifi-settings-restore.timer", args[-1])
            self.assertTrue(all("examplepass" not in arg and "Example Secure" not in arg for arg in args))
            self.assertEqual(radio.credential.stat().st_mode & 0o777, 0o600)

    def test_connect_preserves_other_saved_networks_and_replaces_only_selected(self):
        with tempfile.TemporaryDirectory() as tmp:
            radio = TrialRadio(Path(tmp))
            original = wifi.config_for("Example Guest", "open")
            radio._persist(original)
            radio.connected = True
            with patch.object(wifi.subprocess, "Popen", return_value=FakeProcess([])):
                radio.connect("Example Secure", "wpa2-psk", "examplepass")
            names = [identity["ssid"] for identity, _ in wifi.parse_saved(radio.credential.read_bytes())]
            self.assertEqual(names, ["Example Guest", "Example Secure"])
            radio.forget("Example Secure")
            self.assertEqual([identity["ssid"] for identity, _ in wifi.parse_saved(radio.credential.read_bytes())],
                             ["Example Guest"])

    def test_unsupported_legacy_config_refused_without_stopping_prior_service(self):
        with tempfile.TemporaryDirectory() as tmp:
            radio = TrialRadio(Path(tmp))
            legacy = b"country=US\nnetwork={\n ssid=4578616d706c65\n psk=0000000000000000000000000000000000000000000000000000000000000000\n}\n"
            radio._persist(legacy)
            with self.assertRaisesRegex(wifi.WifiError, "unsupported-saved-config"):
                radio.connect("Example Secure", "wpa2-psk", "examplepass")
            self.assertEqual(radio.credential.read_bytes(), legacy)
            self.assertFalse(radio.commands)

    def test_failed_attempt_preserves_prior_credential_and_restores_service(self):
        with tempfile.TemporaryDirectory() as tmp:
            radio = TrialRadio(Path(tmp))
            previous = wifi.config_for("Example Guest", "open")
            radio._persist(previous)
            with patch.object(wifi.subprocess, "Popen", return_value=FakeProcess([])), \
                 patch.object(wifi.time, "monotonic", side_effect=[0, 100]):
                with self.assertRaisesRegex(wifi.WifiError, "connection-timeout"):
                    radio.connect("Example Secure", "wpa2-psk", "examplepass")
            self.assertEqual(radio.credential.read_bytes(), previous)
            self.assertIn(("systemctl", "start", "k230-wifi.service"), radio.commands)

    def test_cancel_before_commit_keeps_prior_networks(self):
        with tempfile.TemporaryDirectory() as tmp:
            radio = TrialRadio(Path(tmp))
            previous = wifi.config_for("Example Guest", "open")
            radio._persist(previous)
            checks = iter([False, True])
            with patch.object(wifi.subprocess, "Popen", return_value=FakeProcess([])):
                with self.assertRaisesRegex(wifi.WifiError, "cancelled"):
                    radio.connect("Example Secure", "wpa2-psk", "examplepass",
                                  cancelled=lambda: next(checks, True))
            self.assertEqual(radio.credential.read_bytes(), previous)
            self.assertIn(("systemctl", "start", "k230-wifi.service"), radio.commands)

    def test_failed_service_restart_restores_prior_credential_for_watchdog(self):
        with tempfile.TemporaryDirectory() as tmp:
            radio = TrialRadio(Path(tmp))
            previous = wifi.config_for("Example Guest", "open")
            radio._persist(previous)
            radio.connected = True
            radio.fail_start = True
            with patch.object(wifi.subprocess, "Popen", return_value=FakeProcess([])):
                with self.assertRaisesRegex(wifi.WifiError, "service-restart-failed"):
                    radio.connect("Example Secure", "wpa2-psk", "examplepass")
            self.assertEqual(radio.credential.read_bytes(), previous)
            self.assertNotIn(("systemctl", "stop", "k230-wifi-settings-restore.timer"), radio.commands)

    def test_forget_removes_only_matching_saved_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            radio = TrialRadio(Path(tmp))
            radio._persist(wifi.config_for("Example Guest", "open"))
            with self.assertRaises(wifi.WifiError):
                radio.forget("Other")
            self.assertTrue(radio.credential.exists())
            radio.forget("Example Guest")
            self.assertFalse(radio.credential.exists())


if __name__ == "__main__":
    unittest.main()
