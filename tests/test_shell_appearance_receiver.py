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
static int submitted;
static bool redraw(void) { submitted++; return true; }
int main(int argc, char **argv) {
  if (argc!=6 || k230_appearance_start(argv[1],argv[1],argv[5])) return 2;
  unsigned theme=(unsigned)strtoul(argv[2],NULL,16);
  unsigned restored=(unsigned)strtoul(argv[3],NULL,16);
  unsigned startup=(unsigned)strtoul(argv[4],NULL,16);
  if (k230_appearance.background!=startup) return 4;
  uint64_t startup_serial=k230_appearance_generation_serial();
  bool saw_theme=false;
  unsigned foreground=0,muted=0,tile=0,selected=0,error=0;
  for (int n=0; n<300; n++) {
    struct pollfd fds[2]={{k230_appearance_listener_fd(),POLLIN,0},
                          {k230_appearance_client_fd(),POLLIN|POLLHUP,0}};
    poll(fds,2,10);
    k230_appearance_service((fds[0].revents&POLLIN)!=0,
                            (fds[1].revents&(POLLIN|POLLHUP))!=0,redraw);
    if (!saw_theme && submitted>=1 && k230_appearance.background==theme) {
      struct k230_appearance_brush surface;
      struct k230_appearance_border border;
      double scale=0;
      if (!k230_appearance_brush("launcher","background",&surface)
          || surface.stop_count!=1 || surface.alpha<0.94 || surface.alpha>0.96
          || !k230_appearance_border("launcher","border",&border)
          || border.brush.stop_count!=2 || border.brush.angle_degrees!=45
          || border.width[0]!=1 || border.width[1]!=2
          || border.width[2]!=3 || border.width[3]!=4
          || !k230_appearance_number("spacing","scale",&scale) || scale!=1.25
          || !k230_appearance_icon_theme()
          || !k230_appearance_background_path()
          || k230_appearance_generation_serial()<=startup_serial) return 5;
      saw_theme=true; foreground=k230_appearance.foreground;
      muted=k230_appearance.muted;
      tile=k230_appearance.tile; selected=k230_appearance.selected;
      error=k230_appearance_error();
    }
    if (submitted>=2 && saw_theme && k230_appearance.background==restored) {
      k230_appearance_stop();
      printf("applied-and-rolled-back %08x %08x %08x %08x %08x\n",
             foreground,muted,tile,selected,error); return 0;
    }
  }
  k230_appearance_stop(); return 3;
}
'''


class ShellAppearanceReceiver(unittest.TestCase):
    @staticmethod
    def write_generation(path, palette, *, with_background=False):
        path.mkdir(parents=True)
        if with_background:
            assets = path / "theme/backgrounds"
            assets.mkdir(parents=True)
            (assets / "still.png").write_bytes(b"host-fixture")
            (path / "background").symlink_to("theme/backgrounds/still.png")
        (path / "report.json").write_text(json.dumps({"generation": path.name,
                                                       "palette": palette}))
        background = palette["background"]
        (path / "appearance.json").write_text(json.dumps({
            "version": 1, "generation": path.name, "icon_theme": "Yaru-purple",
            "background": "background" if with_background else None,
            "sections": {
                "launcher": {
                    "background": {"kind": "brush", "alpha": 0.95,
                                   "angle_degrees": 0,
                                   "stops": [{"argb": "#ff" + background[1:], "offset": 0}]},
                    "border": {"kind": "brush", "alpha": 0.7,
                               "angle_degrees": 45,
                               "stops": [{"argb": "#ff112233", "offset": 0},
                                         {"argb": "#ff445566", "offset": 1}]},
                    "border-width": {"kind": "width", "value": [1, 2, 3, 4]},
                },
                "spacing": {"scale": {"kind": "number", "value": 1.25}},
            },
        }))

    @staticmethod
    def contrast(first, second):
        def luminance(color):
            channels = [(color >> shift) & 255 for shift in (16, 8, 0)]
            linear = [c / 255 / 12.92 if c / 255 <= 0.04045
                      else ((c / 255 + 0.055) / 1.055) ** 2.4 for c in channels]
            return sum(a * b for a, b in zip(linear, (0.2126, 0.7152, 0.0722)))
        hi, lo = sorted((luminance(first), luminance(second)), reverse=True)
        return (hi + 0.05) / (lo + 0.05)

    def run_case(self, *, restart=False, light=False, palette=None, unavailable=False):
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
            self.write_generation(old, {"background": "#102030", "foreground": "#ffffff"})
            if restart:
                (root / "active").symlink_to(old)
            elif unavailable:
                (root / "active").symlink_to(root / "generations" / ("f" * 24))
            pinned = root / "pinned" / "generations" / ("c" * 24)
            self.write_generation(pinned, {"background": "#1e1e2e", "foreground": "#cdd6f4"})
            generation = root / "generations" / ("a" * 24)
            background = palette["background"] if palette else "#f0f0f0" if light else "#202830"
            foreground = palette["foreground"] if palette else "#202020" if light else "#ffffff"
            tile = palette["dark_background"] if palette else "#e4e4e4" if light else "#283848"
            selected = palette["lighter_background"] if palette else "#d8d8d8" if light else "#344454"
            self.write_generation(generation, {"background": background, "foreground": foreground,
                                               "dark_background": tile, "lighter_background": selected,
                                               "muted": palette.get("muted", foreground) if palette else foreground,
                                               "accent": "#778899"}, with_background=True)
            restored = "ff102030" if restart else "ff1e1e2e"
            startup = "ff102030" if restart else "ff1e1e2e"
            process = subprocess.Popen([str(binary), str(root),
                                        "ff" + background[1:], restored, startup, str(pinned)], stdout=subprocess.PIPE,
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
                marker, rendered_fg, rendered_muted, rendered_tile, rendered_selected, rendered_error = stdout.strip().split()
                self.assertEqual(marker, "applied-and-rolled-back")
                bg = int(background[1:], 16)
                fg = int(rendered_fg, 16)
                self.assertGreaterEqual(self.contrast(bg, fg), 4.5)
                self.assertGreaterEqual(self.contrast(bg, int(rendered_muted, 16)), 4.5)
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

    def test_missing_selected_generation_falls_back_to_pinned_default(self):
        self.run_case(unavailable=True)

    def test_pinned_dark_light_and_community_palette_contrast(self):
        # Values are the resolved palettes of the pinned task-1 fixtures.
        for palette in (
            {"background": "#eff1f5", "foreground": "#4c4f69", "muted": "#acb0be",
             "dark_background": "#e3e4e8", "lighter_background": "#dce0e8"},
            {"background": "#1e1e2e", "foreground": "#cdd6f4", "muted": "#585b70",
             "dark_background": "#161622", "lighter_background": "#313244"},
            {"background": "#1a2234", "foreground": "#cdd6ee", "muted": "#4e5784",
             "dark_background": "#141a27", "lighter_background": "#232c44"},
        ):
            with self.subTest(background=palette["background"]):
                self.run_case(palette=palette)


if __name__ == "__main__":
    unittest.main()
