#!/usr/bin/env python3
"""Real cross-built Sway scene proof under QEMU; no physical-touch claim."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from card_shell_test_support import ROOT, binaries


class TwoAxisRuntime(unittest.TestCase):
    def test_same_contact_scene_and_quick_switch(self):
        sway, client = binaries()
        with tempfile.TemporaryDirectory(prefix="card-two-axis-") as directory:
            output = Path(directory) / "evidence"
            subprocess.run([
                sys.executable, str(ROOT / "tests/card_shell_runtime.py"),
                "--sway", sway, "--client", client, "--output", str(output),
                "--native-touch", "--touch-first", "--two-axis",
            ], cwd=ROOT, check=True)
            log = (output / "sway.log").read_text()
            self.assertIn("K230_CARD_SHELL mirror id=", log)
            self.assertIn("K230_CARD_SHELL restored focus=", log)
            self.assertTrue((output / "two-axis-held.png").exists())
            self.assertTrue((output / "two-axis-quick-paused.png").exists())
            self.assertTrue((output / "two-axis-quick-releasing.png").exists())
            self.assertTrue((output / "two-axis-private-neighbor.png").exists())


if __name__ == "__main__":
    unittest.main()
