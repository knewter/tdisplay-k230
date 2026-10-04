"""Execute actual patched reporter code with isolated native callbacks; no board."""
import ctypes
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'nix/patches/mainline/k230-uart-progress.c'
PATCH = ROOT / 'nix/patches/mainline/k230-uart-progress-breadcrumbs.patch'
ENTRY = b'\nK230_UPB1 point=worker-entry\n'
WAKE = b'\nK230_UPB1 point=first-post-sleep\n'

PREFIX = r'''
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32;
typedef uint64_t u64;
#define __init
#define __aligned(n) __attribute__((aligned(n)))
#define __setup(k,f) static const char *key_##f __attribute__((unused)) = k
#define late_initcall(f)
#define IS_ENABLED(x) (x)
#define static_assert(x) _Static_assert(x, #x)
static bool sbi_debug_console_available;
struct task_struct { int unused; }; static struct task_struct task;
static int calls,sleeps,starts,checks,stop_at,result,bad,snapshots,event_count;
static int events[64]; static char records[8][256];
static void event(int x) { if(event_count>=64)bad++; else events[event_count++]=x; }
static int kthread_should_stop(void) { checks++;event(100+checks);return stop_at && checks>=stop_at; }
static void msleep(unsigned int n) { if(n!=5000)bad++;sleeps++;event(200+sleeps); }
static u64 ktime_get_ns(void) { return (u64)sleeps*5000000000ULL; }
static u64 get_jiffies_64(void) { return (u64)sleeps*1250; }
struct k230_uart_progress_snapshot {
 u32 state,irq,irq_count,rx,tx,frame,parity,overrun,buf_overrun,ier,read_mask,ignore_mask,uartclk;
};
#define K230_UP_OK 0
#define K230_UP_CHANGED 5
static void k230_uart_progress_snapshot(struct k230_uart_progress_snapshot *s) {
 snapshots++;event(300+snapshots);*s=(struct k230_uart_progress_snapshot){0,17,170,1,2,3,4,5,6,5,7,8,50000000}; }
static unsigned int k230_uart_progress_timer_irq(void) { return 5; }
static unsigned int kstat_irqs_usr(unsigned int irq) { return irq*10; }
static int sbi_debug_console_write(const char *s,unsigned int n) {
 int point=!strncmp(s,"\nK230_UPB1 point=worker-entry\n",n)?1:
           !strncmp(s,"\nK230_UPB1 point=first-post-sleep\n",n)?2:3;
 if(!n || n>=256 || calls>=8 || (uintptr_t)s%(point==3?256:64) || (point!=3 && n>64))bad++;
 event(400+point);if(calls<8){memcpy(records[calls],s,n);records[calls][n]=0;}calls++;
 return result==9999?(int)n:result;
}
static struct task_struct *kthread_run(int (*f)(void *),void *arg,const char *name) {
 (void)f;(void)arg;if(strcmp(name,"k230-uart-progress"))bad++;starts++;return &task; }
#define IS_ERR(x) ((void)(x),false)
#define PTR_ERR(x) ((void)(x),0)
'''
SUFFIX = r'''
void reset(void) {
 calls=sleeps=starts=checks=stop_at=bad=snapshots=event_count=0;result=9999;
 memset(records,0,sizeof records);memset(events,0,sizeof events);
 sbi_debug_console_available=true;k230_uart_progress_enabled=false;
#ifdef BREADCRUMB_VARIANT
 k230_uart_progress_breadcrumbs_enabled=false;
#endif
}
void base_flag(const char *s) { k230_uart_progress_setup((char *)s); }
void new_flag(const char *s) {
#ifdef BREADCRUMB_VARIANT
 k230_uart_progress_breadcrumbs_setup((char *)s);
#else
 (void)s;
#endif
}
void parse_new(const char *s) {
#ifdef BREADCRUMB_VARIANT
 const char *key=key_k230_uart_progress_breadcrumbs_setup;size_t n=strlen(key);
 if(!strncmp(s,key,n))k230_uart_progress_breadcrumbs_setup((char *)s+n);
#else
 (void)s;
#endif
}
void available(int x) { sbi_debug_console_available=x; }
void stop(int x) { stop_at=x; }
void returned(int x) { result=x; }
void execute(void) { (void)k230_uart_progress_init();if(starts)(void)k230_uart_progress_worker(NULL); }
int count(void) { return calls; }
int sleep_count(void) { return sleeps; }
int snapshot_count(void) { return snapshots; }
int start_count(void) { return starts; }
int health(void) { return bad; }
const char *record(int i) { return records[i]; }
int event_at(int i) { return events[i]; }
int number_events(void) { return event_count; }
'''


