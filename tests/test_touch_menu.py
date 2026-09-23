"""Protocol and action tests for nix/touch-menu.sh; no Nix build required."""
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import time
import unittest


ROOT = pathlib.Path(__file__).parents[1]
MENU = ROOT / "nix" / "touch-menu.sh"
TREE = json.dumps({"type": "root", "nodes": [{"type": "workspace", "nodes": [
    {"type": "con", "id": 42, "pid": 1, "app_id": "other", "name": "Other app"},
    {"type": "con", "id": 43, "pid": 2, "app_id": "k230-terminal", "name": "Terminal"},
    {"type": "con", "id": 44, "pid": 3, "app_id": "k230-monitor", "name": "Monitor"},
]}]})


class TouchMenuTest(unittest.TestCase):
    def run_menu(self, events, tree=TREE):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            log = root / "actions"
            swaymsg = root / "swaymsg"
            swaymsg.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = -t ]; then printf '%s\\n' \"$K230_TEST_TREE\"; "
                "else printf 'swaymsg %s\\n' \"$*\" >> \"$K230_TEST_LOG\"; fi\n"
            )
            for name in ("foot", "pkill", "sudo", "launcher"):
                path = root / name
                exit_status = 'exit "${K230_TEST_SUDO_STATUS:-0}"\n' if name == "sudo" else ""
                htoprc = 'printf "HTOPRC=%s\\n" "${HTOPRC:-}" >> "$K230_TEST_LOG"\n' if name == "foot" else ""
                path.write_text("#!/bin/sh\nprintf '%s %s\\n' \"$0\" \"$*\" >> \"$K230_TEST_LOG\"\n" + htoprc + exit_status)
                path.chmod(0o755)
            video = root / "video-session"
            video.write_text("#!/bin/sh\nprintf 'video %s\\n' \"$*\" >> \"$K230_TEST_LOG\"\n")
            video.chmod(0o755)
            swaymsg.chmod(0o755)
            env = os.environ | {
                "K230_SWAYMSG": str(swaymsg), "K230_FOOT": str(root / "foot"),
                "K230_HTOP": "/mock/htop", "K230_JQ": shutil.which("jq"),
                "K230_SED": shutil.which("sed"), "K230_PKILL": str(root / "pkill"),
                "K230_SUDO": str(root / "sudo"), "K230_SYSTEMCTL": "/mock/systemctl",
                "K230_TERMINAL_CONFIG": "/mock/terminal.ini",
                "K230_MONITOR_CONFIG": "/mock/monitor.ini",
                "K230_HTOPRC": "/mock/monitor.htoprc", "K230_LAUNCHER": str(root / "launcher"),
                "K230_VIDEO_SESSION": str(video),
                "K230_TEST_TREE": tree, "K230_TEST_LOG": str(log),
            }
            self.assertIsNotNone(env["K230_JQ"], "jq is required by the tested menu")
            self.assertIsNotNone(env["K230_SED"], "sed is required by the tested menu")
            result = subprocess.run(["bash", str(MENU)], input="\n".join(events) + "\n",
                                    text=True, capture_output=True, env=env, check=True)
            # The production launcher intentionally backgrounds foot. Give the
            # stub one scheduling turn before reading its action log.
            time.sleep(0.02)
            return result.stdout, log.read_text() if log.exists() else ""

    def frames(self, stream):
        lines = stream.splitlines()
        self.assertEqual(json.loads(lines[0]), {"version": 1, "click_events": True})
        self.assertEqual(lines[1], "[")
        # Each status line is a single valid i3bar array element; no extra
        # header/open-array may appear after click events.
        self.assertTrue(all(not line.startswith('{') and line != "[" for line in lines[2:]))
        return [json.loads(line.rstrip(",")) for line in lines[2:]]

    def test_stream_and_whitespace_events(self):
        stream, actions = self.run_menu(['{"name": "apps"}', '{"name":"back"}', '{ "name" : "system" }'])
        frames = self.frames(stream)
        self.assertEqual([block["name"] for block in frames[0]], ["apps", "windows", "keyboard", "system"])
        self.assertEqual([block["name"] for block in frames[1]], ["apps", "windows", "keyboard", "system"])
        self.assertEqual([block["name"] for block in frames[3]], ["reboot", "poweroff", "back"])
        self.assertEqual([block["background"] for block in frames[0]], ["#2f6b4f", "#2b547c", "#6b4f2b", "#5e3d61"])
        self.assertTrue(all(block["color"] == "#ffffff" for block in frames[0]))
        self.assertIn('launcher ', actions)
        for frame in frames:
            self.assertLessEqual(sum(block["min_width"] for block in frame), 540)
            self.assertTrue(all(block["separator_block_width"] == 0 for block in frame))

    def test_actual_windows_and_focus(self):
        stream, actions = self.run_menu(['{"name":"windows"}', '{"name":"window:42"}'])
        frames = self.frames(stream)
        self.assertEqual([block["name"] for block in frames[1]], ["window:42", "home", "next-windows", "back"])
        self.assertIn('swaymsg [con_id=42] focus', actions)

    def test_window_paging_wraps_and_empty_windows_are_explicit(self):
        stream, _ = self.run_menu(['{"name":"windows"}', '{"name":"next-windows"}', '{"name":"next-windows"}', '{"name":"next-windows"}'])
        frames = self.frames(stream)
        self.assertEqual(frames[1][0]["name"], "window:42")
        self.assertEqual(frames[2][0]["name"], "window:43")
        self.assertEqual(frames[3][0]["name"], "window:44")
        self.assertEqual(frames[4][0]["name"], "window:42")
        empty = json.dumps({"type": "root", "nodes": []})
        stream, _ = self.run_menu(['{"name":"windows"}'], empty)
        self.assertEqual([block["name"] for block in self.frames(stream)[1]], ["no-windows", "home", "back"])

    def test_existing_app_focus_and_missing_app_recovery(self):
        _, actions = self.run_menu(['{"name":"terminal"}'])
        self.assertIn('swaymsg [app_id="k230-terminal"] focus', actions)
        missing = json.dumps({"type": "root", "nodes": []})
        _, actions = self.run_menu(['{"name":"terminal"}'], missing)
        self.assertIn('foot --config /mock/terminal.ini', actions)
        _, actions = self.run_menu(['{"name":"monitor"}'], missing)
        self.assertIn('foot --config /mock/monitor.ini -e /mock/htop', actions)
        self.assertIn('HTOPRC=/mock/monitor.htoprc', actions)
        _, actions = self.run_menu(['{"name":"new-terminal"}'])
        self.assertIn('foot --config /mock/terminal.ini', actions)
        self.assertNotIn('swaymsg [app_id="k230-terminal"] focus', actions)

    def test_cancel_does_not_call_sudo_and_confirm_does(self):
        _, actions = self.run_menu(['{"name":"system"}', '{"name":"reboot"}', '{"name":"cancel"}'])
        self.assertNotIn('sudo', actions)
        _, actions = self.run_menu(['{"name":"system"}', '{"name":"poweroff"}', '{"name":"confirm-poweroff"}'])
        self.assertIn('sudo -n /mock/systemctl poweroff', actions)

    def test_failed_or_out_of_context_confirmation_keeps_menu_recoverable(self):
        stream, actions = self.run_menu(['{"name":"confirm-reboot"}'])
        self.assertNotIn('sudo', actions)
        self.assertEqual(self.frames(stream)[1][0]["name"], "apps")
        old_status = os.environ.get("K230_TEST_SUDO_STATUS")
        os.environ["K230_TEST_SUDO_STATUS"] = "1"
        try:
            stream, actions = self.run_menu(['{"name":"system"}', '{"name":"reboot"}', '{"name":"confirm-reboot"}', '{"name":"back"}'])
        finally:
            if old_status is None:
                del os.environ["K230_TEST_SUDO_STATUS"]
            else:
                os.environ["K230_TEST_SUDO_STATUS"] = old_status
        self.assertIn('sudo -n /mock/systemctl reboot', actions)
        frames = self.frames(stream)
        self.assertEqual(frames[3][0]["name"], "retry-system")
        self.assertEqual(frames[4][0]["name"], "apps")


if __name__ == "__main__":
    unittest.main()
