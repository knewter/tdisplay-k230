import importlib.util,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('destination',Path(__file__).with_name('log-destination-analyze.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class JournalSamples(unittest.TestCase):
 def rows(self):return [{'t_ns':i*1_000_000_000,'cpu_ns':i*100_000_000,'cgroup_identity':[1,2]} for i in range(6)]
 def test_measured_window_excludes_boundary_samples_without_interpolation(self):
  v=m.cpu_window(self.rows(),500_000_000,4_500_000_000)
  self.assertEqual((v['sample_count'],v['elapsed_seconds'],v['cpu_seconds']),(4,3,.3));self.assertAlmostEqual(v['average_cores'],.1)
 def test_cgroup_replacement_is_rejected(self):
  r=self.rows();r[3]['cgroup_identity']=[1,3]
  with self.assertRaises(AssertionError):m.cpu_window(r,0,5_000_000_000)
 def test_counter_reset_is_rejected(self):
  r=self.rows();r[3]['cpu_ns']=1
  with self.assertRaises(AssertionError):m.cpu_window(r,0,5_000_000_000)
 def test_clock_reversal_is_rejected(self):
  r=self.rows();r[3]['t_ns']=1
  with self.assertRaises(AssertionError):m.cpu_window(r,0,5_000_000_000)
 def test_insufficient_inside_phase_samples_are_rejected(self):
  with self.assertRaises(AssertionError):m.cpu_window(self.rows(),500_000_000,2_500_000_000)
if __name__=='__main__':unittest.main()
