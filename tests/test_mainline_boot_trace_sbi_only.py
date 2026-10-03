"""Native execution of the actual layered helper; no kernel/firmware/board run."""
import ctypes
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "nix/patches/mainline/k230-boot-trace-sbi-only.patch"
PAIRS = ("basic-setup", "initcalls", "initramfs-wait", "root-console", "init-access",
         "namespace", "integrity-keys", "async-wait", "initmem-readonly", "init-exec")
STEPS = tuple(f"{pair}-{side}" for pair in PAIRS for side in ("enter", "exit"))


def additions(patch):
    return "\n".join(line[1:] for line in patch.splitlines()
                     if line.startswith("+") and not line.startswith("+++"))


class BootTraceSbiOnly(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        original = additions((ROOT / "nix/patches/mainline/k230-boot-trace.patch").read_text())
        start = original.index("/* Optional K230 boot diagnosis.")
        end = original.index("\n}\n", original.index("static void k230_boot_trace_mark")) + 3
        original = original[start:end]
        cls.patch = PATCH.read_text()
        added = additions(cls.patch)
        start = added.index("/* Fixed single-attempt records;")
        end = added.index("\n};", added.index("k230_boot_sbi_records[]")) + 4
        definitions = added[start:end] + "\n"
        branch = added[end:].strip("\n") + "\n\n"
        cls.helper = original.replace("static void k230_boot_trace_mark",
                                      definitions + "static void k230_boot_trace_mark", 1)
        cls.helper = cls.helper.replace("\t/* Never keep emergency state", branch + "\t/* Never keep emergency state", 1)
        cls.temp = tempfile.TemporaryDirectory()
        directory = Path(cls.temp.name)
        prefix = r'''
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#define __init
#define __aligned(n) __attribute__((aligned(n)))
#define __setup(key, fn) static const char *setup_key_##fn = key
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
static bool sbi_debug_console_available;
static int calls, result, enters, exits, nesting, bad;
static size_t used, legacy_used;
static char requested[4096], legacy[4096];
static void nbcon_cpu_emergency_enter(void) { if (nesting++) bad++; enters++; }
static void nbcon_cpu_emergency_exit(void) { if (--nesting) bad++; exits++; }
static void report(const char *fmt, ...) {
    va_list args; if (nesting != 1) bad++;
    va_start(args, fmt);
    int n = vsnprintf(legacy + legacy_used, sizeof(legacy) - legacy_used, fmt, args);
    va_end(args);
    if (n < 0 || (size_t)n >= sizeof(legacy) - legacy_used) bad++;
    else legacy_used += n;
}
#define pr_info report
int sbi_debug_console_write(const char *data, unsigned int len) {
    if (nesting || !len || len >= 64 || ((uintptr_t)data % 64)) bad++;
    calls++;
    if (used + len >= sizeof(requested)) bad++;
    else { memcpy(requested + used, data, len); used += len; requested[used] = 0; }
    return result;
}
'''
        suffix = r'''
void reset(void) {
    k230_boot_trace_enabled = k230_boot_trace_sbi_only_enabled = false;
    sbi_debug_console_available = false; k230_boot_trace_seq = 0;
    calls = enters = exits = nesting = bad = result = 0;
    used = legacy_used = 0; requested[0] = legacy[0] = 0;
}
void gates(int base, int available) {
    k230_boot_trace_enabled = base; sbi_debug_console_available = available;
}
int setup(char *s) { return k230_boot_trace_sbi_only_setup(s); }
int parse(char *s) {
    size_t n = strlen(setup_key_k230_boot_trace_sbi_only_setup);
    return strncmp(s, setup_key_k230_boot_trace_sbi_only_setup, n) ? 0 : setup(s + n);
}
int base_setup(char *s) { (void)setup_key_k230_boot_trace_setup; return k230_boot_trace_setup(s); }
void mock_return(int ret) { result = ret; }
void mark(char *s) { k230_boot_trace_mark(s); }
const char *requests(void) { return requested; }
const char *prints(void) { return legacy; }
int call_count(void) { return calls; }
int enter_count(void) { return enters; }
unsigned int sequence(void) { return k230_boot_trace_seq; }
int health(void) { return bad || nesting || enters != exits; }
const char *step(unsigned int i) { return k230_boot_sbi_records[i].step; }
const char *record(unsigned int i) { return k230_boot_sbi_records[i].record; }
uintptr_t address(unsigned int i) { return (uintptr_t)k230_boot_sbi_records[i].record; }
'''
        cls.libs = []
        for config in (True, False):
            source, output = directory / f"helper-{config}.c", directory / f"helper-{config}.so"
            source.write_text(("#define CONFIG_RISCV_SBI 1\n" if config else "") + prefix + cls.helper + suffix)
            subprocess.run(["gcc", "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-shared", "-fPIC",
                            str(source), "-o", str(output)], check=True, capture_output=True)
            lib = ctypes.CDLL(str(output))
            for name in ("setup", "parse", "base_setup", "mark"):
                getattr(lib, name).argtypes = [ctypes.c_char_p]
            for name in ("requests", "prints", "step", "record"):
                getattr(lib, name).restype = ctypes.c_char_p
            lib.address.restype = ctypes.c_size_t
            cls.libs.append(lib)
        cls.lib = cls.libs[0]

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        for lib in self.libs:
            lib.reset()

    def enable(self, lib=None):
        lib = lib or self.lib
        lib.gates(1, 1)
        self.assertEqual(lib.setup(b"1"), 1)

    def test_absent_new_flag_preserves_original_helper_and_cap(self):
        self.lib.gates(1, 1)
        for _ in range(100): self.lib.mark(b"init-exec-enter")
        self.assertEqual(self.lib.call_count(), 0)
        self.assertEqual(self.lib.enter_count(), 32)
        self.assertEqual(self.lib.sequence(), 32)
        self.assertEqual(len(self.lib.prints().splitlines()), 32)
        self.assertTrue(self.lib.prints().startswith(b"K230_BOOT_TRACE_V1 seq=1 step=init-exec-enter\n"))
        self.assertEqual(self.lib.health(), 0)

    def test_invalid_bare_empty_new_flags_preserve_original_output(self):
        for arg in (b"k230.boot_trace_sbi_only", b"k230.boot_trace_sbi_only=",
                    b"k230.boot_trace_sbi_only=0", b"k230.boot_trace_sbi_only=true",
                    b"k230.boot_trace_sbi_only=01", b"k230.boot_trace_sbi_only=1x"):
            with self.subTest(arg=arg):
                self.lib.reset(); self.lib.gates(1, 1)
                self.assertEqual(self.lib.parse(arg), 0)
                self.lib.mark(b"basic-setup-enter")
                self.assertEqual(self.lib.call_count(), 0)
                self.assertEqual(self.lib.enter_count(), 1)
                self.assertEqual(self.lib.prints(), b"K230_BOOT_TRACE_V1 seq=1 step=basic-setup-enter\n")
        self.assertEqual(self.lib.parse(b"k230.boot_trace_sbi_only=1"), 1)

    def test_runtime_base_flag_required(self):
        self.enable(); self.lib.gates(0, 1)
        self.lib.mark(b"basic-setup-enter")
        self.assertEqual(self.lib.call_count(), 0)
        self.assertEqual(self.lib.enter_count(), 0)
        self.assertEqual(self.lib.prints(), b"")

    def test_unavailable_extension_no_attempt_or_fallback(self):
        self.enable(); self.lib.gates(1, 0)
        self.lib.mark(b"basic-setup-enter")
        self.assertEqual(self.lib.call_count(), 0)
        self.assertEqual(self.lib.enter_count(), 0)
        self.assertEqual(self.lib.sequence(), 0)
        self.assertEqual(self.lib.prints(), b"")

    def test_config_disabled_no_attempt_or_fallback(self):
        lib = self.libs[1]; self.enable(lib)
        lib.mark(b"basic-setup-enter")
        self.assertEqual(lib.call_count(), 0)
        self.assertEqual(lib.enter_count(), 0)
        self.assertEqual(lib.prints(), b"")

    def test_all_twenty_exact_points_use_sbi_without_printk_or_emergency(self):
        self.enable(); expected = b""
        for step in STEPS:
            message = f"\r\nK230_BOOT_SBI_ONLY_V1 step={step}\r\n".encode()
            self.lib.mock_return(len(message)); self.lib.mark(step.encode())
            expected += message
        self.assertEqual(self.lib.requests(), expected)
        self.assertEqual(self.lib.call_count(), 20)
        self.assertEqual(self.lib.sequence(), 20)
        self.assertEqual(self.lib.enter_count(), 0)
        self.assertEqual(self.lib.prints(), b"")
        self.assertEqual(self.lib.health(), 0)

    def test_partial_zero_error_and_full_are_one_attempt_with_no_fallback(self):
        length = len(b"\r\nK230_BOOT_SBI_ONLY_V1 step=basic-setup-enter\r\n")
        for ret in (length, 1, 0, -5, -95):
            with self.subTest(ret=ret):
                self.lib.reset(); self.enable(); self.lib.mock_return(ret)
                self.lib.mark(b"basic-setup-enter")
                self.assertEqual(self.lib.call_count(), 1)
                self.assertEqual(self.lib.sequence(), 1)
                self.assertEqual(self.lib.enter_count(), 0)
                self.assertEqual(self.lib.prints(), b"")
                self.assertEqual(self.lib.health(), 0)

    def test_32_attempt_cap_includes_zero_progress_exec_fallbacks(self):
        self.enable(); self.lib.mock_return(0)
        for _ in range(100): self.lib.mark(b"init-exec-enter")
        self.assertEqual(self.lib.call_count(), 32)
        self.assertEqual(self.lib.sequence(), 32)
        self.assertEqual(self.lib.enter_count(), 0)
        self.assertEqual(self.lib.health(), 0)

    def test_null_or_unknown_step_is_safe_and_does_not_consume_attempt(self):
        self.enable()
        for step in (None, b"", b"private-unknown", b"init-exec-enter-extra"):
            self.lib.mark(step)
        self.assertEqual(self.lib.call_count(), 0)
        self.assertEqual(self.lib.sequence(), 0)
        self.assertEqual(self.lib.prints(), b"")

    def test_every_record_has_exact_label_alignment_and_page_bound(self):
        for i, step in enumerate(STEPS):
            self.assertEqual(self.lib.step(i), step.encode())
            record = self.lib.record(i)
            self.assertEqual(record, f"\r\nK230_BOOT_SBI_ONLY_V1 step={step}\r\n".encode())
            self.assertLess(len(record), 64)
            address = self.lib.address(i)
            self.assertEqual(address % 64, 0)
            self.assertLessEqual(address % 4096 + len(record), 4096)

    def test_patch_only_adds_mode_and_preserves_fixed_call_sites(self):
        self.assertEqual(self.patch.count("sbi_debug_console_write("), 1)
        self.assertNotIn("snprintf", self.helper)
        self.assertNotIn("__initdata", self.helper)
        self.assertNotIn("__initconst", self.helper)
        self.assertNotIn("__init k230_boot_trace_mark", self.helper)
        self.assertNotIn("+\tk230_boot_trace_mark(", self.patch)
        self.assertNotIn("while (", self.helper)


if __name__ == "__main__":
    unittest.main()
