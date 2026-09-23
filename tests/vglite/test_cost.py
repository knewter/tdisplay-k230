#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[2] / 'tools/vglite-cost.py'
spec = importlib.util.spec_from_file_location('cost', path)
cost = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cost)


def record(**updates):
    fields = dict(v='1', result='gpu', ok='1', ops='3', **{k: '0' for k in cost.METRICS})
    fields.update(snapshot_wall_ns='1000000', snapshot_cpu_ns='900000',
                  total_wall_ns='3000000', total_cpu_ns='1000000')
    fields.update(updates)
    return '00:01 [INFO] VG-Lite cost '+' '.join(k+'='+v for k, v in fields.items())


class Costs(unittest.TestCase):
    def test_aggregates_and_warmup(self):
        rows = cost.parse('\n'.join([record(total_wall_ns='90000000')]+[record()]*4))
        result = cost.summarize(rows, minimum=4, discard=1)
        self.assertEqual(result['costs']['total_wall_ms']['p95'], 3)
        self.assertEqual(result['phase_cpu_fraction']['snapshot'], .9)
        self.assertEqual(result['measured_frames'], 4)

    def test_rejects_failed_or_fabricated_clocks(self):
        for update in ({'ok':'0'}, {'result':'failed'}, {'v':'2'}, {'total_cpu_ns':'0'},
                       {'init_cpu_ns':'2000000'}, {'upload_wall_ns':'-1'},
                       {'total_wall_ns':'nan'}, {'total_cpu_ns':'1.2'}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                cost.parse(record(**update))

    def test_missing_duplicate_and_unknown_fields(self):
        for text in ('no profiler', record().replace(' ok=1',''), record()+' ok=1', record()+' extra=1'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                cost.parse(text)

    def test_rejects_short_or_mixed_run(self):
        with self.assertRaises(ValueError):
            cost.summarize(cost.parse(record()), minimum=2, discard=0)
        with self.assertRaises(ValueError):
            cost.summarize(cost.parse(record()+'\n'+record(result='pixman')), minimum=2, discard=0)


if __name__ == '__main__':
    unittest.main()
