import importlib.util
from pathlib import Path
import unittest

s=importlib.util.spec_from_file_location('profile_analyze',Path(__file__).with_name('render-profile-analyze.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

class WaitPartition(unittest.TestCase):
    def test_runnable_and_sleep_wakeup_are_disjoint(self):
        rows=[{'start_ns':2,'end_ns':5,'state':'R','wakeup_ns':None},
              {'start_ns':6,'end_ns':12,'state':'S','wakeup_ns':10}]
        self.assertEqual(m.off_cpu((0,15),rows),{'runnable_ns':5,'blocked_ns':4,'unknown_ns':0})

    def test_clips_both_edges_of_a_render_window(self):
        rows=[{'start_ns':2,'end_ns':8,'state':'S','wakeup_ns':6},
              {'start_ns':10,'end_ns':20,'state':'R+','wakeup_ns':None}]
        self.assertEqual(m.off_cpu((4,14),rows),{'runnable_ns':6,'blocked_ns':2,'unknown_ns':0})

    def test_missing_wakeup_remains_unknown(self):
        rows=[{'start_ns':2,'end_ns':9,'state':'D','wakeup_ns':None}]
        self.assertEqual(m.off_cpu((0,10),rows),{'runnable_ns':0,'blocked_ns':0,'unknown_ns':7})

    def test_overlapping_or_impossible_waits_are_rejected(self):
        with self.assertRaises(AssertionError):m.off_cpu((0,10),[{'start_ns':1,'end_ns':9,'state':'S','wakeup_ns':20}])
        with self.assertRaises(AssertionError):m.off_cpu((0,10),[{'start_ns':0,'end_ns':10,'state':'R','wakeup_ns':None}]*2)
        with self.assertRaises(AssertionError):m.off_cpu((0,100),[
            {'start_ns':2,'end_ns':5,'state':'R','wakeup_ns':None},
            {'start_ns':4,'end_ns':7,'state':'R','wakeup_ns':None}])

if __name__=='__main__':unittest.main()
