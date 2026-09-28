#!/usr/bin/env python3
"""Summarize a tools/measure-panel-refresh.sh capture.

Reads a transcript produced by running that script on the board (directly,
or captured over serial with tools/capture-boot.py --out, whose own status
lines and the script's `PANEL_REFRESH_RAW ...` informational lines are both
ignored -- only `PANEL_REFRESH v=1 event=...` lines are parsed) and prints
the vblank interval distribution, the VO IRQ rate, and the programmed mode's
computed refresh, so the three numbers in
docs/evidence/card-shell/frame-budget/analysis.md's decision table can be
read off one command instead of by hand.

  python3 tools/parse-panel-refresh.py --input docs/evidence/card-shell/frame-budget/idle-capture.txt
  cat capture.txt | python3 tools/parse-panel-refresh.py

Never opens a board or a device itself; this is a pure text parser.
"""
import argparse
import re
import sys
import unittest
from pathlib import Path

PREFIX = 'PANEL_REFRESH v=1 '
LINE_RE = re.compile(r'event=(\S+)')
KV_RE = re.compile(r'(\w+)=(\S+)')


class InvalidCapture(ValueError):
    pass


def parse_lines(text):
    """Yield (event, {key: value}) for every PANEL_REFRESH v=1 line.

    Tolerant of a capture-boot.py timestamp prefix ("[  12.345] ") before
    the marker, since the board's own output is not itself timestamped that
    way but a whole-transcript capture interleaves capture-boot's status
    lines which are. Anything that is not a `PANEL_REFRESH v=1` line
    (including `PANEL_REFRESH_RAW ...` informational text) is ignored, not
    an error -- this parser only reads what it explicitly understands.
    """
    for raw in text.splitlines():
        idx = raw.find(PREFIX)
        if idx < 0:
            continue
        rest = raw[idx + len(PREFIX):]
        m = LINE_RE.match(rest)
        if not m:
            continue
        event = m.group(1)
        fields = dict(KV_RE.findall(rest))
        yield event, fields


def percentile(sorted_values, p):
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(sorted_values) - 1)
    if lo == hi:
        return sorted_values[lo]
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (k - lo)


def distribution(values_ms):
    if not values_ms:
        return None
    ordered = sorted(values_ms)
    return {
        'count': len(ordered),
        'min_ms': round(ordered[0], 4),
        'p50_ms': round(percentile(ordered, 0.50), 4),
        'p90_ms': round(percentile(ordered, 0.90), 4),
        'p95_ms': round(percentile(ordered, 0.95), 4),
        'max_ms': round(ordered[-1], 4),
    }


def summarize(text):
    mode = None
    vblank_samples = []  # (seq, t_ms)
    vblank_errors = 0
    irq_before = None
    irq_after = None
    notes = []

    for event, fields in parse_lines(text):
        if event == 'mode' and 'vrefresh_computed_hz' in fields:
            mode = {
                'clock_khz': int(fields['clock_khz']),
                'htotal': int(fields['htotal']),
                'vtotal': int(fields['vtotal']),
                'vrefresh_reported_hz': int(fields.get('vrefresh_reported', 0)),
                'vrefresh_computed_hz': float(fields['vrefresh_computed_hz']),
            }
        elif event == 'vblank':
            try:
                seq = int(fields['seq'])
                t_ms = int(fields['sec']) * 1000.0 + int(fields['usec']) / 1000.0
            except (KeyError, ValueError) as exc:
                raise InvalidCapture(f'malformed vblank line: {fields}') from exc
            vblank_samples.append((seq, t_ms))
        elif event == 'vblank_error':
            vblank_errors += 1
        elif event == 'irq_sample':
            phase = fields.get('phase')
            try:
                count = int(fields['count'])
            except (KeyError, ValueError):
                continue
            if phase == 'before':
                irq_before = (count, fields.get('t_unix'))
            elif phase == 'after':
                irq_after = (count, fields.get('t_unix'), fields.get('window_seconds'))
        elif event == 'note':
            notes.append(fields.get('text', ''))

    vblank_samples.sort(key=lambda pair: pair[1])
    interval_ms = [b - a for (_, a), (_, b) in zip(vblank_samples, vblank_samples[1:])]
    seq_gaps = [bseq - aseq for (aseq, _), (bseq, _) in zip(vblank_samples, vblank_samples[1:])]

    irq_rate_hz = None
    irq_delta = None
    if irq_before and irq_after:
        before_count, _ = irq_before
        after_count, _, window = irq_after
        irq_delta = after_count - before_count
        try:
            window_f = float(window)
        except (TypeError, ValueError):
            window_f = None
        if window_f and window_f > 0 and irq_delta >= 0:
            irq_rate_hz = round(irq_delta / window_f, 4)

    return {
        'mode': mode,
        'vblank_interval': distribution(interval_ms),
        'vblank_sequence_gaps_nonunity': sum(1 for g in seq_gaps if g != 1),
        'vblank_sequence_samples': len(vblank_samples),
        'vblank_errors': vblank_errors,
        'irq_delta': irq_delta,
        'irq_window_rate_hz': irq_rate_hz,
        'notes': notes,
    }


