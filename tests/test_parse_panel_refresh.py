#!/usr/bin/env python3
"""Host fixture test for tools/parse-panel-refresh.py against a realistic,
full transcript shape: a tools/capture-boot.py-style capture interleaving
its own bracketed status lines, tools/measure-panel-refresh.sh's
PANEL_REFRESH_RAW informational text, and the PANEL_REFRESH v=1 lines the
parser actually reads. No board access -- this exercises only the parser.

See tools/parse-panel-refresh.py's own embedded ParserTest for the
finer-grained unit tests (percentile math, malformed-line rejection, the
vblank-every-3rd-refresh discrimination case); this file checks the whole
pipeline end to end the way the coordinator will actually run it.
"""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P = load('parse_panel_refresh', 'parse-panel-refresh.py')

# A realistic capture: capture-boot.py's own status lines (bracketed,
# timestamped), the script's modetest cross-check (RAW, never parsed), the
# VO IRQ before/after pair, four vblank samples at the panel's real
# 52.1836Hz period with one dropped frame, and the probe's mode summary.
CAPTURE = """\
[   0.102] --- port opened ---
[   0.402] --- settle window clean, nothing discarded ---
[   0.900] --- sending: sh /tmp/measure-panel-refresh.sh ---

== modetest -c (informational only; not machine-parsed) ==
PANEL_REFRESH_RAW modetest: id	encoder	status		name		size (mm)	modes	encoders
PANEL_REFRESH_RAW modetest: 31	30	connected	DSI-1        	44x95		1	30

== VO vblank IRQ rate ==
PANEL_REFRESH v=1 event=irq_sample phase=before irq=39 count=884213 t_unix=1790600000
PANEL_REFRESH v=1 event=irq_sample phase=after irq=39 count=884474 t_unix=1790600005 window_seconds=5

== vblank samples (tools/panel-refresh-probe) ==
PANEL_REFRESH v=1 event=header device=/dev/dri/card0 requested_count=4
PANEL_REFRESH v=1 event=mode connector_id=31 name=568x1232 clock_khz=49500 hdisplay=568 htotal=748 vdisplay=1232 vtotal=1268 vrefresh_reported=52 vrefresh_computed_hz=52.1836
PANEL_REFRESH v=1 event=vblank seq=1001 sec=1790600 usec=100000
PANEL_REFRESH v=1 event=vblank seq=1002 sec=1790600 usec=119163
PANEL_REFRESH v=1 event=vblank seq=1004 sec=1790600 usec=157484
PANEL_REFRESH v=1 event=vblank seq=1005 sec=1790600 usec=176647

== DRM debugfs (best-effort; canaan-drm has none of its own) ==
PANEL_REFRESH v=1 event=note text=debugfs-dri-not-mounted

PANEL_REFRESH v=1 event=probe_end
"""


class PanelRefreshParserTest(unittest.TestCase):
    def test_full_capture_end_to_end(self):
        summary = P.summarize(CAPTURE)

        self.assertEqual(summary['mode']['clock_khz'], 49500)
        self.assertEqual(summary['mode']['vtotal'], 1268)
        self.assertAlmostEqual(summary['mode']['vrefresh_computed_hz'], 52.1836)

        # 4 samples -> 3 intervals: 19.163ms, 38.321ms (one dropped vblank,
        # sequence gap 2), 19.163ms.
        dist = summary['vblank_interval']
        self.assertEqual(dist['count'], 3)
        self.assertAlmostEqual(dist['min_ms'], 19.163, places=2)
        self.assertAlmostEqual(dist['max_ms'], 38.321, places=2)
        self.assertEqual(summary['vblank_sequence_gaps_nonunity'], 1)

        self.assertEqual(summary['irq_delta'], 261)
        self.assertAlmostEqual(summary['irq_window_rate_hz'], 52.2, places=1)

        self.assertIn('debugfs-dri-not-mounted', summary['notes'])

    def test_report_is_readable(self):
        report = P.format_report(P.summarize(CAPTURE))
        self.assertIn('vrefresh_computed=52.1836Hz', report)
        self.assertIn('vblank interval (3 samples)', report)
        self.assertIn('VO IRQ rate:', report)

    def test_cli_reads_from_file(self):
        import subprocess
        import tempfile
        with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as handle:
            handle.write(CAPTURE)
            path = handle.name
        try:
            result = subprocess.run(
                ['python3', str(ROOT / 'tools/parse-panel-refresh.py'), '--input', path],
                capture_output=True, text=True, check=True)
        finally:
            Path(path).unlink()
        self.assertIn('vrefresh_computed=52.1836Hz', result.stdout)


if __name__ == '__main__':
    unittest.main()
