"""Exercise the real GLib desktop provider with isolated XDG directories."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Catalog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.binary = Path(cls.tmp.name) / "catalog"
        flags = shlex.split(subprocess.check_output(
            ["pkg-config", "--cflags", "--libs", "gio-unix-2.0"], text=True))
        subprocess.run(["cc", "-O2", "-Wall", "-o", str(cls.binary),
                        str(ROOT / "nix/touch-launcher/catalog.c"), *flags], check=True)

    def env(self, root):
        return os.environ | {
            "XDG_DATA_HOME": str(root / "home"),
            "XDG_DATA_DIRS": str(root / "system"),
            "XDG_CURRENT_DESKTOP": "sway",
            "PATH": str(root / "bin") + ":" + os.environ["PATH"],
        }

    def entry(self, directory, name, body):
        path = directory / "applications" / (name + ".desktop")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("[Desktop Entry]\nType=Application\n" + body)
        return path

    def listing(self, env):
        return subprocess.check_output([self.binary, "list"], env=env, text=True)

    def test_visibility_precedence_add_remove_and_hidden_override(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            system, home = root / "system", root / "home"
            self.entry(system, "same", "Name=System\nExec=true\n")
            self.entry(home, "same", "Name=Home\nExec=true\n")
            for name, extra in [
                ("hidden", "Hidden=true"), ("nodisplay", "NoDisplay=true"),
                ("try", "TryExec=k230-deliberately-missing-command"),
                ("only", "OnlyShowIn=GNOME;"), ("not", "NotShowIn=sway;"),
            ]:
                self.entry(home, name, "Name=Excluded\nExec=true\n" + extra + "\n")
            env = self.env(root)
            self.assertEqual(self.listing(env), "same.desktop\tHome\t0\n")
            added = self.entry(home, "added", "Name=Added\nExec=true\n")
            self.assertIn("added.desktop\tAdded\t0", self.listing(env))
            added.unlink()
            self.assertNotIn("added.desktop", self.listing(env))
            self.entry(home, "same", "Name=Hidden override\nHidden=true\n")
            self.assertEqual(self.listing(env), "")
            failed = subprocess.run([self.binary, "launch", "same.desktop"],
                                    env=env, capture_output=True)
            self.assertNotEqual(failed.returncode, 0)

    def test_escaped_names_do_not_break_catalogue_records(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.entry(root / "home", "escaped", "Name=One\\tTwo\\nThree\nExec=true\n")
            output = self.listing(self.env(root))
            self.assertEqual(output, "escaped.desktop\tOne\\tTwo\\nThree\t0\n")

    def test_glib_launch_preserves_argv_fields_and_working_directory(self):
        for terminal in [False, True]:
            with self.subTest(terminal=terminal), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "bin").mkdir()
                log, term_log = root / "app.json", root / "terminal.json"
                app = root / "bin" / "app"
                app.write_text(f"#!{sys.executable}\n" +
                    "import os,sys,json,pathlib\n"
                    "pathlib.Path(os.environ['APP_LOG']).write_text(json.dumps("
                    "{'argv':sys.argv[1:],'cwd':os.getcwd()}))\n")
                app.chmod(0o755)
                helper = root / "bin" / "xdg-terminal-exec"
                helper.write_text(f"#!{sys.executable}\n" +
                    "import os,sys,json,pathlib\n"
                    "pathlib.Path(os.environ['TERM_LOG']).write_text(json.dumps(sys.argv[1:]))\n"
                    "os.execvp(sys.argv[1],sys.argv[1:])\n")
                helper.chmod(0o755)
                work = root / "working directory"
                work.mkdir()
                desktop = self.entry(root / "home", "quoted",
                    'Name=Quoted Name\nExec=app "two words" %c %k %% %f %i "$(no-shell)"\n'
                    'Icon=test-icon\nPath=' + str(work) + '\nTerminal=' + str(terminal).lower() + '\n')
                env = self.env(root) | {"APP_LOG": str(log), "TERM_LOG": str(term_log)}
                subprocess.run([self.binary, "launch", "quoted.desktop"], env=env, check=True)
                # Launch is asynchronous; keep the temporary executable alive
                # until the spawned program completes its observable write.
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    try:
                        observed = json.loads(log.read_text())
                        break
                    except (FileNotFoundError, json.JSONDecodeError):
                        time.sleep(0.02)
                else:
                    self.fail("launched fixture did not finish")
                expected = ["two words", "Quoted Name", str(desktop), "%",
                            "--icon", "test-icon", "$(no-shell)"]
                self.assertEqual(observed, {"argv": expected, "cwd": str(work)})
                if terminal:
                    self.assertEqual(json.loads(term_log.read_text()), ["app", *expected])
                else:
                    self.assertFalse(term_log.exists())


if __name__ == "__main__":
    unittest.main()
