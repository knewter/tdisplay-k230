"""Native host protocol fixture; Wayland presentation still needs device proof."""

from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import theme_transaction as tx  # noqa: E402


HARNESS = r'''
#include "appearance.h"
#include <poll.h>
#include <stdio.h>
#include <time.h>
#include <unistd.h>
static bool redraw(void) { return true; }
int main(int argc, char **argv) {
  if (argc!=2 || k230_appearance_start(argv[1])) return 2;
  bool saw_theme=false;
  for (int n=0; n<300; n++) {
    struct pollfd fds[2]={{k230_appearance_listener_fd(),POLLIN,0},
                          {k230_appearance_client_fd(),POLLIN|POLLHUP,0}};
    poll(fds,2,10);
    k230_appearance_service((fds[0].revents&POLLIN)!=0,
                            (fds[1].revents&(POLLIN|POLLHUP))!=0,redraw);
    if (k230_appearance.background==0xff202830) saw_theme=true;
    if (saw_theme && k230_appearance.background==0xff111827) {
      k230_appearance_stop(); puts("applied-and-rolled-back"); return 0;
    }
  }
  k230_appearance_stop(); return 3;
}
'''


class ShellAppearanceReceiver(unittest.TestCase):
    def test_prepare_commit_and_rollback_socket_protocol(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "receiver-test.c"
            source.write_text(HARNESS)
            binary = root / "receiver-test"
            pkg = subprocess.check_output(
                ["pkg-config", "--cflags", "--libs", "json-glib-1.0"], text=True).split()
            subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                            "-I", str(ROOT / "nix/touch-launcher"), str(source),
                            str(ROOT / "nix/touch-launcher/appearance.c"), *pkg,
                            "-o", str(binary)], check=True)
            generation = root / "generations" / ("a" * 24)
            generation.mkdir(parents=True)
            (generation / "report.json").write_text(json.dumps({
                "generation": generation.name,
                "palette": {"background": "#202830", "foreground": "#ffffff",
                            "accent": "#778899"},
            }))
            process = subprocess.Popen([str(binary), str(root)], stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True)
            endpoint = root / "appearance.sock"
            try:
                for _ in range(100):
                    if endpoint.is_socket():
                        break
                    time.sleep(0.01)
                self.assertTrue(endpoint.is_socket())
                tx.exchange(endpoint, "prepare", generation)
                tx.exchange(endpoint, "commit", generation)
                tx.exchange(endpoint, "rollback", None)
                stdout, stderr = process.communicate(timeout=4)
                self.assertEqual(process.returncode, 0, stderr)
                self.assertEqual(stdout.strip(), "applied-and-rolled-back")
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=2)


if __name__ == "__main__":
    unittest.main()
