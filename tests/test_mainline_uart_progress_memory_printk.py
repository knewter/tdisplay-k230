"""Execute actual layered observer C with isolated native printk/SBI callbacks."""
import ctypes
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

import test_mainline_uart_progress_memory as memory

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / 'nix/patches/mainline/k230-uart-progress-memory-printk.patch'
PRINT = r'''
static int print_calls,print_result;
static char print_record[256];
static int native_pr_info(const char *format,unsigned int s,unsigned int n,
                          unsigned int m,unsigned int l,unsigned int w) {
 int length=snprintf(print_record,sizeof(print_record),format,s,n,m,l,w);
 if(length<=0 || length>=256)bad++;
 print_calls++;event(500);return print_result;
}
#define pr_info native_pr_info
'''
END = r'''
void printk_flag(const char *s) {
#ifdef PRINTK_VARIANT
 k230_uart_progress_memory_printk_setup((char *)s);
#else
 (void)s;
#endif
}
void parse_printk_flag(const char *s) {
#ifdef PRINTK_VARIANT
 const char *key=key_k230_uart_progress_memory_printk_setup;size_t n=strlen(key);
 if(!strncmp(s,key,n))k230_uart_progress_memory_printk_setup((char *)s+n);
#else
 (void)s;
#endif
}
int print_count(void) { return print_calls; }
const char *printed(void) { return print_record; }
void print_returned(int n) { print_result=n; }
'''


