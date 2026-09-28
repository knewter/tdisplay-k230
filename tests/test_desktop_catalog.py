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

    def describe(self, env):
        rows = subprocess.check_output([self.binary, "describe"], env=env, text=True)
        return [line.split("\t") for line in rows.splitlines()]

    def test_curation_suppresses_endpoints_demotes_duplicates_and_retains_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            system = root / "system"
            self.entry(system, "footclient", "Name=Foot Client\nExec=true\n")
            self.entry(system, "foot-server", "Name=Foot Server\nExec=true\n")
            self.entry(system, "foot", "Name=Foot\nExec=true\n")
            self.entry(system, "htop", "Name=Htop\nExec=true\n")
            self.entry(system, "zeta", "Name=Zeta Notes\nComment=Write short notes\nExec=true\n")
            self.entry(system, "alpha", "Name=Alpha\nGenericName=Viewer\nExec=true\n")
            self.entry(system, "bare", "Name=Bare\nExec=true\n")
            env = self.env(root)
            rows = self.describe(env)
            ids = [row[0] for row in rows]
            # Endpoints never appear as peer applications.
            self.assertNotIn("footclient.desktop", ids)
            self.assertNotIn("foot-server.desktop", ids)
            # Unknown entries are retained ahead of demoted duplicates.
            self.assertEqual(ids, ["alpha.desktop", "bare.desktop", "zeta.desktop",
                                   "foot.desktop", "htop.desktop"])
            by_id = {row[0]: row[1:] for row in rows}
            self.assertEqual(by_id["zeta.desktop"], ["Zeta Notes", "Write short notes", "shown"])
            self.assertEqual(by_id["alpha.desktop"], ["Alpha", "Viewer", "shown"])
            self.assertEqual(by_id["bare.desktop"], ["Bare", "Installed application", "shown"])
            self.assertEqual(by_id["foot.desktop"][2], "demoted")
            self.assertEqual(by_id["htop.desktop"][2], "demoted")
            # Every visible card has an action name and a non-empty description.
            for row in rows:
                self.assertTrue(row[1] and row[2])
            # Only visible entries count towards the Apps page count.
            self.assertEqual(len(self.listing(env).splitlines()), 5)

    def test_curation_applies_after_refresh(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env = self.env(root)
            self.entry(root / "home", "plain", "Name=Plain\nExec=true\n")
            self.assertEqual([r[0] for r in self.describe(env)], ["plain.desktop"])
            added = self.entry(root / "home", "foot-server", "Name=Foot Server\nExec=true\n")
            self.entry(root / "home", "later", "Name=Later\nExec=true\n")
            self.assertEqual([r[0] for r in self.describe(env)], ["later.desktop", "plain.desktop"])
            added.unlink()
            self.assertEqual([r[0] for r in self.describe(env)], ["later.desktop", "plain.desktop"])

    def test_failed_launch_reports_short_copy_without_raw_path(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            # A missing working directory makes GLib's spawn fail with a
            # message naming the raw path.
            missing = root / "deliberately-missing-directory"
            self.entry(root / "home", "broken", f"Name=Broken\nExec=true\nPath={missing}\n")
            env = self.env(root)
            failed = subprocess.run([self.binary, "launch", "broken.desktop"],
                                    env=env, capture_output=True, text=True)
            self.assertNotEqual(failed.returncode, 0)
            self.assertEqual(failed.stdout, "Could not open Broken · Back returns to Apps\n")
            self.assertNotIn(str(root), failed.stdout)
            self.assertNotIn("/", failed.stdout)
            # The raw diagnostic remains available to logs.
            self.assertIn("launch failed:", failed.stderr)
            gone = subprocess.run([self.binary, "launch", "vanished.desktop"],
                                  env=env, capture_output=True, text=True)
            self.assertNotEqual(gone.returncode, 0)
            self.assertEqual(gone.stdout, "Could not open the application · Back returns to Apps\n")

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
