"""Host fixtures for the bounded cgroup-only theme background sampler."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from theme_background_metrics import measure, snapshot  # noqa: E402


class MetricsFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.groups = self.root / "system.slice"
        self.proc = self.root / "proc"
        for unit, pid, cpu, memory, rss in (("shell.service", 11, 100, 1000, 2),
                                             ("shell-ui.service", 12, 200, 2000, 3)):
            group = self.groups / unit
            group.mkdir(parents=True)
            (group / "cpu.stat").write_text(f"usage_usec {cpu}\nuser_usec 0\n")
            (group / "memory.current").write_text(f"{memory}\n")
            (group / "cgroup.procs").write_text(f"{pid}\n")
            directory = self.proc / str(pid)
            directory.mkdir(parents=True)
            (directory / "status").write_text(f"Name:\ttest\nVmRSS:\t{rss} kB\n")

    def test_combines_shell_and_decoder_cgroups_with_sampled_peaks(self):
        tick = [0.0]

        def sleep(seconds):
            tick[0] += seconds
            for unit, increment in (("shell.service", 100_000),
                                    ("shell-ui.service", 200_000)):
                group = self.groups / unit
                before = int((group / "cpu.stat").read_text().split()[1])
                (group / "cpu.stat").write_text(f"usage_usec {before + increment}\n")
            (self.groups / "shell-ui.service" / "memory.current").write_text("4000\n")
            (self.proc / "12" / "status").write_text("Name:\tdecoder\nVmRSS:\t5 kB\n")

        result = measure(2.0, 0.5, cgroup_root=self.groups, proc_root=self.proc,
                         clock=lambda: tick[0], sleep=sleep)
        self.assertEqual(result["sample_count"], 5)
        self.assertEqual(result["cpu_usage_usec"], 1_200_000)
        self.assertEqual(result["mean_cpu_cores"], 0.6)
        self.assertEqual(result["process_rss_peak_bytes"], 7 * 1024)
        self.assertEqual(result["cgroup_memory_peak_bytes"], 5000)
        self.assertTrue(result["rss_complete"])

    def test_missing_or_unbounded_process_state_is_not_a_pass(self):
        (self.proc / "12" / "status").unlink()
        self.assertFalse(snapshot(self.groups, self.proc)["rss_complete"])
        (self.groups / "shell-ui.service" / "cgroup.procs").write_text("1\n" * 500)
        with self.assertRaisesRegex(ValueError, "process count"):
            snapshot(self.groups, self.proc)
        with self.assertRaisesRegex(ValueError, "bound"):
            measure(61, cgroup_root=self.groups, proc_root=self.proc)

    def test_one_unit_counter_reset_cannot_hide_behind_other_unit_growth(self):
        tick = [0.0]

        def sleep(seconds):
            tick[0] += seconds
            (self.groups / "shell.service" / "cpu.stat").write_text("usage_usec 900000\n")
            (self.groups / "shell-ui.service" / "cpu.stat").write_text("usage_usec 0\n")

        with self.assertRaisesRegex(ValueError, "shell-ui.service CPU counter regressed"):
            measure(2.0, 0.5, cgroup_root=self.groups, proc_root=self.proc,
                    clock=lambda: tick[0], sleep=sleep)

    def test_recreated_unit_cgroup_is_rejected_even_if_cpu_counter_grows(self):
        tick = [0.0]
        changed = [False]

        def sleep(seconds):
            tick[0] += seconds
            if changed[0]:
                return
            changed[0] = True
            old = self.groups / "shell-ui.service"
            old.rename(self.groups / "old-shell-ui.service")
            old.mkdir()
            (old / "cpu.stat").write_text("usage_usec 300\n")
            (old / "memory.current").write_text("2000\n")
            (old / "cgroup.procs").write_text("12\n")

        with self.assertRaisesRegex(ValueError, "shell-ui.service cgroup was recreated"):
            measure(2.0, 0.5, cgroup_root=self.groups, proc_root=self.proc,
                    clock=lambda: tick[0], sleep=sleep)


if __name__ == "__main__":
    unittest.main()
