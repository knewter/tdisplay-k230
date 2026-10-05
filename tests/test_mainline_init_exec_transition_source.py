"""Execute the patched selected caller and both RISC-V witness sites on host."""
import ctypes
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PARENT = Path('/nix/store/dsgrv7744lzh418z22gb865c0j09g1qs-linux-mainline-k230-init-exec-return-src')
PATCH = ROOT / 'nix/patches/mainline/k230-init-exec-transition.patch'


# Exact parent excerpts at their original line numbers; fixtures are not full source proof.
PARENT_EXCERPTS = {'init/main.c': [(28, '#include <linux/init.h>\n'),
                 (174,
                  '/* Read after free_initmem: keep this runtime gate in ordinary storage. */\n'
                  'static bool k230_init_exec_return_enabled;\n'
                  '\n'
                  'static int __init k230_init_exec_return_setup(char *value)\n'
                  '{\n'
                  '\tk230_init_exec_return_enabled = !strcmp(value, "1");\n'
                  '\treturn 1;\n'
                  '}\n'
                  '__setup("k230.init_exec_return=", k230_init_exec_return_setup);\n'
                  '\n'),
                 (1663, 'static int __ref kernel_init(void *unused)\n{\n'),
                 (1703,
                  '\tif (ramdisk_execute_command) {\n'
                  '\t\tret = run_init_process(ramdisk_execute_command);\n'
                  '\t\tif (k230_init_exec_return_enabled)\n'
                  '\t\t\tpr_info("K230_INIT_EXEC_RETURN_V1 ret=%d\\n", ret);\n'
                  '\t\tif (!ret)\n'
                  '\t\t\treturn 0;\n'
                  '\t\tpr_err("Failed to execute %s (error %d)\\n",\n'
                  '\t\t       ramdisk_execute_command, ret);\n'
                  '\t}\n'
                  '\n'
                  '\t/*\n'
                  '\t * We try each of these until one succeeds.\n'
                  '\t *\n'
                  '\t * The Bourne shell can be used instead of init if we are\n'
                  '\t * trying to recover a really broken machine.\n'
                  '\t */\n'
                  '\tif (execute_command) {\n'
                  '\t\tret = run_init_process(execute_command);\n')],
 'arch/riscv/kernel/process.c': [(20, '#include <linux/entry-common.h>\n'),
                                 (228,
                                  'asmlinkage void ret_from_fork_kernel(void *fn_arg, int '
                                  '(*fn)(void *), struct pt_regs *regs)\n'
                                  '{\n'
                                  '\tfn(fn_arg);\n'
                                  '\n'
                                  '\tsyscall_exit_to_user_mode(regs);\n'
                                  '}\n')],
 'arch/riscv/kernel/traps.c': [(23, '#include <linux/entry-common.h>\n'),
                               (326,
                                'asmlinkage __visible __trap_section  __no_stack_protector\n'
                                'void do_trap_ecall_u(struct pt_regs *regs)\n'
                                '{\n'
                                '\tif (user_mode(regs)) {\n'
                                '\t\tlong syscall = regs->a7;\n'
                                '\n'
                                '\t\tregs->epc += 4;\n'
                                '\t\tregs->orig_a0 = regs->a0;\n'
                                '\t\tregs->a0 = -ENOSYS;\n'
                                '\n'
                                '\t\triscv_v_vstate_discard(regs);\n'
                                '\n'
                                '\t\tif '
                                '(likely(syscall_enter_from_user_mode_randomize_stack(regs, '
                                '&syscall))) {\n'
                                '\t\t\tif (syscall >= 0 && syscall < NR_syscalls) {\n'
                                '\t\t\t\tsyscall = array_index_nospec(syscall, NR_syscalls);\n'
                                '\t\t\t\tsyscall_handler(regs, syscall);\n'
                                '\t\t\t}\n'
                                '\t\t}\n'
                                '\t\tsyscall_exit_to_user_mode(regs);\n'
                                '\t} else {\n'
                                '\t\tirqentry_state_t state = irqentry_nmi_enter(regs);\n'
                                '\n'
                                '\t\tdo_trap_error(regs, SIGILL, ILL_ILLTRP, regs->epc,\n'
                                '\t\t\t"Oops - environment call from U-mode");\n'
                                '\n'
                                '\t\tirqentry_nmi_exit(regs, state);\n'
                                '\t}\n'
                                '\n'
                                '}\n'
                                '\n')]}

def parent_fixture(name):
    lines = []
    for first, text in PARENT_EXCERPTS[name]:
        lines.extend(["\n"] * (first - 1 - len(lines)))
        lines.extend(text.splitlines(True))
    return "".join(lines)


def function(text, name):
    start = text.index(name + '(')
    start = text.rfind('\n', 0, start) + 1
    opening = text.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


