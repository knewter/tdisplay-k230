#!/usr/bin/env python3
"""Regression proof for the reported "black / glitching" card overview.

Root cause (see openspec/changes/fix-overview-home-bleed-through/design.md
and the `home_layer_sync` comment in nix/card-shell/adapter.c): the Home
screen's always-mapped `Layer::Bottom` surface sat directly beneath the
overview's own deliberately-transparent canvas with nothing hiding it while
the overview was active, so Home's grid/dock painted through the deck and
over "Swipe up for apps" -- and because the touch-first two-axis entry
gesture (`cs_begin_entry`) flips `shell.active` at first touch-down, this
bled through for the whole animated entry gesture too, not only the
already-settled overview a native capture showed.

This test maps a native Layer::Bottom fixture (`card_shell_home_layer.c`)
filled with a colour no other surface in this suite uses, then runs the
exact same real cross-built Sway/two-axis touch sequence
`test_card_shell_two_axis_runtime.py` proves (entry, drag, bend, quick
switch, close, settle) through `tests/card_shell_runtime.py`, which sweeps
every frame that sequence captures for the fixture's colour and asserts the
compositor's own `debug-scene` `home_enabled` flag tracks the overview
correctly in both directions -- hidden throughout the gesture and the
settled overview, restored once a card is focused again, and genuinely
visible once every card closes (so the fix cannot pass by simply disabling
Home forever).

Headless-QEMU-injected-input evidence only; no physical touch or panel
proof.
"""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from card_shell_test_support import ROOT, binaries

PROTOCOL = Path('/nix/store/r2zcb3d3dgmz09qjaqsy945inal2h41r-source/protocol/wlr-layer-shell-unstable-v1.xml')


class HomeBleedRuntime(unittest.TestCase):
    def test_home_layer_hidden_through_entry_and_restored_when_idle(self):
        sway, client = binaries()
        with tempfile.TemporaryDirectory(prefix="card-home-bleed-") as directory:
            fixture = Path(directory) / "fixture"
            fixture.mkdir()
            header = fixture / "wlr-layer-shell-unstable-v1-client-protocol.h"
            source = fixture / "protocol.c"
            subprocess.run(["wayland-scanner", "client-header", str(PROTOCOL), str(header)], check=True)
            subprocess.run(["wayland-scanner", "private-code", str(PROTOCOL), str(source)], check=True)
            xdg = "/usr/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml"
            xdg_source = fixture / "xdg-protocol.c"
            subprocess.run(["wayland-scanner", "private-code", xdg, str(xdg_source)], check=True)
            flags = subprocess.check_output(["pkg-config", "--cflags", "--libs", "wayland-client"],
                                            text=True).split()
            home_layer_client = fixture / "home-layer"
            subprocess.run(["cc", "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-I" + str(fixture),
                            str(ROOT / "tests/card_shell_home_layer.c"), str(source), str(xdg_source),
                            *flags, "-o", str(home_layer_client)], check=True)
            output = Path(directory) / "evidence"
            subprocess.run([
                sys.executable, str(ROOT / "tests/card_shell_runtime.py"),
                "--sway", sway, "--client", client, "--output", str(output),
                "--native-touch", "--touch-first", "--two-axis",
                "--home-layer-client", str(home_layer_client),
            ], cwd=ROOT, check=True)
            log = (output / "sway.log").read_text()
            self.assertIn("K230_CARD_SHELL mirror id=", log)
            self.assertIn("K230_CARD_SHELL restored focus=", log)
            self.assertIn("home mapped", (output / "home-layer.log").read_text())
            self.assertTrue((output / "two-axis-home-idle.png").exists())


if __name__ == "__main__":
    unittest.main()
