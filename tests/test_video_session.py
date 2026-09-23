"""Lifecycle tests for the shell-owned video wrapper; no Nix or board required."""
import os
import pathlib
import stat
import subprocess
import tempfile
import time
import unittest

ROOT = pathlib.Path(__file__).parents[1]
SCRIPT = ROOT / "nix" / "video-session.sh"


class VideoSessionTest(unittest.TestCase):
    def env(self, root, player, **extra):
        return os.environ | {
            "K230_VIDEO_PLAYER": str(player),
            "K230_VIDEO_RUNTIME_DIR": str(root),
            "K230_VIDEO_PID_FILE": str(root / "video.pid"),
            "K230_VIDEO_LOG": str(root / "video.log"),
            "K230_VIDEO_PUBLIC_URL": "https://example.invalid/public.mpd",
            **extra,
        }

    def fake_player(self, root, body):
        player = root / "fake-mpv"
        player.write_text("#!/bin/sh\nprintf '%s\\n' \"$*\" >> \"$FAKE_ARGS\"\n" + body)
        player.chmod(0o755)
        return player

    def run_session(self, root, player, *args, **env_extra):
        env = self.env(root, player, FAKE_ARGS=str(root / "args"), **env_extra)
        return subprocess.run(["bash", str(SCRIPT), *args], env=env, text=True,
                              capture_output=True)

    def test_eof_cleans_pid_and_passes_software_defaults(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            player = self.fake_player(root, "exit 0\n")
            result = self.run_session(root, player, "run")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((root / "video.pid").exists())
            args = (root / "args").read_text()
            self.assertIn("--vd=h264", args)
            self.assertIn("--geometry=480x270", args)
            self.assertIn("--audio=no", args)
            self.assertIn("https://example.invalid/public.mpd", args)

    def test_mvx_is_opt_in_and_lists_software_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            player = self.fake_player(root, "exit 0\n")
            result = self.run_session(root, player, "run", K230_VIDEO_MODE="mvx")
            self.assertEqual(result.returncode, 0, result.stderr)
            args = (root / "args").read_text()
            self.assertIn("--vd=h264_v4l2m2m", args)
            self.assertIn("--correct-pts=no", args)
            self.assertIn("--container-fps-override=30", args)
            self.assertIn("--sws-scaler=point", args)
            self.assertIn("--geometry=568x320", args)
            self.assertIn("--audio=no", args)

    def test_mvx_failure_restarts_with_software_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            player = root / "fake-mpv"
            player.write_text(
                "#!/bin/sh\n"
                "printf '%s\\n' \"$*\" >> \"$FAKE_ARGS\"\n"
                "n=$(wc -l < \"$FAKE_ARGS\")\n"
                "case \"$*\" in *h264_v4l2m2m*) [ \"$n\" -eq 1 ] && exit 9;; esac\n"
                "exit 0\n"
            )
            player.chmod(0o755)
            result = self.run_session(root, player, "run-mvx")
            self.assertEqual(result.returncode, 0, result.stderr)
            invocations = (root / "args").read_text().splitlines()
            self.assertEqual(len(invocations), 2)
            self.assertIn("--vd=h264_v4l2m2m", invocations[0])
            self.assertIn("--vd=h264", invocations[1])
            self.assertNotIn("--container-fps-override=30", invocations[1])

    def test_unresponsive_player_is_stopped_by_deadline(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            player = self.fake_player(root, "sleep 30\n")
            result = self.run_session(root, player, "run", K230_VIDEO_DEADLINE="0.1")
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root / "video.pid").exists())

    def test_player_failure_is_returned_and_state_is_clean(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            player = self.fake_player(root, "exit 7\n")
            result = self.run_session(root, player, "run")
            self.assertEqual(result.returncode, 7)
            self.assertFalse((root / "video.pid").exists())

    def test_private_playlist_content_never_enters_player_argv(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            url_file = root / "private.playlist"
            url_file.write_text("https://private.example.invalid/secret-token.mpd\n")
            url_file.chmod(stat.S_IRUSR | stat.S_IWUSR)
            player = self.fake_player(root, "exit 0\n")
            result = self.run_session(root, player, "run", K230_VIDEO_URL_FILE=str(url_file))
            self.assertEqual(result.returncode, 0, result.stderr)
            args = (root / "args").read_text()
            self.assertIn("--playlist=" + str(url_file), args)
            self.assertNotIn("secret-token", args)

    def test_stop_only_kills_owned_child_and_cleans_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            player = self.fake_player(root, "trap 'exit 143' TERM\nsleep 30\n")
            env = self.env(root, player, FAKE_ARGS=str(root / "args"))
            process = subprocess.Popen(["bash", str(SCRIPT), "run"], env=env,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            pidfile = root / "video.pid"
            for _ in range(20):
                if pidfile.exists(): break
                time.sleep(0.05)
            self.assertTrue(pidfile.exists())
            result = subprocess.run(["bash", str(SCRIPT), "stop"], env=env,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            process.wait(timeout=5)
            self.assertFalse(pidfile.exists())

    def test_duplicate_run_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            player = self.fake_player(root, "sleep 30\n")
            env = self.env(root, player, FAKE_ARGS=str(root / "args"))
            process = subprocess.Popen(["bash", str(SCRIPT), "run"], env=env)
            try:
                pidfile = root / "video.pid"
                for _ in range(20):
                    if pidfile.exists(): break
                    time.sleep(0.05)
                result = subprocess.run(["bash", str(SCRIPT), "run"], env=env,
                                        capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("already", result.stderr)
            finally:
                subprocess.run(["bash", str(SCRIPT), "stop"], env=env)
                process.wait(timeout=5)

    def test_stop_does_not_kill_pid_with_wrong_starttime(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            player = self.fake_player(root, "sleep 30\n")
            unrelated = subprocess.Popen(["sleep", "10"])
            try:
                stat_line = pathlib.Path(f"/proc/{unrelated.pid}/stat").read_text()
                starttime = stat_line.rsplit(") ", 1)[1].split()[19]
                (root / "video.pid").write_text(f"{unrelated.pid} {starttime} 999999\n")
                result = self.run_session(root, player, "stop")
                self.assertEqual(result.returncode, 0)
                self.assertIsNone(unrelated.poll())
                self.assertFalse((root / "video.pid").exists())
            finally:
                unrelated.terminate()
                unrelated.wait(timeout=3)


if __name__ == "__main__":
    unittest.main()
