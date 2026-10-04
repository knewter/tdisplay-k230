"""Execute patch-applied worker code with isolated callbacks; no hardware."""
import ctypes
import importlib.util
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('breadcrumb_fixture', ROOT / 'tests/test_mainline_uart_progress_breadcrumbs.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
AFTER = b'\nK230_UPP1 point=after-n1-write\n'
THIRD = b'\nK230_UPP1 point=third-post-sleep\n'
PREFIX = fixture.PREFIX.replace('#include <string.h>', '#include <string.h>\n#include <setjmp.h>')
PREFIX = PREFIX.replace('static int calls,sleeps', 'static jmp_buf unreturned; static int jump_at;\nstatic int calls,sleeps')
PREFIX = PREFIX.replace('records[8][256]', 'records[10][256]').replace('calls>=8', 'calls>=10').replace('calls<8', 'calls<10')
PREFIX = PREFIX.replace('!strncmp(s,"\\nK230_UPB1 point=first-post-sleep\\n",n)?2:3;',
    '!strncmp(s,"\\nK230_UPB1 point=first-post-sleep\\n",n)?2:\n'
    '           !strncmp(s,"\\nK230_UPP1 point=after-n1-write\\n",n)?4:\n'
    '           !strncmp(s,"\\nK230_UPP1 point=third-post-sleep\\n",n)?5:3;')
PREFIX = PREFIX.replace('calls++;\n return result', 'calls++;if(jump_at && calls==jump_at)longjmp(unreturned,1);\n return result')
SUFFIX = fixture.SUFFIX.replace('result=9999;', 'result=9999;jump_at=0;')
SUFFIX = SUFFIX.replace(' sbi_debug_console_available=true;', '''
#ifdef POST_SAMPLE_VARIANT
 k230_uart_progress_post_sample_enabled=false;
#endif
 sbi_debug_console_available=true;''')
SUFFIX = SUFFIX.replace('void execute(void) {', 'void execute(void) { if(setjmp(unreturned))return;')
SUFFIX += r'''
void post_flag(const char *s) {
#ifdef POST_SAMPLE_VARIANT
 k230_uart_progress_post_sample_setup((char *)s);
#else
 (void)s;
#endif
}
void parse_post(const char *s) {
#ifdef POST_SAMPLE_VARIANT
 const char *key=key_k230_uart_progress_post_sample_setup;size_t n=strlen(key);
 if(!strncmp(s,key,n))k230_uart_progress_post_sample_setup((char *)s+n);
#else
 (void)s;
#endif
}
void nonreturn(int n) { jump_at=n; }
'''


class PostSample(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        folder = Path(cls.temp.name)
        worker = folder / 'drivers/soc/canaan/k230-uart-progress.c'
        worker.parent.mkdir(parents=True)
        worker.write_bytes((ROOT / 'nix/patches/mainline/k230-uart-progress.c').read_bytes())
        def apply(name):
            subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(ROOT / 'nix/patches/mainline' / name)],
                           cwd=folder, check=True, capture_output=True)
        apply('k230-uart-progress-breadcrumbs.patch')
        cls.base = worker.read_text()
        apply('k230-uart-progress-post-sample.patch')
        cls.patched = worker.read_text()
        cls.libs = {}
        for name, source, config in [('base', cls.base, 1), ('new', cls.patched, 1), ('configoff', cls.patched, 0)]:
            code = re.sub(r'^#include[^\n]*\n', '', source, flags=re.M)
            c = folder / (name + '.c')
            c.write_text(PREFIX + code + SUFFIX)
            args = ['gcc', '-shared', '-fPIC', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                    '-DBREADCRUMB_VARIANT=1', f'-DCONFIG_RISCV_SBI={config}']
            if name != 'base': args.append('-DPOST_SAMPLE_VARIANT=1')
            subprocess.run(args + [str(c), '-o', str(folder / (name + '.so'))], check=True, capture_output=True)
            lib = ctypes.CDLL(str(folder / (name + '.so')))
            lib.record.restype = ctypes.c_char_p
            for method in ('base_flag', 'new_flag', 'post_flag', 'parse_post'):
                getattr(lib, method).argtypes = [ctypes.c_char_p]
            cls.libs[name] = lib

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def setUp(self):
        for lib in self.libs.values(): lib.reset()

    def enable(self, name='new', post=True):
        lib = self.libs[name]
        lib.base_flag(b'1'); lib.new_flag(b'1')
        if post: lib.post_flag(b'1')
        return lib

    def records(self, lib): return tuple(lib.record(i) for i in range(lib.count()))
    def events(self, lib): return tuple(lib.event_at(i) for i in range(lib.number_events()))

    def test_exact_bytes_order_and_ten_call_cap(self):
        lib = self.enable(); lib.execute()
        records = self.records(lib)
        self.assertEqual(lib.count(), 10)
        self.assertEqual(records[4:6], (AFTER, THIRD))
        self.assertEqual(records[:2], (fixture.ENTRY, fixture.WAKE))
        numeric = [r for r in records if r.startswith(b'\nK230_UP1 ')]
        self.assertEqual(len(numeric), 6)
        for i, record in enumerate(numeric): self.assertTrue(record.startswith(f'\nK230_UP1 n={i} '.encode()))
        self.assertEqual((lib.sleep_count(), lib.snapshot_count(), lib.health()), (6, 6, 0))

    def test_actual_callback_placement(self):
        lib = self.enable(); lib.execute(); events = self.events(lib)
        self.assertEqual(events[events.index(404)-2:events.index(404)+4], (302, 403, 404, 105, 203, 106))
        self.assertEqual(events[events.index(405)-3:events.index(405)+3], (105, 203, 106, 405, 303, 403))
        self.assertEqual(events.count(404), 1); self.assertEqual(events.count(405), 1)

    def test_absent_gate_preserves_actual_base_records_and_events(self):
        base = self.enable('base', post=False); base.execute()
        new = self.enable(post=False); new.execute()
        self.assertEqual(self.records(new), self.records(base))
        self.assertEqual(self.events(new), self.events(base))
        self.assertEqual(new.count(), 8)

    def test_new_gate_exact_only(self):
        for value in (None, b'', b'0', b'01', b'true', b'1 ', b'1='):
            with self.subTest(value=value):
                lib = self.libs['new']; lib.reset(); self.enable(post=False); lib.post_flag(value); lib.execute()
                self.assertEqual(lib.count(), 8); self.assertNotIn(AFTER, self.records(lib))

    def test_bare_unknown_tokens_do_not_enable(self):
        for value in (b'k230.uart_progress_post_sample', b'k230.uart_progress_post_sample_extra=1', b'k230.uart_progress_post_sample=0'):
            with self.subTest(value=value):
                lib = self.libs['new']; lib.reset(); self.enable(post=False); lib.parse_post(value); lib.execute()
                self.assertEqual(lib.count(), 8)

    def test_exact_setup_key_enables(self):
        lib = self.enable(post=False); lib.parse_post(b'k230.uart_progress_post_sample=1'); lib.execute()
        self.assertEqual(lib.count(), 10)

    def test_invalid_after_valid_clears_gate(self):
        lib = self.enable(); lib.post_flag(b'0'); lib.execute(); self.assertEqual(lib.count(), 8)

    def test_both_prior_gates_still_required(self):
        lib = self.enable(); lib.base_flag(b'0'); lib.execute(); self.assertEqual(lib.count(), 0)
        lib.reset(); self.enable(); lib.new_flag(b'0'); lib.execute()
        self.assertEqual(lib.count(), 6); self.assertNotIn(AFTER, self.records(lib)); self.assertNotIn(THIRD, self.records(lib))

    def test_extension_unavailable_starts_no_worker(self):
        lib = self.enable(); lib.available(0); lib.execute(); self.assertEqual((lib.count(), lib.start_count()), (0, 0))

    def test_configoff_isolated_helper_emits_no_fixed_points(self):
        lib = self.enable('configoff'); lib.execute()
        self.assertEqual(lib.count(), 6)
        self.assertNotIn(AFTER, self.records(lib)); self.assertNotIn(THIRD, self.records(lib))

    def test_full_partial_zero_error_are_never_retried(self):
        for returned in (9999, 1, 0, -5):
            with self.subTest(returned=returned):
                lib = self.libs['new']; lib.reset(); self.enable(); lib.returned(returned); lib.execute()
                self.assertEqual((lib.count(), lib.health()), (10, 0))
                self.assertEqual(self.records(lib)[4:6], (AFTER, THIRD))

    def test_second_numeric_nonreturn_model_reaches_no_followup(self):
        lib = self.enable(); lib.nonreturn(4); lib.execute()
        self.assertEqual(lib.count(), 4)
        self.assertTrue(self.records(lib)[-1].startswith(b'\nK230_UP1 n=1 '))
        self.assertNotIn(AFTER, self.records(lib)); self.assertNotIn(THIRD, self.records(lib))
        self.assertEqual((lib.sleep_count(), lib.snapshot_count()), (2, 2))

    def test_new_after_point_nonreturn_model_reaches_no_third_sleep(self):
        lib = self.enable(); lib.nonreturn(5); lib.execute()
        self.assertEqual(self.records(lib)[-1], AFTER)
        self.assertEqual((lib.count(), lib.sleep_count()), (5, 2))
        self.assertNotIn(THIRD, self.records(lib))

    def test_existing_stop_boundaries_are_preserved(self):
        for stop, calls, sleeps in ((1, 0, 0), (4, 3, 2), (5, 5, 2), (6, 5, 3), (7, 7, 3)):
            with self.subTest(stop=stop):
                lib = self.libs['new']; lib.reset(); self.enable(); lib.stop(stop); lib.execute()
                self.assertEqual((lib.count(), lib.sleep_count(), lib.health()), (calls, sleeps, 0))
                self.assertEqual(THIRD in self.records(lib), stop == 7)

    def test_literal_bounds_lifetimes_and_added_code_scope(self):
        self.assertLessEqual(len(AFTER)+1, 64); self.assertLessEqual(len(THIRD)+1, 64)
        patch = (ROOT/'nix/patches/mainline/k230-uart-progress-post-sample.patch').read_text()
        added = '\n'.join(line[1:] for line in patch.splitlines() if line.startswith('+') and not line.startswith('+++'))
        self.assertEqual(added.count('static const char'), 2)
        self.assertEqual(added.count('__aligned(64)'), 2)
        self.assertEqual(added.count('static_assert('), 2)
        for forbidden in ('__initdata', '__initconst', 'pr_info', 'printk', 'nbcon', 'readl', 'writel', 'snprintf', 'msleep', 'kthread_should_stop', 'set_cpus_allowed', 'sched_set'):
            self.assertNotIn(forbidden, added)
        self.assertEqual(self.patched.count('msleep(K230_UP_DELAY_MS)'), 1)
        self.assertEqual(self.patched.count('k230_uart_progress_snapshot(&s)'), 1)
        self.assertEqual(self.patched.count('kthread_should_stop()'), 2)


if __name__ == '__main__': unittest.main()
