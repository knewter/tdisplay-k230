"""Execute actual Memory-applied C with isolated native callbacks; no board."""
import ctypes
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from test_mainline_uart_progress_breadcrumbs import PREFIX

ROOT = Path(__file__).resolve().parents[1]
PATCHES = [ROOT / ('nix/patches/mainline/' + name) for name in (
    'k230-uart-progress-breadcrumbs.patch', 'k230-uart-progress-post-sample.patch',
    'k230-uart-progress-memory.patch')]

EXTRA = r'''
typedef struct { int counter; } atomic_t;
#define ATOMIC_INIT(x) {x}
struct completion { int done; };
#define DECLARE_COMPLETION(x) struct completion x = {0}
static int publishes,acquires,waits,completions,timeout_mode,worker_created,observer_created,fail_create,init_rc;
static int words[32];
static void atomic_set_release(atomic_t *p,int n) {
 if(publishes>=32 || n<0 || n>=4096)bad++;else words[publishes]=n;
 publishes++;p->counter=n;
}
static int atomic_read_acquire(const atomic_t *p) { acquires++;return p->counter; }
static void complete(struct completion *p) { p->done=1;completions++; }
static unsigned long msecs_to_jiffies(unsigned int n) { return n/4; }
static unsigned long wait_for_completion_timeout(struct completion *p,unsigned long n) {
 waits++;if(n!=11250)bad++;return !timeout_mode && p->done?1:0;
}
static struct task_struct *kthread_run(int (*f)(void *),void *arg,const char *name) {
 (void)f;(void)arg;starts++;
 if(fail_create==starts)return (struct task_struct *)(intptr_t)-12;
 if(!strcmp(name,"k230-uart-progress"))worker_created++;
 else if(!strcmp(name,"k230-uart-memory"))observer_created++;else bad++;
 return &task;
}
#define IS_ERR(x) ((intptr_t)(x)<0)
#define PTR_ERR(x) ((int)(intptr_t)(x))
'''
SUFFIX = r'''
void reset(void) {
 calls=sleeps=starts=checks=stop_at=bad=snapshots=event_count=0;result=9999;
 publishes=acquires=waits=completions=timeout_mode=worker_created=observer_created=fail_create=init_rc=0;
 memset(records,0,sizeof records);memset(events,0,sizeof events);memset(words,0,sizeof words);
 sbi_debug_console_available=true;k230_uart_progress_enabled=false;
 k230_uart_progress_breadcrumbs_enabled=false;k230_uart_progress_post_sample_enabled=false;
#ifdef MEMORY_VARIANT
 k230_uart_progress_memory_enabled=false;k230_uart_progress_memory_done.done=0;
 k230_uart_progress_memory_state.counter=0;
#endif
}
void base_flag(const char *s) { k230_uart_progress_setup((char *)s); }
void bread_flag(const char *s) { k230_uart_progress_breadcrumbs_setup((char *)s); }
void post_flag(const char *s) { k230_uart_progress_post_sample_setup((char *)s); }
void memory_flag(const char *s) {
#ifdef MEMORY_VARIANT
 k230_uart_progress_memory_setup((char *)s);
#else
 (void)s;
#endif
}
void parse_flag(const char *s) {
#ifdef MEMORY_VARIANT
 const char *key=key_k230_uart_progress_memory_setup;size_t n=strlen(key);
 if(!strncmp(s,key,n))k230_uart_progress_memory_setup((char *)s+n);
#else
 (void)s;
#endif
}
void available(int n) { sbi_debug_console_available=n; }
void stop(int n) { stop_at=n; }
void returned(int n) { result=n; }
void failure(int n) { fail_create=n; }
void timed_out(int n) { timeout_mode=n; }
void initialize(void) { init_rc=k230_uart_progress_init(); }
void worker(void) { if(worker_created)(void)k230_uart_progress_worker(NULL); }
void observer(void) {
#ifdef MEMORY_VARIANT
 if(observer_created)(void)k230_uart_progress_memory_observer(NULL);
#endif
}
void execute(void) { initialize();worker();observer(); }
void publish(int s,int n,int m) {
#ifdef MEMORY_VARIANT
 k230_uart_progress_memory_publish(s,n,m);
#else
 (void)s;(void)n;(void)m;
#endif
}
int count(void) { return calls; }
int sleep_count(void) { return sleeps; }
int snapshot_count(void) { return snapshots; }
int start_count(void) { return starts; }
int check_count(void) { return checks; }
int health(void) { return bad; }
int pub_count(void) { return publishes; }
int acquire_count(void) { return acquires; }
int wait_count(void) { return waits; }
int complete_count(void) { return completions; }
int initialization_rc(void) { return init_rc; }
int publication(int i) { return words[i]; }
const char *record(int i) { return records[i]; }
int event_at(int i) { return events[i]; }
int number_events(void) { return event_count; }
'''


