"""Host proof of the dark-panel touch wake gate's swallow rules."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WakeGate(unittest.TestCase):
    def test_gate(self):
        with tempfile.TemporaryDirectory(prefix="card-wake-gate-") as tmp:
            exe = Path(tmp) / "gate"
            subprocess.run([os.environ.get("CC", "cc"), "-std=c11", "-Wall", "-Wextra", "-Werror",
                            "-I" + str(ROOT / "nix/card-shell"),
                            str(ROOT / "tests/card_wake_gate.c"), "-o", str(exe)], check=True)
            subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    unittest.main()
