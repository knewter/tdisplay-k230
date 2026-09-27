import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
import runtime_trace as trace
spec = importlib.util.spec_from_file_location('trace_export', TOOLS / 'runtime-trace-export.py')
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)
ID = '1' * 32


def event(kind, start, data=None, span=0, parent=0, end=None, tid=10):
    return dict(kind=kind, start_us=start, end_us=start if end is None else end,
                cpu_us=0, tid=tid, span_id=span, parent_span_id=parent, data=data or [0]*6)


def report(events, pid=10):
    return dict(schema=1, clock='CLOCK_MONOTONIC', trace_id=ID, pid=pid,
                capacity=65536, deadline_us=100000, finished_us=100000,
                dropped=0, events=events)


class RecorderTests(unittest.TestCase):
    def test_remote_nesting_and_exception_restore(self):
        recorder = trace.Recorder(ID, 10)
        with patch.object(trace, '_recorder', recorder):
            with trace.remote_parent(dict(trace_id=ID, parent_span_id='0000000000000123')):
                with trace.span('helper_request'):
                    with self.assertRaises(RuntimeError):
                        with trace.span('theme_catalog_handle'):
                            raise RuntimeError('private text never recorded')
            with trace.span('theme_catalog_handle'):
                pass
        child, outer, unrelated = recorder.events
        self.assertEqual(child['parent_span_id'], outer['span_id'])
        self.assertEqual(outer['parent_span_id'], 0x123)
        self.assertEqual(unrelated['parent_span_id'], 0)
        self.assertNotIn('private', json.dumps(recorder.finish()))

    def test_context_mismatch_and_invalid_are_ignored(self):
        for context in [None, 7, {}, {'trace_id': '2'*32, 'parent_span_id': '1'*16},
                        {'trace_id': ID, 'parent_span_id': 'secret'}]:
            recorder = trace.Recorder(ID, 10)
            with patch.object(trace, '_recorder', recorder), trace.remote_parent(context):
                with trace.span('helper_request'):
                    pass
            self.assertEqual(recorder.events[0]['parent_span_id'], 0)

    def test_bound_stop_and_disabled_fast_path(self):
        recorder = trace.Recorder(ID, 10, capacity=2)
        with patch.object(trace, '_recorder', recorder):
            for _ in range(5):
                with trace.span('helper_request'):
                    pass
            result = recorder.finish()
            with trace.span('helper_request'):
                pass
        self.assertEqual(len(result['events']), 2)
        self.assertEqual(result['dropped'], 3)
        self.assertEqual(recorder.events, [])
        with patch.object(trace, '_recorder', None), patch.object(trace, 'now_us', side_effect=AssertionError):
            with trace.span('helper_request'):
                pass

    def test_recording_file_is_exclusive_private_and_flushes_after_window(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'trace.json'
            with patch.object(trace, '_recorder', None), patch.dict(trace.os.environ, {
                    'K230_TRACE_PATH': str(path), 'K230_TRACE_ID': ID, 'K230_TRACE_SECONDS': '10'}):
                trace.init()
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                with trace.span('helper_request'):
                    pass
                self.assertEqual(path.read_bytes(), b'')
                trace._recorder.deadline = 0
                trace.finish_if_due()
                self.assertEqual(len(json.loads(path.read_text())['events']), 1)
            with patch.object(trace, '_recorder', None), patch.dict(trace.os.environ, {
                    'K230_TRACE_PATH': str(path), 'K230_TRACE_ID': ID}):
                with self.assertRaises(FileExistsError):
                    trace.init()


class ExportTests(unittest.TestCase):
    def test_nested_spans_and_cross_process_flow(self):
        parent = event('theme_helper_rpc', 10, span=1, end=90)
        child = event('helper_request', 20, span=2, parent=1, end=80, tid=20)
        timeline, summary = exporter.export([report([parent]), report([child], pid=20)])
        self.assertEqual([e['ph'] for e in timeline['traceEvents']].count('X'), 2)
        self.assertEqual([e['ph'] for e in timeline['traceEvents']].count('s'), 1)
        self.assertFalse(any('missing parents' in w for w in summary['warnings']))

    def test_idle_gap_excluded_and_presentation_clock_checked(self):
        events = []
        for frame, start, active in [(1, 100, 0), (2, 50000, 1), (3, 60000, 1)]:
            events += [event('draw_begin', start, [frame, 0, 568, 1232, 0, active]),
                       event('commit', start+5, [frame, 0, 0, 0, 0, 0]),
                       event('presented', start+200, [frame, (start+100)*1000, 16666667, frame, 3, 1])]
        _, summary = exporter.export([report(events)])
        self.assertEqual(summary['active_gap_count'], 1)
        self.assertEqual(summary['active_gap_us']['p99'], 10000)
        events[-1]['data'][-1] = 0
        _, summary = exporter.export([report(events)])
        self.assertTrue(any('unsupported presentation clock' in w for w in summary['warnings']))

    def test_malformed_clock_identity_and_unreviewed_names_rejected(self):
        for field, value in [('clock','CLOCK_REALTIME'), ('trace_id','invalid'), ('pid',True)]:
            broken = report([]); broken[field] = value
            with self.assertRaises(ValueError):
                exporter.export([broken])
        with self.assertRaises(ValueError):
            exporter.export([report([event('secret path',1)])])
        with self.assertRaises(ValueError):
            exporter.export([report([]), report([])])
        other = report([], 20); other['trace_id'] = '2'*32
        with self.assertRaises(ValueError):
            exporter.export([report([]), other])

    def test_loss_missing_feedback_and_partial_parent_are_explicit(self):
        recording = report([event('helper_request',1,span=2,parent=1,end=10),
                            event('commit',11,[1,0,0,0,0,0])])
        recording['dropped'] = 5
        _, summary = exporter.export([recording])
        self.assertFalse(summary['recording_intact'])
        self.assertTrue(any('dropped 5' in w for w in summary['warnings']))
        self.assertTrue(any('missing parents' in w for w in summary['warnings']))
        self.assertTrue(any('lack presentation' in w for w in summary['warnings']))


if __name__ == '__main__':
    unittest.main()