class Source(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='k230-transition-source-', dir=Path.home()/'tmp')
        cls.root = Path(cls.tmp.name)
        cls.actual_parent = PARENT.exists() and not os.environ.get('K230_TRANSITION_FORCE_FIXTURE')
        paths = ['init/main.c', 'arch/riscv/kernel/process.c', 'arch/riscv/kernel/traps.c']
        for name in paths:
            target = cls.root/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text((PARENT/name).read_text() if cls.actual_parent else parent_fixture(name))
        (cls.root/'include/linux').mkdir(parents=True)
        subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(PATCH)], cwd=cls.root, check=True, capture_output=True)
        cls.main = (cls.root/'init/main.c').read_text()
        cls.process = (cls.root/'arch/riscv/kernel/process.c').read_text()
        cls.traps = (cls.root/'arch/riscv/kernel/traps.c').read_text()
        defs = cls.main[cls.main.index('static bool k230_init_exec_return_enabled;'):cls.main.index(function(cls.main, 'k230_init_exec_transition_user_ecall')) + len(function(cls.main, 'k230_init_exec_transition_user_ecall'))]
        # Exact selected ramdisk branch; original errors/return are retained.
        selected = cls.main[cls.main.index('\tif (ramdisk_execute_command) {', cls.main.index('static int __ref kernel_init')):]
        selected = selected[:selected.index('\n\tif (execute_command)')]
        fork = function(cls.process, 'ret_from_fork_kernel')
        ecall = function(cls.traps, 'do_trap_ecall_u')
        ecall = ecall[:ecall.index('\n\t} else {')] + '\n\t}\n}'
        preamble = r'''
#include <stdbool.h>
#include <string.h>
#include <stdio.h>
#include <stdarg.h>
#define __init
#define __setup(a,b)
#define asmlinkage
#define __visible
#define __trap_section
#define __no_stack_protector
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,v) ((x)=(v))
#define likely(x) (x)
#define ENOSYS 38
#define NR_syscalls 512
#define array_index_nospec(x,n) (x)
struct pt_regs { long a7, epc, orig_a0, a0; };
static int current, pid1, enter_ok, user, result, errors, exits, dispatches, outputs, active_output;
static char records[4][128];
static int is_global_init(int task) { return pid1; }
static int pr_info(const char *format, ...) {
    va_list args;
    if (active_output) { fprintf(stderr,"recursive output\n"); return -1; }
    active_output=1;
    va_start(args,format); vsnprintf(records[outputs++],128,format,args); va_end(args);
    /* Re-entry cannot retry a point consumed before this output. */
    if (strstr(format,"kernel-init-return")) k230_init_exec_transition_kernel_return();
    if (strstr(format,"first-user-ecall")) k230_init_exec_transition_user_ecall();
    active_output=0;
    return -1;
}
#define pr_err(...) (++errors)
static int run_init_process(const char *name) { return result; }
static void syscall_exit_to_user_mode(struct pt_regs *regs) { ++exits; }
static int user_mode(struct pt_regs *regs) { return user; }
static void riscv_v_vstate_discard(struct pt_regs *regs) {}
static int syscall_enter_from_user_mode_randomize_stack(struct pt_regs *regs,long *nr) { return enter_ok; }
static void syscall_handler(struct pt_regs *regs,long nr) { ++dispatches; }
'''
        prototypes = (cls.root/'include/linux/k230-init-exec-transition.h').read_text()
        harness = prototypes + preamble + defs + '\nint selected(void) { const char *ramdisk_execute_command="/init"; int ret;\n' + selected + '\nreturn 99; }\n' + fork + '\n' + ecall + r'''
static int selected_fn(void *arg) { return selected(); }
void reset(const char *parent,const char *child,int global,int ret) {
    k230_init_exec_return_setup((char*)parent); k230_init_exec_transition_setup((char*)child);
    k230_init_exec_transition_armed=false; k230_init_exec_transition_return_consumed=false;
    k230_init_exec_transition_ecall_consumed=false; pid1=global; result=ret; user=enter_ok=1;
    errors=exits=dispatches=outputs=active_output=0; memset(records,0,sizeof(records));
}
void fork_once(void) { struct pt_regs regs={0}; ret_from_fork_kernel(NULL,selected_fn,&regs); }
void ecall_once(int enabled,int userspace,long number) {
    struct pt_regs regs={.a7=number}; enter_ok=enabled; user=userspace; do_trap_ecall_u(&regs);
}
int count(void) { return outputs; }
int dispatched(void) { return dispatches; }
int exited(void) { return exits; }
int failed(void) { return errors; }
const char *record(int index) { return records[index]; }
'''
        native = cls.root/'native.c'; native.write_text(harness)
        lib = cls.root/'native.so'
        compile_result=subprocess.run(['cc','-shared','-fPIC','-Werror','-o',str(lib),str(native)],capture_output=True,text=True)
        if compile_result.returncode: raise RuntimeError(compile_result.stderr)
        cls.c = ctypes.CDLL(str(lib))
        cls.c.reset.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int,ctypes.c_int]
        cls.c.record.restype=ctypes.c_char_p

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def reset(self, parent=b'1', child=b'1', pid1=1, ret=0):
        self.c.reset(parent,child,pid1,ret)

    def records(self):
        return [self.c.record(i) for i in range(self.c.count())]

    def test_success_preserves_parent_and_order_and_dispatch(self):
        self.reset(); self.c.fork_once(); self.c.ecall_once(1,1,1)
        self.assertEqual(self.records(),[b'K230_INIT_EXEC_RETURN_V1 ret=0\n',b'K230_INIT_EXEC_TRANSITION_V1 point=kernel-init-return\n',b'K230_INIT_EXEC_TRANSITION_V1 point=first-user-ecall\n'])
        self.assertEqual((self.c.exited(),self.c.dispatched(),self.c.failed()),(2,1,0))

    def test_strict_both_gates(self):
        for invalid in (b'',b'0',b'01',b'1x',b'true'):
            for parent,child in ((invalid,b'1'),(b'1',invalid)):
                with self.subTest(parent=parent,child=child):
                    self.reset(parent,child); self.c.fork_once(); self.c.ecall_once(1,1,1)
                    self.assertFalse(any(b'TRANSITION' in x for x in self.records()))

    def test_non_pid1_never_arms(self):
        self.reset(pid1=0); self.c.fork_once(); self.c.ecall_once(1,1,1)
        self.assertEqual(self.records(),[b'K230_INIT_EXEC_RETURN_V1 ret=0\n'])

    def test_failed_selected_exec_preserves_error_and_no_arm(self):
        for result in (-2,1):
            self.reset(ret=result); self.c.fork_once(); self.c.ecall_once(1,1,1)
            self.assertEqual(self.records(),[f'K230_INIT_EXEC_RETURN_V1 ret={result}\n'.encode()])
            self.assertEqual(self.c.failed(),1)

    def test_one_shots_consumed_before_reentrant_failed_output(self):
        self.reset(); self.c.fork_once()
        for _ in range(3): self.c.k230_init_exec_transition_kernel_return(); self.c.ecall_once(1,1,1)
        self.assertEqual(self.c.count(),3)
        self.assertEqual(self.c.dispatched(),3)

    def test_no_arm_before_selected_caller(self):
        self.reset(); self.c.k230_init_exec_transition_kernel_return(); self.c.ecall_once(1,1,1)
        self.assertEqual(self.records(),[])

    def test_reentry_setup_and_user_mode_gate(self):
        self.reset(); self.c.fork_once(); self.c.ecall_once(0,1,1); self.c.ecall_once(1,0,1)
        self.assertEqual(self.c.count(),2); self.assertEqual(self.c.dispatched(),0)
        self.c.ecall_once(1,1,1); self.assertEqual(self.c.count(),3)

    def test_invalid_syscall_still_positive_entry_not_handler_completion(self):
        self.reset(); self.c.fork_once(); self.c.ecall_once(1,1,-1)
        self.assertEqual(self.c.count(),3); self.assertEqual(self.c.dispatched(),0)

    def test_runtime_lifetime_and_safe_placement(self):
        self.assertNotIn('__initdata',self.main[self.main.index('/* These witnesses'):self.main.index(function(self.main, 'k230_init_exec_transition_user_ecall')) + len(function(self.main, 'k230_init_exec_transition_user_ecall'))])
        self.assertLess(self.process.index('fn(fn_arg);'),self.process.index('k230_init_exec_transition_kernel_return();'))
        self.assertLess(self.process.index('k230_init_exec_transition_kernel_return();'),self.process.index('syscall_exit_to_user_mode(regs);'))
        self.assertLess(self.traps.index('k230_init_exec_transition_user_ecall();'),self.traps.index('syscall_handler(regs, syscall);'))

    def test_removing_only_additions_restores_original_sites(self):
        for path,call in [('arch/riscv/kernel/process.c','\tk230_init_exec_transition_kernel_return();\n'),('arch/riscv/kernel/traps.c','\t\t\tk230_init_exec_transition_user_ecall();\n')]:
            new=(self.root/path).read_text().replace('#include <linux/k230-init-exec-transition.h>\n','').replace(call,'')
            self.assertEqual(new,(PARENT/path).read_text() if self.actual_parent else parent_fixture(path))


if __name__ == '__main__':
    unittest.main()
