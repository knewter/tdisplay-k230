#!/usr/bin/env python3
"""Exercise the compositor's drawer gesture and fixed-argv helper route."""
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CardDrawerRoute(unittest.TestCase):
    def test_gesture_and_trusted_helper(self):
        with tempfile.TemporaryDirectory(prefix="card-route-") as directory:
            path = Path(directory)
            include = path / "sway"
            include.mkdir()
            (include / "card_shell_route.h").write_bytes(
                (ROOT / "nix/card-shell/route.h").read_bytes()
            )
            program = path / "route-test.c"
            program.write_text(r'''
#include <assert.h>
#include <stdlib.h>
#include "sway/card_shell_route.h"
int main(int argc, char **argv) {
    assert(argc == 2);
    struct card_shell_drawer_gesture gesture = {0};
    card_shell_drawer_down(&gesture, 3, 200, 1100);
    card_shell_drawer_motion(&gesture, 3, 210, 1040, 72);
    assert(!card_shell_drawer_up(&gesture, 3));
    card_shell_drawer_down(&gesture, 3, 200, 1100);
    card_shell_drawer_motion(&gesture, 3, 210, 1000, 72);
    card_shell_drawer_motion(&gesture, 3, 210, 1090, 72);
    assert(!card_shell_drawer_up(&gesture, 3)); /* reversal */
    card_shell_drawer_down(&gesture, 3, 200, 1100);
    card_shell_drawer_motion(&gesture, 3, 350, 1000, 72);
    assert(!card_shell_drawer_up(&gesture, 3)); /* horizontal */
    card_shell_drawer_down(&gesture, 3, 200, 1100);
    card_shell_drawer_motion(&gesture, 3, 210, 1000, 72);
    card_shell_drawer_down(&gesture, 4, 210, 1000);
    assert(!card_shell_drawer_up(&gesture, 4));
    assert(!card_shell_drawer_up(&gesture, 3)); /* second contact cancels */
    card_shell_drawer_down(&gesture, 3, 200, 1100);
    card_shell_drawer_motion(&gesture, 3, 210, 1000, 72);
    card_shell_drawer_cancel(&gesture);
    assert(!card_shell_drawer_up(&gesture, 3));
    card_shell_drawer_down(&gesture, 3, 200, 1100);
    card_shell_drawer_motion(&gesture, 3, 210, 1000, 72);
    assert(card_shell_drawer_up(&gesture, 3));
    assert(!card_shell_drawer_up(&gesture, 3));
    card_shell_drawer_down(&gesture, 5, 200, 10);
    card_shell_shade_motion(&gesture, 5, 210, 110, 72);
    assert(card_shell_drawer_up(&gesture, 5));
    card_shell_drawer_down(&gesture, 5, 200, 10);
    card_shell_shade_motion(&gesture, 5, 350, 110, 72);
    assert(!card_shell_drawer_up(&gesture, 5));
    unsetenv("SWAY_K230_CARD_DRAWER_HELPER");
    assert(!card_shell_launch_surface("drawer"));
    setenv("SWAY_K230_CARD_DRAWER_HELPER", "relative/path", 1);
    assert(!card_shell_launch_surface("drawer"));
    setenv("SWAY_K230_CARD_DRAWER_HELPER", argv[1], 1);
    assert(!card_shell_launch_surface("unsupported"));
    /* "hide" is what the compositor's bottom-edge overlay escape (adapter.c
     * input_down) spawns to dismiss a mapped Drawer/Shade/Settings route --
     * see docs/design/shell-ux-critique.md S1.1 and
     * openspec/changes/the-shell-behaves-as-one-coherent-system/. Checked
     * before the final "shade" call below so the capture file's last write
     * (asserted by the Python harness) stays deterministic. */
    assert(card_shell_launch_surface("hide"));
    assert(card_shell_launch_surface("shade"));
    return 0;
}
''')
            binary = path / "route-test"
            subprocess.run(
                [os.environ.get("CC", "cc"), "-std=gnu11", "-Wall", "-Wextra", "-Werror",
                 "-I" + str(path), str(program), str(ROOT / "nix/card-shell/route.c"),
                 "-lm", "-o", str(binary)], check=True,
            )
            helper = path / "helper with spaces"
            helper.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$CARD_ROUTE_CAPTURE"\n')
            helper.chmod(0o700)
            capture = path / "capture"
            subprocess.run([str(binary), str(helper)], check=True,
                           env={**os.environ, "CARD_ROUTE_CAPTURE": str(capture)})
            deadline = time.monotonic() + 2
            while not capture.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual(capture.read_text().splitlines(), ["--surface", "shade"])


if __name__ == "__main__":
    unittest.main()
