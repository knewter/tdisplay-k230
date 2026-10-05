"""Actual selected-caller native semantics and optional ordinary-controller gates."""
import ast
import ctypes
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('exec_return_previous',ROOT/'tests/test_mainline_initrd_info_kmsg_logging.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
t,d=f.t,f.d
SOURCE=Path('/nix/store/dsgrv7744lzh418z22gb865c0j09g1qs-linux-mainline-k230-init-exec-return-src/init/main.c')


def selected(original=d.ORIGINAL):
    return t.ordinary_bootargs(original,d.SYSTEM,wait_initramfs_in_initcall=True,without_boot_markers=True,init_exec_return=True)


def prepared():
    p=f.prepared();p.pop('initrd_info_kmsg_logging')
    p['init_exec_return']=True;p['init_exec_return_proof']={'fixture':True};p['init_exec_return_archive']={'fixture':True}
    p['bootargs']=selected();p['diagnostic_controls']=t.diagnostic_controls(True,without_boot_markers=True,init_exec_return=True)
    return p


class Pump:
    def __init__(self,chunks):self.chunks=list(chunks);self.buffer=b'';self.writes=[];self.now=0
    def pump(self):
        self.now+=1
        out=self.chunks.pop(0)if self.chunks else b''
        self.buffer=(self.buffer+out)[-131072:]
        return out
    def clock(self):return self.now
    def write(self,value):self.writes.append(value)


def phase(p):
    return (b'Linux version 7.3.0-rc5 fixture\n[    0.000000] Kernel command line: '+p['bootargs'].removeprefix('bootargs=').encode()+
            b'\n[    4.000000] Run /init as init process\n')


class ArchiveDelta(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('exec_return_qualifier',ROOT/'tools/mainline-init-exec-return-qualify.py')
        cls.q=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.q)

    def trees(self):
        old_root='nix/store/'+'a'*32+'-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-modules-shrunk'
        new_root='nix/store/'+'b'*32+'-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-modules-shrunk'
        common={'init':(0o120777,b'/selected/systemd'),'etc/unit':(0o100644,b'original unit')}
        tree={'':(0o040755,b''),'/lib':(0o040755,b''),'/lib/modules':(0o040755,b''),'/lib/modules/modules.dep':(0o100644,b'unchanged')}
        return tuple({**common,'lib':(0o120777,('/'+root+'/lib').encode()),
                      **{root+name:value for name,value in tree.items()}}for root in (old_root,new_root))

    def test_exact_module_tree_relocation_and_no_delta(self):
        old,new=self.trees();proof=self.q.archive_delta(old,new)
        self.assertEqual(proof['changed'],['lib'])
        self.assertEqual(proof['module_tree_relocation']['entries'],4)
        self.assertTrue(proof['module_tree_relocation']['normalized_bytes_and_modes_equal'])
        self.assertIsNone(self.q.archive_delta(old,old)['module_tree_relocation'])

    def test_rejects_changed_tree_dependency_unit_mode_and_target(self):
        old,new=self.trees();module=next(k for k in new if k.endswith('modules.dep'))
        mutations=[{**new,module:(0o100644,b'changed module')},
                   {**new,module:(0o100600,b'unchanged')},
                   {**new,'etc/new':(0o100644,b'extra dependency')},
                   {**new,'etc/unit':(0o100644,b'changed unit')},
                   {**new,'lib':(0o100644,new['lib'][1])},
                   {**new,'lib':(0o120700,new['lib'][1])},
                   {**new,'lib':(0o120777,b'/nix/store/arbitrary/lib')},
                   {k:v for k,v in new.items()if k!=module}]
        for changed in mutations:
            with self.subTest(changed=changed):
                with self.assertRaises(ValueError):self.q.archive_delta(old,changed)


class Native(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # CI need not have the realized source; the patch defines exact additions.
        patch=(ROOT/'nix/patches/mainline/k230-init-exec-return.patch').read_text()
        additions='\n'.join(line[1:]for line in patch.splitlines()if line.startswith('+')and not line.startswith('+++'))
        definitions=additions[:additions.index('\t\tif (k230_init_exec_return_enabled)')]
        marker=additions[additions.index('\t\tif (k230_init_exec_return_enabled)'):]
        # Original selected call/branches taken verbatim from committed source baseline.
        original='''\tif (ramdisk_execute_command) {
\t\tret = run_init_process(ramdisk_execute_command);
\t\tif (!ret)
\t\t\treturn 0;
\t\tpr_err("Failed to execute %s (error %d)\\n",
\t\t       ramdisk_execute_command, ret);
\t}
'''
        new=original.replace('\t\tif (!ret)',marker+'\n\t\tif (!ret)')
        cls.original=original;cls.additions=additions
        cls.temp=tempfile.TemporaryDirectory();directory=Path(cls.temp.name)
        prefix='''#include <stdbool.h>
#include <string.h>
#include <stdio.h>
#include <stdarg.h>
#define __init
#define __setup(key, fn)
static int returned,calls,prints,errors,ret;
static const char *ramdisk_execute_command;
static char record[128];
static int run_init_process(const char *s){(void)s;calls++;return returned;}
static void output(const char *fmt,...){va_list a;va_start(a,fmt);vsnprintf(record,sizeof(record),fmt,a);va_end(a);prints++;}
#define pr_info output
#define pr_err(...) errors++
'''
        code=prefix+definitions+'\nint selected(void){\n'+new+'return 77;\n}\n'+'''
void reset(int result,int present){returned=result;ramdisk_execute_command=present?"/init":NULL;calls=prints=errors=0;k230_init_exec_return_enabled=false;record[0]=0;}
int setup(char *s){return k230_init_exec_return_setup(s);}
int count(void){return prints;}
int call_count(void){return calls;}
int error_count(void){return errors;}
const char *text(void){return record;}
'''
        source=directory/'probe.c';source.write_text(code);output=directory/'probe.so'
        subprocess.run(['gcc','-std=gnu11','-Wall','-Wextra','-Werror','-shared','-fPIC',str(source),'-o',str(output)],check=True,capture_output=True)
        cls.lib=ctypes.CDLL(str(output));cls.lib.text.restype=ctypes.c_char_p
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_default_disabled_and_invalid_exact_values_preserve_branches(self):
        for value in (None,b'',b'0',b'01',b'1x',b' 1',b'true',b'-1'):
            for returned in (0,-2,-13,1):
                self.lib.reset(returned,1)
                if value is not None:self.assertEqual(self.lib.setup(value),1)
                self.assertEqual(self.lib.selected(),0 if returned==0 else 77)
                self.assertEqual(self.lib.count(),0);self.assertEqual(self.lib.call_count(),1)
                self.assertEqual(self.lib.error_count(),returned!=0)
    def test_exact1_single_signed_record_return_value_ignored(self):
        for returned in (0,-2,-13,-2147483648,2147483647):
            self.lib.reset(returned,1);self.lib.setup(b'1')
            self.assertEqual(self.lib.selected(),0 if returned==0 else 77)
            self.assertEqual(self.lib.count(),1);self.assertEqual(self.lib.call_count(),1)
            self.assertEqual(self.lib.text(),f'K230_INIT_EXEC_RETURN_V1 ret={returned}\n'.encode())
            self.assertEqual(self.lib.error_count(),returned!=0)
    def test_no_selected_ramdisk_no_generic_fallback_record(self):
        self.lib.reset(0,0);self.lib.setup(b'1');self.assertEqual(self.lib.selected(),77)
        self.assertEqual(self.lib.count(),0);self.assertEqual(self.lib.call_count(),0)
    def test_regular_flag_lifetime_and_only_setup_freed(self):
        self.assertIn('static bool k230_init_exec_return_enabled;',self.additions)
        self.assertNotIn('__initdata',self.additions)
        self.assertIn('static int __init k230_init_exec_return_setup',self.additions)
        self.assertNotIn('nbcon',self.additions);self.assertNotIn('sbi_',self.additions)
        self.assertEqual(self.additions.count('pr_info('),1)
        if SOURCE.exists():
            source=SOURCE.read_text();self.assertEqual(hashlib.sha256(source.encode()).hexdigest(),t.INIT_EXEC_RETURN_MAIN_SHA256)
            self.assertLess(source.index('free_initmem();'),source.index('if (k230_init_exec_return_enabled)'))


class Controller(unittest.TestCase):
    def test_sole_gate_default_modes_and_safe_literal(self):
        old=t.ordinary_bootargs(d.ORIGINAL,d.SYSTEM,wait_initramfs_in_initcall=True,without_boot_markers=True)
        self.assertEqual(selected(),old+' '+t.INIT_EXEC_RETURN_FLAG)
        p=prepared();self.assertEqual(t.volatile_bootargs_command(p),'setenv bootargs "'+selected().removeprefix('bootargs=')+'"')
        for token in ('k230.init_exec_return=0','rd.k230.init-exec-return=1','k230.init_exec_return','rd.systemd.log-level=info','rd.debug','nohlt','k230.uart_progress=1'):
            with self.assertRaises(ValueError):selected(d.ORIGINAL.rstrip()+' '+token+'\n')
        for value in (None,0,1,'false'):
            with self.assertRaises(ValueError):t.diagnostic_controls(True,without_boot_markers=True,init_exec_return=value)
        for kw in ({'wait_initramfs_in_initcall':False},{'without_boot_markers':False},{'initrd_debug_logging':True},{'initrd_info_logging':True},{'initrd_info_kmsg_logging':True}):
            with self.assertRaises(ValueError):t.diagnostic_controls(**(dict(wait_initramfs_in_initcall=True,without_boot_markers=True,init_exec_return=True)|kw))
    def test_types_phases_conflicts_reject_before_output_prepare_UART(self):
        base=dict(phase='begin',wait_initramfs_in_initcall=True,without_boot_markers=True,init_exec_return=True)
        for change in ({'phase':'finish'},{'phase':'touch'},{'init_exec_return':1},{'initrd_debug_logging':True},{'without_boot_markers':False}):
            with mock.patch.object(t,'prepare')as prepare,mock.patch.object(t.rd,'safe_log_path')as output,mock.patch.object(t.rd,'PrivateSession')as uart:
                with self.assertRaises(ValueError):t.run(SimpleNamespace(**(base|change)))
                prepare.assert_not_called();output.assert_not_called();uart.assert_not_called()
    def test_exact_integer_timestamp_CRLF_and_corruption(self):
        for value in (0,-2,-2147483648,2147483647):
            for ending in (b'\n',b'\r\n'):
                self.assertEqual(t.init_exec_return_record(b'[    5.123456] K230_INIT_EXEC_RETURN_V1 ret='+str(value).encode()+ending),value)
        for line in (b'K230_INIT_EXEC_RETURN_V1 ret=0\n',b'[5.123] K230_INIT_EXEC_RETURN_V1 ret=0\n',b'[5.123456] K230_INIT_EXEC_RETURN_V1 ret=+0\n',b'[5.123456] K230_INIT_EXEC_RETURN_V1 ret=00\n',b'[5.123456] K230_INIT_EXEC_RETURN_V1 ret=-0\n',b'[5.123456] K230_INIT_EXEC_RETURN_V1 ret=2147483648\n',b'[5.123456] K230_INIT_EXEC_RETURN_V1 re\rt=0\n',b'[5.123456] K230_INIT_EXEC_RETURN_V1 ret=0'):
            self.assertIsNone(t.init_exec_return_record(line))
    def test_real_split_pump_fresh_record_is_fact_without_readiness_or_input(self):
        p=prepared();wire=phase(p)+b'[    5.000000] K230_INIT_EXEC_RETURN_V1 ret=0\n'
        session=Pump([wire[:20],wire[20:100],wire[100:-3],wire[-3:]])
        self.assertFalse(t.wait_init_exec_candidate(session,p,timeout=10,clock=session.clock))
        self.assertEqual(p['init_exec_return_observation']['records'],[{'ret':0,'exec_setup_succeeded':True}])
        self.assertFalse(p['init_exec_return_observation']['primary_prompt']);self.assertEqual(session.writes,[])
    def test_valid_prompt_same_chunk_qualifies_only_exact_received_args(self):
        p=prepared();session=Pump([phase(p)+b'[    5.000000] K230_INIT_EXEC_RETURN_V1 ret=0\nnixos login: \nroot@nixos:~# '])
        self.assertTrue(t.wait_init_exec_candidate(session,p,timeout=10,clock=session.clock));self.assertEqual(session.writes,[])
    def test_stale_duplicate_truncated_echo_bad_args_unqualified_no_input(self):
        marker=b'[    5.000000] K230_INIT_EXEC_RETURN_V1 ret=0\n'
        p=prepared()
        cases=[marker+phase(p),phase(p)+marker+marker,phase(p)+marker[:-1],phase(p)+b'echo '+marker,
               phase(p).replace(b'k230.init_exec_return=1',b'k230.init_exec_return=0')+marker,
               phase(p)+b'[    5.000000] Kernel command line: bad\n'+marker,
               phase(p).replace(b'Kernel command line:',b'Kernel command line: bad')+marker,
               phase(p).replace(b'[    4.000000] Run /init as init process\n',b'')+marker]
        for wire in cases:
            q=prepared();session=Pump([wire]);self.assertFalse(t.wait_init_exec_candidate(session,q,timeout=10,clock=session.clock));self.assertEqual(session.writes,[])
    def test_same_p2_rejected_before_transport_or_UART(self):
        p=prepared()
        with mock.patch.object(t.rd,'inspect_uart_progress_kernel',return_value={'kernel':'/missing','derivation':'/nix/store/'+'a'*32+'-kernel.drv'}),mock.patch.object(t.subprocess,'check_output',return_value='{}'):
            with self.assertRaises(ValueError):t.inspect_init_exec_kernel(p)
    @unittest.skipUnless(Path('/nix/store/yk44vx3ny4h6a9mx3ya4rczh7akhyjbj-nixos-system-nixos-26.11.20260919.20b1ddd').exists(), 'actual p2 artifacts absent on this host')
    def test_actual_p2_kernel_is_rejected_without_build_or_UART(self):
        with self.assertRaisesRegex(ValueError,'not the reviewed exec-return variant'):
            t.inspect_init_exec_kernel({'system':'/nix/store/yk44vx3ny4h6a9mx3ya4rczh7akhyjbj-nixos-system-nixos-26.11.20260919.20b1ddd'})

    def test_unknown_full_transport_no_candidate_writes_result_keeps_observation(self):
        p=prepared();Session=f.session_for(p)
        with tempfile.TemporaryDirectory()as name:
            root=Path(name);root.chmod(0o700);args=f.args_at(root,initrd_info_kmsg_logging=False,init_exec_return=True)
            def capture(session,p):p['init_exec_return_observation']={'records':[{'ret':0}],'errors':[]};return False
            with mock.patch.dict(__import__('sys').modules,{'serial':SimpleNamespace()}),mock.patch.object(t,'prepare',return_value=p),mock.patch.object(t.rd,'PrivateSession',Session),mock.patch.object(t.rd,'LOCK_PATH',root/'lock'),mock.patch.object(t,'wait_init_exec_candidate',side_effect=capture),mock.patch('sys.stderr'):
                self.assertFalse(t.run(args))
            self.assertEqual(Session.instances[-1].writes[-1],b'bootm 0x8000000 0x9000000 0x8400000\r')
            import json
            result=json.loads(args.result.read_text());self.assertEqual(result['init_exec_return_observation']['records'],[{'ret':0}]);self.assertIsNone(result['normal_recovery'])
    def test_saved_resume_selection_old_false_and_bad_state_preopen(self):
        import json,sys
        p=prepared();facts=f.f.facts();facts['bootargs']['cmdline']=p['bootargs'].removeprefix('bootargs=')
        with tempfile.TemporaryDirectory()as name:
            root=Path(name);root.chmod(0o700);args=f.args_at(root,initrd_info_kmsg_logging=False,init_exec_return=True)
            Session=f.session_for(p);f.f.FlowSession.values=facts;f.f.FlowSession.fail_stage=None
            try:
                with mock.patch.dict(sys.modules,{'serial':SimpleNamespace()}),mock.patch.object(t,'prepare',return_value=p)as prepare,mock.patch.object(t.rd,'PrivateSession',Session),mock.patch.object(t.rd,'LOCK_PATH',root/'lock'),mock.patch.object(t,'wait_init_exec_candidate',side_effect=lambda session,p:t.wait_candidate(session)):
                    self.assertTrue(t.run(args));state=json.loads(args.state.read_text());self.assertTrue(state['init_exec_return'])
                    args.phase='finish';args.init_exec_return=False;args.log=root/'finish.log';args.result=root/'finish.result'
                    self.assertTrue(t.run(args));self.assertTrue(prepare.call_args.kwargs['init_exec_return'])
                    self.assertTrue(json.loads(args.result.read_text())['init_exec_return'])
            finally:f.f.FlowSession.values=None
            state.pop('init_exec_return');args.state.write_text(json.dumps(state))
            with mock.patch.object(t,'prepare',side_effect=ValueError('fixture'))as prepare:
                with self.assertRaises(ValueError):t.run(args)
            self.assertNotIn('init_exec_return',prepare.call_args.kwargs)
            for value in ('false',0,1,None):
                args.state.write_text(json.dumps(state|{'init_exec_return':value}))
                with mock.patch.object(t,'prepare')as prepare,mock.patch.object(t.rd,'safe_log_path')as output:
                    with self.assertRaises(ValueError):t.run(args)
                    prepare.assert_not_called();output.assert_not_called()

    def test_unaffected_core_functions_AST_identical(self):
        original=subprocess.check_output(['git','show','8557a214:tools/mainline-drm-system-trial.py'],cwd=ROOT,text=True)
        defs=lambda s:{x.name:ast.dump(x,include_attributes=False)for x in ast.parse(s).body if isinstance(x,ast.FunctionDef)}
        old,new=defs(original),defs(Path(t.__file__).read_text())
        changed={'diagnostic_controls','ordinary_bootargs','prepare','volatile_bootargs_command','boot','run','main'}
        for name in old.keys()-changed:self.assertEqual(old[name],new[name],name)


if __name__=='__main__':unittest.main()