def format_report(summary):
    lines = []
    mode = summary['mode']
    if mode:
        lines.append(f"programmed mode: clock={mode['clock_khz']}kHz "
                      f"htotal={mode['htotal']} vtotal={mode['vtotal']} "
                      f"vrefresh_reported={mode['vrefresh_reported_hz']}Hz "
                      f"vrefresh_computed={mode['vrefresh_computed_hz']:.4f}Hz")
    else:
        lines.append('programmed mode: <not captured>')

    dist = summary['vblank_interval']
    if dist:
        lines.append(f"vblank interval ({dist['count']} samples): "
                      f"min={dist['min_ms']}ms p50={dist['p50_ms']}ms "
                      f"p90={dist['p90_ms']}ms p95={dist['p95_ms']}ms max={dist['max_ms']}ms")
    else:
        lines.append(f"vblank interval: <no samples "
                      f"({summary['vblank_sequence_samples']} raw, "
                      f"{summary['vblank_errors']} errors)>")
    if summary['vblank_sequence_gaps_nonunity']:
        lines.append(f"  note: {summary['vblank_sequence_gaps_nonunity']} sample pair(s) had a "
                      "vblank sequence gap other than 1 (missed samples in this probe's own "
                      "loop, not necessarily on the hardware side)")

    if summary['irq_window_rate_hz'] is not None:
        lines.append(f"VO IRQ rate: {summary['irq_window_rate_hz']} Hz "
                      f"({summary['irq_delta']} events in the sampled window)")
    else:
        lines.append('VO IRQ rate: <not captured>')

    for note in summary['notes']:
        lines.append(f'note: {note}')
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--input', type=Path, default=None,
                         help='capture file; defaults to stdin')
    args = parser.parse_args(argv)
    text = args.input.read_text() if args.input else sys.stdin.read()
    summary = summarize(text)
    print(format_report(summary))
    return 0


class ParserTest(unittest.TestCase):
    def test_ignores_capture_boot_and_raw_lines(self):
        text = (
            "[   0.100] --- port opened ---\n"
            "PANEL_REFRESH_RAW modetest: id encoder status\n"
            "PANEL_REFRESH v=1 event=mode connector_id=1 name=568x1232 "
            "clock_khz=49500 hdisplay=568 htotal=748 vdisplay=1232 vtotal=1268 "
            "vrefresh_reported=52 vrefresh_computed_hz=52.1836\n"
        )
        summary = summarize(text)
        self.assertIsNotNone(summary['mode'])
        self.assertAlmostEqual(summary['mode']['vrefresh_computed_hz'], 52.1836)

    def test_vblank_interval_distribution_native_refresh(self):
        lines = ['PANEL_REFRESH v=1 event=header device=/dev/dri/card0 requested_count=5']
        # Four samples, uniform 19.163ms apart == the panel's advertised
        # ~52.19Hz period, sequence incrementing by 1 every time.
        base_sec, base_usec = 100, 0
        t = 0.0
        for seq in range(4):
            usec = base_usec + round(t * 1000) % 1_000_000
            sec = base_sec + int(t // 1000)
            lines.append(f'PANEL_REFRESH v=1 event=vblank seq={seq} sec={sec} usec={usec}')
            t += 19.163
        summary = summarize('\n'.join(lines))
        dist = summary['vblank_interval']
        self.assertEqual(dist['count'], 3)
        self.assertAlmostEqual(dist['p50_ms'], 19.163, places=2)
        self.assertEqual(summary['vblank_sequence_gaps_nonunity'], 0)

    def test_vblank_every_third_refresh_hypothesis_is_distinguishable(self):
        # If the structural-divisor hypothesis were true, the probe -- which
        # samples every single vblank via DRM_VBLANK_RELATIVE sequence=1 --
        # would show non-unity sequence gaps of 3 at a genuinely ~57ms
        # spacing, not a ~19ms spacing with an unrelated slow consumer.
        lines = []
        sec = 200
        for i, seq in enumerate([0, 3, 6, 9]):
            usec = (i * 57_490) % 1_000_000
            s = sec + (i * 57_490) // 1_000_000
            lines.append(f'PANEL_REFRESH v=1 event=vblank seq={seq} sec={s} usec={usec}')
        summary = summarize('\n'.join(lines))
        self.assertEqual(summary['vblank_sequence_gaps_nonunity'], 3)
        self.assertAlmostEqual(summary['vblank_interval']['p50_ms'], 57.49, places=1)

    def test_irq_rate_computed_from_before_after(self):
        text = (
            'PANEL_REFRESH v=1 event=irq_sample phase=before irq=39 count=1000 t_unix=1000\n'
            'PANEL_REFRESH v=1 event=irq_sample phase=after irq=39 count=1260 t_unix=1005 window_seconds=5\n'
        )
        summary = summarize(text)
        self.assertEqual(summary['irq_delta'], 260)
        self.assertAlmostEqual(summary['irq_window_rate_hz'], 52.0)

    def test_malformed_vblank_line_rejected(self):
        with self.assertRaises(InvalidCapture):
            summarize('PANEL_REFRESH v=1 event=vblank seq=1 sec=nope usec=0\n')

    def test_probe_unavailable_note_surfaced(self):
        text = 'PANEL_REFRESH v=1 event=note text=probe-unavailable path=/tmp/panel-refresh-probe\n'
        summary = summarize(text)
        self.assertIn('probe-unavailable', summary['notes'])

    def test_format_report_smoke(self):
        text = (
            'PANEL_REFRESH v=1 event=mode connector_id=1 name=x clock_khz=49500 '
            'hdisplay=568 htotal=748 vdisplay=1232 vtotal=1268 vrefresh_reported=52 '
            'vrefresh_computed_hz=52.1836\n'
            'PANEL_REFRESH v=1 event=irq_sample phase=before irq=39 count=0 t_unix=0\n'
            'PANEL_REFRESH v=1 event=irq_sample phase=after irq=39 count=100 t_unix=2 '
            'window_seconds=2\n'
        )
        report = format_report(summarize(text))
        self.assertIn('vrefresh_computed=52.1836Hz', report)
        self.assertIn('VO IRQ rate: 50.0 Hz', report)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--selftest':
        sys.exit(unittest.main(argv=[sys.argv[0]] + sys.argv[2:]))
    sys.exit(main())
