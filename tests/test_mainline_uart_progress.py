"""Native actual-code/API fixtures; no kernel, firmware, UART or board run."""
import ctypes
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / 'nix/patches/mainline/k230-uart-progress.patch'
SOURCE = ROOT / 'nix/patches/mainline/k230-uart-progress.c'


class UartProgress(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        added = '\n'.join(s[1:] for s in PATCH.read_text().splitlines()
                          if s.startswith('+') and not s.startswith('+++'))
        a = added.index('void k230_uart_progress_snapshot(')
        b = added.index('\n#endif', a)
        snapshot = added[a:b]
        timer_start = added.index('static unsigned int k230_uart_progress_ready_timer_irq;')
        timer_end = added.index('\n#endif', timer_start)
        timer_getter = added[timer_start:timer_end]
        worker = re.sub(r'^#include[^\n]*\n', '', SOURCE.read_text(), flags=re.M)
        header = (ROOT / 'nix/patches/mainline/k230-uart-progress.h').read_text()
        header = re.sub(r'^#include[^\n]*\n', '', header, flags=re.M)
        prefix = r'''
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32;
typedef uint64_t u64;
#define __init
#define __aligned(n) __attribute__((aligned(n)))
#define __setup(k, f) static const char *setup_key = k
#define late_initcall(f)
#define READ_ONCE(x) (x)
#define PORT_UNKNOWN 0
static int lifetime, port_lock, life_ok, port_ok, life_tries, port_tries, bad;
static int serial_mutex, sleeps, calls, starts, stopped, stop_after, result, maximal, change_second;
static bool sbi_debug_console_available;
struct task_struct { int unused; };
static struct task_struct task;
struct node { int id; }; static struct node uart_node, plic_node;
struct device { struct node *of_node; };
struct domain { struct node *node; };
struct irq_data { unsigned long hwirq; struct domain *domain; };
static struct domain domain; static struct irq_data irq_data;
struct counts { u32 rx,tx,frame,parity,overrun,buf_overrun; };
struct uart_port { struct device *dev; void *state; int type,line,irq,lock;
  unsigned long mapbase; struct counts icount; u32 read_status_mask,ignore_status_mask,uartclk; };
struct uart_8250_port { struct uart_port port; u32 ier; };
static struct uart_8250_port serial8250_ports[1]; static struct device dev;
#define timer_irq k230_uart_progress_ready_timer_irq
static char records[6][256]; static unsigned int lengths[6];
static int mutex_trylock(int *p) { (void)p; life_tries++; if (!life_ok) return 0; lifetime++; return 1; }
static void mutex_unlock(int *p) { (void)p; if (lifetime != 1 || port_lock) bad++; lifetime--; }
static int take_port(void) { port_tries++; if (!port_ok) return 0; port_lock++; return 1; }
#define spin_trylock_irqsave(p,f) ((f)=0, (void)(p), take_port())
#define spin_unlock_irqrestore(p,f) do { (void)(p); (void)(f); if(port_lock!=1)bad++; port_lock--; } while(0)
static void rcu_read_lock(void) { if(!lifetime || port_lock)bad++; }
static void rcu_read_unlock(void) { if(!lifetime || port_lock)bad++; }
static struct irq_data *irq_get_irq_data(unsigned int irq) { return irq ? &irq_data : NULL; }
static struct node *irq_domain_get_of_node(struct domain *d) { return d ? d->node : NULL; }
static bool of_device_is_compatible(struct node *n, const char *s) {
  return n && ((n->id==1 && !strcmp(s,"snps,dw-apb-uart")) ||
               (n->id==2 && !strcmp(s,"canaan,k230-plic"))); }
static unsigned int kstat_irqs_usr(unsigned int irq) { if(port_lock)bad++; return irq*10; }
static int kthread_should_stop(void) { return stopped || (stop_after >= 0 && sleeps>=stop_after); }
static void msleep(unsigned int n) { if(n!=5000 || lifetime || port_lock)bad++; sleeps++; if(change_second && sleeps==2)serial8250_ports[0].port.irq=18; }
static u64 ktime_get_ns(void) { return maximal ? UINT64_MAX : (u64)sleeps*5000000000ULL; }
static u64 get_jiffies_64(void) { return maximal ? UINT64_MAX : (u64)sleeps*1250; }
static int sbi_debug_console_write(const char *s, unsigned int n) {
 if(lifetime || port_lock || n>=256 || !n || (uintptr_t)s%256 || calls>=6)bad++;
 if(calls<6) { memcpy(records[calls],s,n); records[calls][n]=0; lengths[calls]=n; }
 calls++; return result == 9999 ? (int)n : result;
}
static struct task_struct *kthread_run(int (*f)(void *),void *p,const char *name) {
 (void)f; (void)p; if(strcmp(name,"k230-uart-progress"))bad++; starts++; return &task; }
#define IS_ERR(p) ((void)(p), false)
#define PTR_ERR(p) ((void)(p), 0)
'''
        suffix = r'''
void reset(void) {
 lifetime=port_lock=life_tries=port_tries=bad=sleeps=calls=starts=stopped=result=0;
 stop_after=-1; maximal=change_second=0; life_ok=port_ok=1; timer_irq=5; sbi_debug_console_available=true;
 result=9999; k230_uart_progress_enabled=false; memset(records,0,sizeof records);
 uart_node.id=1; plic_node.id=2; dev.of_node=&uart_node; domain.node=&plic_node;
 irq_data.hwirq=16; irq_data.domain=&domain;
 serial8250_ports[0]=(struct uart_8250_port){.ier=5,.port={.dev=&dev,.state=&dev,
 .type=1,.line=0,.irq=17,.mapbase=0x91400000,.icount={1,2,3,4,5,6},
 .read_status_mask=7,.ignore_status_mask=8,.uartclk=50000000}};
}
int parse(const char *s) { size_t n=strlen(setup_key); return strncmp(s,setup_key,n)?0:k230_uart_progress_setup((char *)s+n); }
void setup(const char *s) { k230_uart_progress_setup((char *)s); }
void available(int x) { sbi_debug_console_available=x; }
void init(void) { (void)k230_uart_progress_init(); }
void run(void) { (void)k230_uart_progress_worker(NULL); }
void inject(int code) {
 switch(code) { case 1:life_ok=0;break;case 2:port_ok=0;break;case 3:serial8250_ports[0].port.dev=NULL;break;
 case 4:serial8250_ports[0].port.mapbase++;break;case 5:irq_data.hwirq=17;break;
 case 6:irq_data.domain=NULL;break;case 7:timer_irq=0;break;case 8:stop_after=2;break;
 case 9:maximal=1; serial8250_ports[0].port.icount=(struct counts){UINT32_MAX,UINT32_MAX,UINT32_MAX,UINT32_MAX,UINT32_MAX,UINT32_MAX};
 serial8250_ports[0].ier=serial8250_ports[0].port.uartclk=serial8250_ports[0].port.read_status_mask=serial8250_ports[0].port.ignore_status_mask=UINT32_MAX;break;
 case 10:change_second=1;break;case 11:stop_after=0;break; }
}
void returned(int x) { result=x; }
int call_count(void) { return calls; }
int start_count(void) { return starts; }
int sleep_count(void) { return sleeps; }
int health(void) { return bad || lifetime || port_lock; }
const char *record(unsigned int i) { return records[i]; }
unsigned int record_length(unsigned int i) { return lengths[i]; }
void snapshot(unsigned int *out) { k230_uart_progress_snapshot((void *)out); }
int life_attempts(void) { return life_tries; }
int port_attempts(void) { return port_tries; }
'''
        path = Path(cls.temp.name)
        source = path / 'test.c'
        source.write_text(prefix + header + '\n' + snapshot + '\n' + timer_getter + '\n' + worker + suffix)
        subprocess.run(['gcc', '-shared', '-fPIC', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                        str(source), '-o', str(path/'test.so')], check=True, capture_output=True)
        cls.lib = ctypes.CDLL(str(path/'test.so'))
        cls.lib.record.restype = ctypes.c_char_p
        cls.lib.parse.argtypes = [ctypes.c_char_p]
        cls.lib.setup.argtypes = [ctypes.c_char_p]

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.lib.reset()

    def test_exact_runtime_gate_disabled_bare_invalid(self):
        for flag in (b'k230.uart_progress', b'k230.uart_progress=0', b'k230.uart_progress=01',
                     b'k230.uart_progress=1x', b'other=1'):
            self.lib.reset(); self.lib.parse(flag); self.lib.init()
            self.assertEqual(self.lib.start_count(), 0)
        self.lib.setup(None); self.lib.init(); self.assertEqual(self.lib.start_count(), 0)
        self.lib.parse(b'k230.uart_progress=1'); self.lib.init()
        self.assertEqual(self.lib.start_count(), 1)
        self.assertEqual(self.lib.call_count(), 0)

    def test_extension_unavailable_starts_no_worker(self):
        self.lib.parse(b'k230.uart_progress=1'); self.lib.available(0); self.lib.init()
        self.assertEqual(self.lib.start_count(), 0)

    def test_six_finite_single_attempt_aligned_complete_records(self):
        self.lib.run()
        self.assertEqual(self.lib.call_count(), 6); self.assertEqual(self.lib.sleep_count(), 6)
        for n in range(6):
            record = self.lib.record(n)
            self.assertTrue(record.startswith(f'\nK230_UP1 n={n} s=0 '.encode()))
            self.assertTrue(record.endswith(b'\n'))
            self.assertEqual(record.count(b'K230_UP1'), 1)
            self.assertEqual(len(record), self.lib.record_length(n))
            self.assertLess(len(record), 256)
            self.assertIn(b'u=00000011 ti=00000005 ui=000000aa tc=00000032', record)
        self.assertEqual(self.lib.health(), 0)

    def test_partial_zero_error_do_not_retry_or_fallback(self):
        for result in (0, 1, -1, -5):
            self.lib.reset(); self.lib.returned(result); self.lib.run()
            self.assertEqual(self.lib.call_count(), 6); self.assertEqual(self.lib.health(), 0)

    def test_lifecycle_and_port_busy_are_single_try_states(self):
        for code, state, ports in ((1, 1, 0), (2, 2, 1)):
            self.lib.reset(); self.lib.inject(code)
            out = (ctypes.c_uint * 13)(); self.lib.snapshot(out)
            self.assertEqual(out[0], state); self.assertEqual(self.lib.life_attempts(), 1)
            self.assertEqual(self.lib.port_attempts(), ports); self.assertEqual(sum(out[1:]), 0)
            self.assertEqual(self.lib.health(), 0)

    def test_unavailable_binding_missing_domain_fail_closed(self):
        for code, state in ((3, 3), (4, 4), (5, 4), (6, 4)):
            self.lib.reset(); self.lib.inject(code)
            out = (ctypes.c_uint * 13)(); self.lib.snapshot(out)
            self.assertEqual(out[0], state); self.assertEqual(self.lib.port_attempts(), 0)
            self.assertEqual(self.lib.health(), 0)

    def test_timer_unavailable_distinct_from_accounted_zero(self):
        self.lib.inject(7); self.lib.run()
        self.assertIn(b'ti=00000000', self.lib.record(0))
        self.assertIn(b'tc=00000000', self.lib.record(0))

    def test_stop_is_finite_and_no_emit_after_stopped(self):
        self.lib.inject(8); self.lib.run()
        self.assertEqual(self.lib.sleep_count(), 2); self.assertEqual(self.lib.call_count(), 1)

    def test_maximum_numeric_values_fit_complete_frame(self):
        self.lib.inject(9); self.lib.run()
        for i in range(6):
            record = self.lib.record(i)
            self.assertIn(b'j=ffffffffffffffff t=ffffffffffffffff', record)
            self.assertIn(b'hz=ffffffff', record)
            self.assertTrue(record.endswith(b'\n'))
            self.assertLess(len(record), 256)
        self.assertEqual(self.lib.health(), 0)

    def test_changed_binding_is_explicit_and_not_measured(self):
        self.lib.inject(10); self.lib.run()
        self.assertIn(b'n=0 s=0 ', self.lib.record(0))
        self.assertIn(b'n=1 s=5 ', self.lib.record(1))
        self.assertIn(b'ui=00000000', self.lib.record(1))
        self.assertIn(b'u=00000000', self.lib.record(1))
        self.assertIn(b'rx=00000000', self.lib.record(1))
        self.assertIn(b'hz=00000000', self.lib.record(1))
        self.assertEqual(self.lib.health(), 0)

    def test_stop_before_sleep_sends_nothing(self):
        self.lib.inject(11); self.lib.run()
        self.assertEqual(self.lib.sleep_count(), 0)
        self.assertEqual(self.lib.call_count(), 0)

    def test_source_has_no_mmio_tty_nbcon_or_emergency_operations(self):
        source = SOURCE.read_text()
        added = '\n'.join(s[1:] for s in PATCH.read_text().splitlines()
                          if s.startswith('+') and not s.startswith('+++'))
        for text in (source, added):
            for symbol in ('pr_info(', 'printk(', 'nbcon_', 'uart_port_trylock',
                           'serial8250_get_port(', 'readl(', 'writel(', 'serial_in(',
                           'serial_out(', 'set_termios(', 'sched_set', 'set_cpus_allowed'):
                self.assertNotIn(symbol, text)
        self.assertIn('READ_ONCE(p->uartclk)', added)
        self.assertIn('if (!error)\n+\t\tWRITE_ONCE', PATCH.read_text())
        self.assertIn('depends on SERIAL_8250=y', PATCH.read_text())


if __name__ == '__main__':
    unittest.main()
