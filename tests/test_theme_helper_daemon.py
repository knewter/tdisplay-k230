"""Host parity/latency proof for the persistent theme-catalog helper.

Compares `tools/theme_client.py` talking to `tools/theme_helperd.py` over a
real Unix socket against a direct `theme_catalog.handle()` call, for every
action the chooser uses. No board, no Python process-start-up measurement
here (that only shows up on the K230's slower core; see
`docs/evidence/omarchy-themes/theme-swap-jank/README.md`) -- this proves
correctness and fallback safety, which is what a host can prove.
"""
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import theme_catalog as catalog
import theme_client as client
import theme_helperd as helperd
from theme_transaction import activate_generation


COLORS = ('background="#101820"\nforeground="#e0e5e8"\naccent="#778899"\n'
          'red="#dd5555"\ngreen="#55dd55"\nyellow="#dddd55"\n'
          'blue="#5555dd"\nmagenta="#dd55dd"\ncyan="#55dddd"\nmode="dark"\n')


def theme(path):
    path.mkdir(parents=True)
    (path / "colors.toml").write_text(COLORS)
    (path / "backgrounds").mkdir()
    (path / "backgrounds/portrait.png").write_bytes(b"not decoded in this test")
    return path


class HelperDaemonTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.user, self.builtins, self.state, self.runtime = (
            self.base / name for name in ("user", "builtins", "state", "runtime")
        )
        self.runtime.mkdir(mode=0o700)
        self.socket_path = self.runtime / "theme-helper.sock"
        fixed = {
            "--tools": catalog.activation.HOST_TOOLS,
            "--wallpaper-cache-tool": None,
            "--user-themes": self.user,
            "--builtins": self.builtins,
            "--state-root": self.state,
            "--socket": self.base / "missing-appearance.sock",
            "--rust-socket": None,
            "--deck-socket": None,
            "--keyboard-runtime-dir": self.base / "keyboard-runtime",
            "--pkill": "pkill",
        }
        self.daemon = helperd.Helperd(fixed, self.socket_path)
        self.stop = threading.Event()
        self.thread = threading.Thread(
            target=self.daemon.serve_forever, args=(self.stop,), daemon=True
        )
        self.thread.start()
        self.addCleanup(self._stop_daemon)
        deadline = time.monotonic() + 2.0
        while not self.socket_path.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(self.socket_path.exists(), "daemon socket never appeared")

    def _stop_daemon(self):
        self.stop.set()
        self.thread.join(timeout=2.0)

    def client_args(self, *extra):
        return ["--helper-socket", str(self.socket_path),
                "--user-themes", str(self.user), "--builtins", str(self.builtins),
                "--state-root", str(self.state), "--socket", str(self.base / "missing-appearance.sock"),
                *extra]

    def run_via_daemon(self, *action_args):
        out_lines = []

        def fake_print(value, file=None):
            out_lines.append(value)

        with mock.patch("builtins.print", side_effect=fake_print):
            status = client.main(self.client_args(*action_args))
        return status, json.loads(out_lines[0])

    def run_direct(self, *action_args):
        out_lines = []

        def fake_print(value, file=None):
            out_lines.append(value)

        with mock.patch("builtins.print", side_effect=fake_print):
            status = catalog.main(["--user-themes", str(self.user), "--builtins", str(self.builtins),
                                   "--state-root", str(self.state),
                                   "--socket", str(self.base / "missing-appearance.sock"),
                                   *action_args])
        return status, json.loads(out_lines[0])

    def test_list_and_preview_match_the_direct_cli_byte_for_byte(self):
        theme(self.builtins / "catppuccin")
        via_daemon = self.run_via_daemon("list", "--json")
        direct = self.run_direct("list", "--json")
        self.assertEqual(via_daemon, direct)

        entry_id = direct[1]["themes"][0]["id"]
        via_daemon = self.run_via_daemon("preview", "--json", entry_id)
        direct = self.run_direct("preview", "--json", entry_id)
        self.assertEqual(via_daemon, direct)

    def test_activate_through_the_daemon_reaches_the_real_two_phase_transaction(self):
        theme(self.builtins / "night")
        entry_id = self.run_via_daemon("list", "--json")[1]["themes"][0]["id"]
        generation = self.run_via_daemon("preview", "--json", entry_id)[1]["generation"]

        phases = []

        def transport(endpoint, phase, generation):
            phases.append(phase)

        def commit(generation, **kwargs):
            activate_generation(generation, **kwargs, transport=transport)

        with mock.patch.object(catalog, "activate_generation", side_effect=commit):
            status, result = self.run_via_daemon(
                "activate", "--json", entry_id, "--expected-generation", generation
            )
        self.assertEqual(status, 0, result)
        self.assertTrue(result["activated"])
        self.assertEqual(phases, ["prepare", "commit"])
        self.assertEqual((self.state / "active").resolve().name, generation)

    def test_a_bad_request_never_wedges_the_daemon_for_the_next_one(self):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(2.0)
            connection.connect(str(self.socket_path))
            connection.sendall(b"not json at all\n")
            reply = json.loads(connection.recv(65536).decode())
        self.assertEqual(reply["exit_code"], 1)
        self.assertIn("error", reply["result"])
        # The daemon must still answer a good request right after a bad one.
        theme(self.builtins / "catppuccin")
        status, _ = self.run_via_daemon("list", "--json")
        self.assertEqual(status, 0)

    def test_client_subprocess_never_imports_theme_catalog_when_the_daemon_answers(self):
        """The whole point of `theme_client.py` not importing `theme_catalog`
        eagerly: board evidence attributes most of the ~1.2 s per
        `k230-theme` call to that import chain, not bare interpreter
        start-up, so a real subprocess (not this test's own already-warm
        interpreter) must show it never gets pulled in on the daemon path.
        """
        theme(self.builtins / "catppuccin")
        tools_path = Path(__file__).resolve().parents[1] / "tools"
        completed = subprocess.run(
            [sys.executable, "-X", "importtime", str(tools_path / "theme_client.py"),
             "--helper-socket", str(self.socket_path),
             "--user-themes", str(self.user), "--builtins", str(self.builtins),
             "--state-root", str(self.state), "list", "--json"],
            capture_output=True, text=True, timeout=10, check=True,
        )
        result = json.loads(completed.stdout)
        self.assertEqual(result["themes"][0]["name"], "catppuccin")
        # -X importtime writes one "import time: ... | <module>" line per
        # module actually imported, to stderr.
        imported = {line.rsplit("|", 1)[-1].strip()
                    for line in completed.stderr.splitlines() if "import time:" in line}
        for heavy in ("theme_catalog", "theme_activate", "theme_transaction",
                     "theme_preferences", "keyboard_appearance"):
            self.assertNotIn(heavy, imported,
                             f"{heavy} was imported on the daemon-reachable fast path")

    def test_client_falls_back_to_the_direct_path_when_no_daemon_is_listening(self):
        theme(self.builtins / "catppuccin")
        missing_socket = self.base / "no-such-daemon.sock"
        out_lines = []

        def fake_print(value, file=None):
            out_lines.append(value)

        args = ["--helper-socket", str(missing_socket),
                "--user-themes", str(self.user), "--builtins", str(self.builtins),
                "--state-root", str(self.state), "--socket", str(self.base / "missing-appearance.sock"),
                "list", "--json"]
        with mock.patch("builtins.print", side_effect=fake_print):
            status = client.main(args)
        self.assertEqual(status, 0)
        direct = self.run_direct("list", "--json")
        self.assertEqual(json.loads(out_lines[0]), direct[1])


if __name__ == "__main__":
    unittest.main()
