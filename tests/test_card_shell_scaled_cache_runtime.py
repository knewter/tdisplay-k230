"""Run actual cross-built Sway with cache off/on at the same RGB565 format."""
from card_shell_test_support import ROOT, binaries
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest


class ScaledCacheRuntime(unittest.TestCase):
    def test_actual_compositor_rgb565_off_and_on(self):
        sway, client = binaries()
        with tempfile.TemporaryDirectory(prefix='card-scaled-runtime-') as tmp:
            for enabled in (False, True):
                out = Path(tmp) / ('on' if enabled else 'off')
                out.mkdir()
                cmd = [sys.executable, str(ROOT / 'tests/card_shell_runtime.py'), '--sway', sway,
                       '--client', client, '--output', str(out), '--rgb565']
                if enabled:
                    cmd.append('--scaled-cache')
                subprocess.run(cmd, cwd=ROOT, check=True)
                result = json.loads((out / 'result.json').read_text())
                assert 'clean-compositor-teardown' in result['passed']


if __name__ == '__main__':
    unittest.main()