class Memory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        folder = Path(cls.temp.name)
        worker = folder / 'drivers/soc/canaan/k230-uart-progress.c'
        worker.parent.mkdir(parents=True)
        worker.write_bytes((ROOT/'nix/patches/mainline/k230-uart-progress.c').read_bytes())
        for patch in PATCHES:
            if patch == PATCHES[-1]: cls.parent = worker.read_text()
            subprocess.run(['patch','--batch','--fuzz=0','-p1','-i',str(patch)],
                           cwd=folder,check=True,capture_output=True)
        cls.source = worker.read_text()
        prefix = PREFIX.replace('records[8][256]', 'records[10][256]').replace('calls>=8', 'calls>=10').replace('calls<8', 'calls<10')
        prefix = prefix.replace('events[64]', 'events[128]').replace('event_count>=64', 'event_count>=128')
        prefix = re.sub(r'static struct task_struct \*kthread_run\(.*?\n#define PTR_ERR\(x\) .*?\n', '', prefix, flags=re.S)
        prefix = prefix.replace('int point=!strncmp', 'int point=!strncmp(s,"\\nK230_UMP1 ",11)?3:!strncmp(s,"\\nK230_UPP1 ",11)?4:!strncmp')
        cls.libs = {}
        for name,source,config in [('parent',cls.parent,1),('memory',cls.source,1),('configoff',cls.source,0)]:
            code = re.sub(r'^#include[^\n]*\n', '', source, flags=re.M)
            c = folder/(name+'.c');c.write_text(prefix+EXTRA+code+SUFFIX)
            args=['gcc','-shared','-fPIC','-std=gnu11','-Wall','-Wextra','-Werror',f'-DCONFIG_RISCV_SBI={config}']
            if name!='parent': args+=['-DMEMORY_VARIANT=1']
            # Parent fixtures do not use the new isolated atomic/wait stubs.
            if name=='parent': args+=['-Wno-unused-function']
            subprocess.run(args+[str(c),'-o',str(folder/(name+'.so'))],check=True,capture_output=True)
            lib=ctypes.CDLL(str(folder/(name+'.so')));lib.record.restype=ctypes.c_char_p
            for method in ('base_flag','bread_flag','post_flag','memory_flag','parse_flag'):
                getattr(lib,method).argtypes=[ctypes.c_char_p]
            cls.libs[name]=lib

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()
    def setUp(self):
        for lib in self.libs.values(): lib.reset()
        self.lib=self.libs['memory']
    def enable(self,lib=None):
        lib=lib or self.lib;lib.base_flag(b'1');lib.memory_flag(b'1')
    def records(self,lib=None):
        lib=lib or self.lib;return [lib.record(i) for i in range(lib.count())]
    def summary(self):
        self.assertEqual(self.lib.count(),1);self.assertEqual(self.lib.health(),0)
        match=re.fullmatch(rb'\nK230_UMP1 s=([0-6]) n=([0-6]) m=([0-9a-f]{2}) l=([0-6]) w=([01])\n',self.lib.record(0))
        self.assertIsNotNone(match)
        a,b,m,d,e=match.groups();return int(a),int(b),int(m,16),int(d),int(e)
    def test_all_output_suppressed_then_one_final_complete_summary(self):
        self.enable();self.lib.bread_flag(b'1');self.lib.post_flag(b'1')
        self.lib.initialize();self.lib.worker()
        self.assertEqual(self.lib.count(),0);self.assertEqual(self.lib.sleep_count(),6)
        self.assertEqual(self.lib.snapshot_count(),6);self.assertEqual(self.lib.check_count(),12)
        self.lib.observer();self.assertEqual(self.summary(),(4,5,63,5,1))
        self.assertEqual(self.lib.start_count(),2);self.assertEqual(self.lib.wait_count(),1)
        self.assertEqual(self.lib.acquire_count(),1);self.assertEqual(self.lib.complete_count(),1)
    def test_exact_coherent_publications_before_after_sleep_and_snapshot(self):
        self.enable();self.lib.execute()
        expected=[(0,6,0)]
        for n in range(6): expected += [(1,n,(1<<n)-1),(2,n,(1<<n)-1),(3,n,(1<<(n+1))-1)]
        expected += [(4,5,63)]
        actual=[self.lib.publication(i) for i in range(self.lib.pub_count())]
        self.assertEqual(actual,[s|(n<<3)|(m<<6) for s,n,m in expected])
    def test_absent_invalid_bare_null_gate_preserves_actual_parent_events(self):
        for flag in (None,b'',b'0',b'01',b'true',b'1 ',b'1x'):
            self.lib.reset();parent=self.libs['parent'];parent.reset()
            for lib in (self.lib,parent):
                lib.base_flag(b'1');lib.bread_flag(b'1');lib.post_flag(b'1');lib.memory_flag(flag);lib.execute()
            self.assertEqual(self.records(),self.records(parent))
            self.assertEqual(self.lib.health(),0);self.assertEqual(parent.health(),0)
            self.assertEqual(self.lib.start_count(),1);self.assertEqual(self.lib.wait_count(),0)
            self.assertEqual([self.lib.event_at(i) for i in range(self.lib.number_events())],
                             [parent.event_at(i) for i in range(parent.number_events())])
    def test_exact_setup_key_and_invalid_after_valid(self):
        self.lib.base_flag(b'1');self.lib.parse_flag(b'k230.uart_progress_memory=1');self.lib.execute()
        self.assertEqual(self.summary(),(4,5,63,5,1))
        for flag in (b'k230.uart_progress_memory',b'other=1',b'k230.uart_progress_memory=01'):
            self.lib.reset();self.lib.base_flag(b'1');self.lib.parse_flag(flag);self.lib.execute()
            self.assertEqual(self.lib.count(),6);self.assertEqual(self.lib.wait_count(),0)
        self.lib.reset();self.enable();self.lib.memory_flag(b'0');self.lib.execute()
        self.assertEqual(self.lib.count(),6);self.assertEqual(self.lib.wait_count(),0)
    def test_base_gate_required_and_extension_unavailable(self):
        for base in (None,b'',b'0',b'01'):
            self.lib.reset();self.lib.base_flag(base);self.lib.memory_flag(b'1');self.lib.execute()
            self.assertEqual(self.lib.start_count(),0);self.assertEqual(self.lib.count(),0)
        self.lib.reset();self.enable();self.lib.available(0);self.lib.execute()
        self.assertEqual(self.lib.start_count(),0);self.assertEqual(self.lib.count(),0)
    def test_configoff_creates_no_observer_preserves_inherited_behavior(self):
        lib=self.libs['configoff'];self.enable(lib);lib.execute()
        self.assertEqual(lib.start_count(),1);self.assertEqual(lib.count(),6);self.assertEqual(lib.wait_count(),0)
    def test_every_stop_boundary_has_terminal_consistent_partial_summary(self):
        for stop in range(1,13):
            self.lib.reset();self.enable();self.lib.stop(stop);self.lib.execute()
            n=(stop-1)//2;mask=(1<<n)-1
            self.assertEqual(self.summary(),(5,n,mask,n-1 if n else 6,1))
            self.assertEqual(self.lib.snapshot_count(),n)
            self.assertEqual(self.lib.sleep_count(),n+(stop%2==0))
    def test_observer_creation_failure_starts_no_worker_or_output(self):
        self.enable();self.lib.failure(1);self.lib.execute()
        self.assertEqual(self.lib.initialization_rc(),-12);self.assertEqual(self.lib.start_count(),1)
        self.assertEqual(self.lib.count(),0);self.assertEqual(self.lib.snapshot_count(),0)
    def test_worker_creation_failure_is_published_before_completion(self):
        self.enable();self.lib.failure(2);self.lib.execute()
        self.assertEqual(self.lib.initialization_rc(),-12);self.assertEqual(self.summary(),(6,6,0,6,1))
        self.assertEqual(self.lib.snapshot_count(),0)
    def test_timeout_reads_initialized_or_partial_state_once(self):
        self.enable();self.lib.initialize();self.lib.timed_out(1)
        self.lib.observer();self.assertEqual(self.summary(),(0,6,0,6,0))
        for state in ((1,2,3),(2,2,3),(3,2,7)):
            self.lib.reset();self.enable();self.lib.initialize();self.lib.publish(*state)
            self.lib.timed_out(1);self.lib.observer()
            s,n,m=state;self.assertEqual(self.summary(),(s,n,m,m.bit_length()-1,0))
            self.assertEqual(self.lib.acquire_count(),1);self.assertEqual(self.lib.wait_count(),1)
    def test_terminal_publication_can_race_timeout_without_false_rejection(self):
        self.enable();self.lib.timed_out(1);self.lib.execute()
        self.assertEqual(self.summary(),(4,5,63,5,0))
    def test_one_call_full_partial_zero_error_never_retried(self):
        for result in (9999,1,0,-1,-5):
            self.lib.reset();self.enable();self.lib.returned(result);self.lib.execute()
            self.assertEqual(self.summary(),(4,5,63,5,1))
            self.assertEqual(self.lib.count(),1);self.assertEqual(self.lib.wait_count(),1)
    def test_source_limits_lifetime_and_no_hardware_or_scheduler_changes(self):
        added='\n'.join(line[1:] for line in PATCHES[-1].read_text().splitlines() if line.startswith('+') and not line.startswith('+++'))
        for name in ('printk(', 'pr_info(', 'nbcon_', 'readl(', 'writel(', 'serial_in(', 'serial_out(', 'sched_set', 'set_cpus_allowed', '__initdata','__initconst','read_seq','while ('):
            self.assertNotIn(name,added)
        self.assertEqual(added.count('sbi_debug_console_write('),1)
        self.assertIn('memory_record[256] __aligned(256)',self.source)
        self.assertEqual(self.source.count('msleep(K230_UP_DELAY_MS);'),1)
        self.assertEqual(self.source.count('kthread_should_stop()'),2)
        self.assertEqual(self.source.count('k230_uart_progress_snapshot(&s);'),1)
        self.assertEqual(self.source.count('atomic_read_acquire('),1)
        self.assertEqual(self.source.count('wait_for_completion_timeout('),1)


if __name__=='__main__': unittest.main()
