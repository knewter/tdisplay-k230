"""Native host protocol fixture; Wayland presentation still needs device proof."""

from pathlib import Path
import json
import os
import stat
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
#include <stdlib.h>
#include <time.h>
#include <unistd.h>
static bool redraw(void) { return true; }
int main(int argc, char **argv) {
  if (argc!=4 || k230_appearance_start(argv[1])) return 2;
  unsigned theme=(unsigned)strtoul(argv[2],NULL,16);
  unsigned restored=(unsigned)strtoul(argv[3],NULL,16);
  bool saw_theme=false;
  unsigned foreground=0,tile=0,selected=0,error=0;
  for (int n=0; n<300; n++) {
    struct pollfd fds[2]={{k230_appearance_listener_fd(),POLLIN,0},
                          {k230_appearance_client_fd(),POLLIN|POLLHUP,0}};
    poll(fds,2,10);
    k230_appearance_service((fds[0].revents&POLLIN)!=0,
                            (fds[1].revents&(POLLIN|POLLHUP))!=0,redraw);
    if (k230_appearance.background==theme) {
      saw_theme=true; foreground=k230_appearance.foreground;
      tile=k230_appearance.tile; selected=k230_appearance.selected;
      error=k230_appearance_error();
    }
    if (saw_theme && k230_appearance.background==restored) {
      k230_appearance_stop();
      printf("applied-and-rolled-back %08x %08x %08x %08x\n",
             foreground,tile,selected,error); return 0;
    }
  }
  k230_appearance_stop(); return 3;
}
'''


class ShellAppearanceReceiver(unittest.TestCase):
    @staticmethod
    def contrast(first, second):
        def luminance(color):
            channels = [(color >> shift) & 255 for shift in (16, 8, 0)]
            linear = [c / 255 / 12.92 if c / 255 <= 0.04045
                      else ((c / 255 + 0.055) / 1.055) ** 2.4 for c in channels]
            return sum(a * b for a, b in zip(linear, (0.2126, 0.7152, 0.0722)))
        hi, lo = sorted((luminance(first), luminance(second)), reverse=True)
        return (hi + 0.05) / (lo + 0.05)

    def run_case(self, *, restart=False, light=False):
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
            old = root / "generations" / ("b" * 24)
            old.mkdir(parents=True)
            (old / "report.json").write_text(json.dumps({
                "generation": old.name,
                "palette": {"background": "#102030", "foreground": "#ffffff"},
            }))
            if restart:
                (root / "active").symlink_to(old)
            generation = root / "generations" / ("a" * 24)
            generation.mkdir(parents=True)
            background = "#f0f0f0" if light else "#202830"
            foreground = "#202020" if light else "#ffffff"
            tile = "#e4e4e4" if light else "#283848"
            selected = "#d8d8d8" if light else "#344454"
            (generation / "report.json").write_text(json.dumps({
                "generation": generation.name,
                "palette": {"background": background, "foreground": foreground,
                            "dark_background": tile, "lighter_background": selected,
                            "accent": "#778899"},
            }))
            restored = "ff102030" if restart else "ff111827"
            process = subprocess.Popen([str(binary), str(root),
                                        "fff0f0f0" if light else "ff202830", restored], stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True)
            endpoint = root / "appearance.sock"
            try:
                for _ in range(100):
                    if endpoint.is_socket():
                        break
                    time.sleep(0.01)
                self.assertTrue(endpoint.is_socket())
                self.assertEqual(stat.S_IMODE(endpoint.stat().st_mode), 0o600)
                if not restart:
                    with self.assertRaisesRegex(tx.TransactionError, "shell rejected rollback"):
                        tx.exchange(endpoint, "rollback", None)
                tx.exchange(endpoint, "prepare", generation)
                tx.exchange(endpoint, "commit", generation)
                tx.exchange(endpoint, "rollback", old if restart else None)
                stdout, stderr = process.communicate(timeout=4)
                self.assertEqual(process.returncode, 0, stderr)
                marker, rendered_fg, rendered_tile, rendered_selected, rendered_error = stdout.strip().split()
                self.assertEqual(marker, "applied-and-rolled-back")
                bg = int(background[1:], 16)
                fg = int(rendered_fg, 16)
                self.assertGreaterEqual(self.contrast(bg, fg), 4.5)
                self.assertGreaterEqual(self.contrast(int(rendered_tile, 16), fg), 4.5)
                self.assertGreaterEqual(self.contrast(int(rendered_selected, 16), fg), 4.5)
                self.assertGreaterEqual(self.contrast(bg, int(rendered_error, 16)), 4.5)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=2)

    def test_prepare_commit_and_rollback_socket_protocol(self):
        self.run_case()

    def test_restarted_receiver_restores_persistent_previous_generation(self):
        self.run_case(restart=True)

    def test_light_palette_keeps_launcher_labels_legible(self):
        self.run_case(light=True)


if __name__ == "__main__":
    unittest.main()