class MemoryPrintk(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        folder=Path(cls.temp.name)
        worker=folder/'drivers/soc/canaan/k230-uart-progress.c'
        worker.parent.mkdir(parents=True)
        worker.write_bytes((ROOT/'nix/patches/mainline/k230-uart-progress.c').read_bytes())
        for patch in [*memory.PATCHES,PATCH]:
            if patch==PATCH:cls.parent=worker.read_text()
            subprocess.run(['patch','--batch','--fuzz=0','-p1','-i',str(patch)],cwd=folder,check=True,capture_output=True)
        cls.source=worker.read_text()
        prefix=memory.PREFIX.replace('records[8][256]','records[10][256]').replace('calls>=8','calls>=10').replace('calls<8','calls<10')
        prefix=prefix.replace('events[64]','events[128]').replace('event_count>=64','event_count>=128')
        prefix=re.sub(r'static struct task_struct \*kthread_run\(.*?\n#define PTR_ERR\(x\) .*?\n','',prefix,flags=re.S)
        suffix=memory.SUFFIX.replace('calls=sleeps=starts=', 'print_calls=print_result=0;memset(print_record,0,sizeof print_record);\n calls=sleeps=starts=')
        suffix=suffix.replace('sbi_debug_console_available=true;', '#ifdef PRINTK_VARIANT\n k230_uart_progress_memory_printk_enabled=false;\n#endif\n sbi_debug_console_available=true;')
        cls.libs={}
        for name,source,config in [('parent',cls.parent,1),('printk',cls.source,1),('configoff',cls.source,0)]:
            code=re.sub(r'^#include[^\n]*\n','',source,flags=re.M)
            c=folder/(name+'.c');c.write_text(prefix+memory.EXTRA+PRINT+code+suffix+END)
            args=['gcc','-shared','-fPIC','-std=gnu11','-Wall','-Wextra','-Werror','-DMEMORY_VARIANT=1',f'-DCONFIG_RISCV_SBI={config}']
            if name!='parent':args+=['-DPRINTK_VARIANT=1']
            else:args+=['-Wno-unused-function']
            subprocess.run(args+[str(c),'-o',str(folder/(name+'.so'))],check=True,capture_output=True)
            lib=ctypes.CDLL(str(folder/(name+'.so')))
            for function in ('record','printed'):getattr(lib,function).restype=ctypes.c_char_p
            for function in ('base_flag','bread_flag','post_flag','memory_flag','printk_flag','parse_printk_flag'):getattr(lib,function).argtypes=[ctypes.c_char_p]
            cls.libs[name]=lib

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def setUp(self):
        for lib in self.libs.values():lib.reset()
        self.lib=self.libs['printk']
    def enable(self,lib=None):
        lib=lib or self.lib;lib.base_flag(b'1');lib.memory_flag(b'1');lib.printk_flag(b'1')
    def summary(self):
        self.assertEqual(self.lib.print_count(),1);self.assertEqual(self.lib.count(),0);self.assertEqual(self.lib.health(),0)
        m=re.fullmatch(rb'\nK230_UMK1 s=([0-6]) n=([0-6]) m=([0-9a-f]{2}) l=([0-6]) w=([01])\n',self.lib.printed())
        self.assertIsNotNone(m);s,n,b,l,w=m.groups();return int(s),int(n),int(b,16),int(l),int(w)
    def test_selected_worker_silent_six_snapshots_one_printk_no_SBI(self):
        self.enable();self.lib.bread_flag(b'1');self.lib.post_flag(b'1');self.lib.initialize();self.lib.worker()
        self.assertEqual(self.lib.count(),0);self.assertEqual(self.lib.print_count(),0)
        self.assertEqual((self.lib.sleep_count(),self.lib.snapshot_count(),self.lib.check_count()),(6,6,12))
        self.lib.observer();self.assertEqual(self.summary(),(4,5,63,5,1))
        self.assertEqual((self.lib.start_count(),self.lib.wait_count(),self.lib.acquire_count(),self.lib.complete_count()),(2,1,1,1))
    def test_absent_bare_null_invalid_gate_matches_actual_Memory_parent(self):
        for flag in (None,b'',b'0',b'01',b'true',b'1 ',b'1x'):
            self.lib.reset();parent=self.libs['parent'];parent.reset()
            for lib in (self.lib,parent):self.enable(lib);lib.printk_flag(flag);lib.execute()
            self.assertEqual(self.lib.print_count(),0)
            self.assertEqual(self.lib.record(0),parent.record(0));self.assertEqual(self.lib.count(),1)
            for method in ('pub_count','sleep_count','snapshot_count','wait_count','acquire_count','complete_count','number_events'):
                self.assertEqual(getattr(self.lib,method)(),getattr(parent,method)())
            self.assertEqual([self.lib.event_at(i)for i in range(self.lib.number_events())],[parent.event_at(i)for i in range(parent.number_events())])
    def test_setup_exact_key_and_invalid_after_valid(self):
        self.enable();self.lib.printk_flag(b'0');self.lib.execute();self.assertEqual(self.lib.print_count(),0)
        for flag,expected in ((b'k230.uart_progress_memory_printk=1',1),(b'k230.uart_progress_memory_printk',0),(b'other=1',0),(b'k230.uart_progress_memory_printk=01',0)):
            self.lib.reset();self.lib.base_flag(b'1');self.lib.memory_flag(b'1');self.lib.parse_printk_flag(flag);self.lib.execute();self.assertEqual(self.lib.print_count(),expected)
    def test_existing_gates_and_extension_required(self):
        for base,mem,avail in ((b'0',b'1',1),(b'1',b'0',1),(b'1',b'1',0)):
            self.lib.reset();self.lib.base_flag(base);self.lib.memory_flag(mem);self.lib.printk_flag(b'1');self.lib.available(avail);self.lib.execute()
            self.assertEqual(self.lib.print_count(),0);self.assertEqual(self.lib.wait_count(),0)
        lib=self.libs['configoff'];self.enable(lib);lib.execute();self.assertEqual(lib.print_count(),0);self.assertEqual(lib.wait_count(),0)
    def test_each_stop_boundary_preserves_partial_terminal_state(self):
        for stop in range(1,13):
            self.lib.reset();self.enable();self.lib.stop(stop);self.lib.execute();n=(stop-1)//2
            self.assertEqual(self.summary(),(5,n,(1<<n)-1,n-1 if n else 6,1))
    def test_timeout_and_terminal_race_single_acquire(self):
        for stage,n,mask in ((0,6,0),(1,2,3),(2,2,3),(3,2,7),(4,5,63),(5,0,0),(6,6,0)):
            self.lib.reset();self.enable();self.lib.initialize();self.lib.publish(stage,n,mask);self.lib.timed_out(1);self.lib.observer()
            self.assertEqual(self.summary(),(stage,n,mask,mask.bit_length()-1 if mask else 6,0));self.assertEqual(self.lib.acquire_count(),1)
    def test_creation_failures_preserved(self):
        self.enable();self.lib.failure(1);self.lib.execute();self.assertEqual(self.lib.initialization_rc(),-12);self.assertEqual(self.lib.print_count(),0)
        self.lib.reset();self.enable();self.lib.failure(2);self.lib.execute();self.assertEqual(self.lib.initialization_rc(),-12);self.assertEqual(self.summary(),(6,6,0,6,1))
    def test_printk_return_ignored_no_retry_or_firmware_fallback(self):
        for result in (0,1,64,-1,-5):
            self.lib.reset();self.enable();self.lib.print_returned(result);self.lib.execute();self.assertEqual(self.summary(),(4,5,63,5,1));self.assertEqual(self.lib.wait_count(),1)
    def test_publication_sequence_identical_to_Memory(self):
        self.enable();self.lib.execute();parent=self.libs['parent'];self.enable(parent);parent.execute()
        self.assertEqual([self.lib.publication(i)for i in range(self.lib.pub_count())],[parent.publication(i)for i in range(parent.pub_count())])
    def test_actual_worker_and_remaining_observer_bytes_unchanged(self):
        self.assertEqual(self.source[self.source.index('static int k230_uart_progress_worker'):],self.parent[self.parent.index('static int k230_uart_progress_worker'):])
        added='\n'.join(s[1:]for s in PATCH.read_text().splitlines()if s.startswith('+')and not s.startswith('+++'))
        self.assertEqual(added.count('pr_info('),1)
        for forbidden in ('sbi_debug_console_write','nbcon_','printk_deferred','readl(','writel(','serial_','sched_set','__initdata','__initconst','while ('):
            self.assertNotIn(forbidden,added)
        self.assertIn('return 0;',added)
        self.assertEqual(self.source.count('atomic_read_acquire('),1);self.assertEqual(self.source.count('wait_for_completion_timeout('),1)
        self.assertNotIn('__init',self.source[self.source.index('static int k230_uart_progress_memory_observer'):self.source.index('static int __init k230_uart_progress_memory_setup')])


if __name__=='__main__':unittest.main()
