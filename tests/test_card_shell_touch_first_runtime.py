#!/usr/bin/env python3
"""Headless QEMU proof of the opt-in live-deck drawer route."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from card_shell_test_support import ROOT, binaries

PROTOCOL = Path('/nix/store/r2zcb3d3dgmz09qjaqsy945inal2h41r-source/protocol/wlr-layer-shell-unstable-v1.xml')


class TouchFirstRuntime(unittest.TestCase):
    def test_deck_to_drawer_without_tearing_down_live_cards(self):
        sway, client = binaries()
        with tempfile.TemporaryDirectory(prefix="card-touch-first-") as directory:
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
            layer_client = fixture / "drawer-layer"
            subprocess.run(["cc", "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-I" + str(fixture),
                            str(ROOT / "tests/card_shell_drawer_layer.c"), str(source), str(xdg_source),
                            *flags, "-o", str(layer_client)], check=True)
            evidence = Path(directory) / "evidence"
            subprocess.run(
                [sys.executable, str(ROOT / "tests/card_shell_runtime.py"),
                 "--sway", sway, "--client", client, "--output", str(evidence),
                 "--touch-first", "--drawer-layer-client", str(layer_client)], cwd=ROOT, check=True,
            )
            log = (evidence / "sway.log").read_text()
            self.assertIn("K230_CARD_SHELL mirror id=", log)
            self.assertIn("K230_CARD_SHELL restored focus=", log)
            self.assertTrue((evidence / "with-drawer.png").exists())
            reveal = Path(directory) / "reveal"
            subprocess.run(
                [sys.executable, str(ROOT / "tests/card_shell_runtime.py"),
                 "--sway", sway, "--client", client, "--output", str(reveal),
                 "--touch-first", "--reveal-stream", "--drawer-layer-client", str(layer_client)],
                cwd=ROOT, check=True,
            )
            self.assertTrue((reveal / "reveal-layer.png").exists())


if __name__ == "__main__":
    unittest.main()