class Breadcrumbs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        folder = Path(cls.temp.name)
        worker = folder / 'drivers/soc/canaan/k230-uart-progress.c'
        worker.parent.mkdir(parents=True)
        worker.write_bytes(BASE.read_bytes())
        subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(PATCH)],
                       cwd=folder, check=True, capture_output=True)
        cls.patched = worker.read_text()
        cls.libraries = {}
        for name,source,config in [('original', BASE.read_text(), 1),
                                  ('enabled', cls.patched, 1), ('configoff', cls.patched, 0)]:
            code = re.sub(r'^#include[^\n]*\n', '', source, flags=re.M)
            c = folder / (name + '.c')
            c.write_text(PREFIX + code + SUFFIX)
            args = ['gcc', '-shared', '-fPIC', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                    f'-DCONFIG_RISCV_SBI={config}']
            if name != 'original': args.append('-DBREADCRUMB_VARIANT=1')
            subprocess.run(args + [str(c), '-o', str(folder / (name + '.so'))],
                           check=True, capture_output=True)
            lib = ctypes.CDLL(str(folder / (name + '.so')))
            lib.record.restype = ctypes.c_char_p
            for method in ('base_flag','new_flag','parse_new'):
                getattr(lib,method).argtypes = [ctypes.c_char_p]
            cls.libraries[name] = lib

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def setUp(self):
        for lib in self.libraries.values(): lib.reset()
        self.lib = self.libraries['enabled']

    def enable(self, lib=None):
        lib = lib or self.lib
        lib.base_flag(b'1'); lib.new_flag(b'1')

    def records(self, lib=None):
        lib = lib or self.lib
        return [lib.record(i) for i in range(lib.count())]

    def test_exact_marker_bytes_placement_and_eight_attempt_cap(self):
        self.enable(); self.lib.execute()
        self.assertEqual(self.lib.count(), 8)
        self.assertEqual(self.lib.sleep_count(), 6)
        self.assertEqual(self.lib.snapshot_count(), 6)
        self.assertEqual(self.records()[:2], [ENTRY, WAKE])
        events = [self.lib.event_at(i) for i in range(self.lib.number_events())]
        self.assertEqual(events[:7], [101,401,201,102,402,301,403])
        for n,line in enumerate(self.records()[2:]):
            self.assertTrue(line.startswith(f'\nK230_UP1 n={n} s=0 '.encode()))
        self.assertEqual(self.lib.health(), 0)

    def test_absent_gate_keeps_original_records_and_event_order(self):
        old = self.libraries['original']
        for lib in (old,self.lib): lib.base_flag(b'1'); lib.execute()
        self.assertEqual(self.records(old), self.records())
        self.assertEqual([old.event_at(i) for i in range(old.number_events())],
                         [self.lib.event_at(i) for i in range(self.lib.number_events())])

    def test_bare_invalid_and_null_new_gate_keep_original_six_samples(self):
        for flag in (b'k230.uart_progress_breadcrumbs', b'k230.uart_progress_breadcrumbs=0',
                     b'k230.uart_progress_breadcrumbs=01', b'k230.uart_progress_breadcrumbs=1x',
                     b'k230.uart_progress_breadcrumbs=', b'other=1'):
            self.lib.reset(); self.lib.base_flag(b'1'); self.lib.parse_new(flag); self.lib.execute()
            self.assertEqual(self.lib.count(), 6)
            self.assertFalse(any(b'UPB1' in line for line in self.records()))
        self.lib.reset();self.lib.base_flag(b'1');self.lib.new_flag(None);self.lib.execute()
        self.assertEqual(self.lib.count(),6)

    def test_exact_new_gate_is_recognized(self):
        self.lib.base_flag(b'1');self.lib.parse_new(b'k230.uart_progress_breadcrumbs=1');self.lib.execute()
        self.assertEqual(self.records()[:2],[ENTRY,WAKE])

    def test_invalid_value_after_valid_clears_new_gate(self):
        self.enable();self.lib.new_flag(b'01');self.lib.execute()
        self.assertEqual(self.lib.count(),6)
        self.assertFalse(any(b'UPB1' in line for line in self.records()))

    def test_original_runtime_gate_still_required(self):
        for flag in (None,b'',b'0',b'01',b'1x'):
            self.lib.reset();self.lib.base_flag(flag);self.lib.new_flag(b'1');self.lib.execute()
            self.assertEqual(self.lib.start_count(),0);self.assertEqual(self.lib.count(),0)

    def test_unavailable_extension_starts_no_worker(self):
        self.enable();self.lib.available(0);self.lib.execute()
        self.assertEqual(self.lib.start_count(),0);self.assertEqual(self.lib.count(),0)

    def test_configoff_has_no_breadcrumb_calls(self):
        lib=self.libraries['configoff'];self.enable(lib);lib.execute()
        self.assertEqual(lib.count(),6)
        self.assertFalse(any(b'UPB1' in line for line in self.records(lib)))

    def test_full_partial_zero_error_never_retries(self):
        for result in (9999,1,0,-1,-5):
            self.lib.reset();self.enable();self.lib.returned(result);self.lib.execute()
            self.assertEqual(self.lib.count(),8);self.assertEqual(self.records()[:2],[ENTRY,WAKE])
            self.assertEqual(self.lib.health(),0)

    def test_stop_before_sleep_keeps_entry_unattempted(self):
        self.enable();self.lib.stop(1);self.lib.execute()
        self.assertEqual(self.lib.count(),0);self.assertEqual(self.lib.sleep_count(),0)

    def test_stop_after_first_sleep_keeps_post_sleep_unattempted(self):
        self.enable();self.lib.stop(2);self.lib.execute()
        self.assertEqual(self.records(),[ENTRY]);self.assertEqual(self.lib.sleep_count(),1)
        self.assertEqual(self.lib.snapshot_count(),0)

    def test_stop_later_keeps_prior_stop_and_delay_semantics(self):
        self.enable();self.lib.stop(4);self.lib.execute()
        self.assertEqual(self.lib.count(),3);self.assertEqual(self.lib.sleep_count(),2)
        self.assertEqual(self.lib.snapshot_count(),1)

    def test_source_change_is_only_additive_worker_breadcrumbs(self):
        added='\n'.join(line[1:] for line in PATCH.read_text().splitlines()
                        if line.startswith('+') and not line.startswith('+++'))
        for symbol in ('printk(', 'pr_info(', 'nbcon_', 'readl(', 'writel(', 'serial_in(',
                       'serial_out(', 'sched_set', 'set_cpus_allowed', 'snprintf(', 'kstat_irqs_usr('):
            self.assertNotIn(symbol,added)
        self.assertNotIn('__initdata',added);self.assertNotIn('__initconst',added)
        self.assertIn('static void k230_uart_progress_breadcrumb(',added)
        self.assertEqual(added.count('sbi_debug_console_write('),1)
        self.assertEqual(self.patched.count('msleep(K230_UP_DELAY_MS);'),1)
        self.assertEqual(self.patched.count('k230_uart_progress_snapshot(&s);'),1)
        self.assertLessEqual(len(ENTRY)+1,64);self.assertLessEqual(len(WAKE)+1,64)


if __name__ == '__main__': unittest.main()
