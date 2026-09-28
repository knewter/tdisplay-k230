"""Run the real cross-built compositor and confirm the live-mirror filter
mode actually toggles both ways during one session: nearest while a card is
in motion (drag/entry/expand/close), bilinear once settled. Guards against
the conditional in sync_node silently never taking one branch (e.g. because
scene_in_motion() was always true or always false for this workload)."""
from card_shell_test_support import ROOT, binaries
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


class MotionFilterRuntime(unittest.TestCase):
    def test_nearest_and_bilinear_both_occur(self):
        sway, client = binaries()
        with tempfile.TemporaryDirectory(prefix='card-motion-filter-') as tmp:
            out = Path(tmp)
            subprocess.run([sys.executable, str(ROOT / 'tests/card_shell_runtime.py'),
                             '--native-touch', '--benchmark', '--delayed-touch',
                             '--sway', sway, '--client', client, '--output', str(out)],
                            cwd=ROOT, check=True)
            log = (out / 'sway.log').read_text()
            rows = re.findall(
                r'K230_CARD_SHELL filter-mode nearest=(\d+) bilinear=(\d+)', log)
            self.assertTrue(rows, 'no filter-mode telemetry rows found in sway.log')
            nearest, bilinear = (int(x) for x in rows[-1])
            self.assertGreater(nearest, 0,
                'sync_node never chose the nearest filter -- scene_in_motion() '
                'was never true during this drag/entry/expand session')
            self.assertGreater(bilinear, 0,
                'sync_node never chose the bilinear filter -- a settled card '
                'is not restored to full quality')


if __name__ == '__main__':
    unittest.main()
