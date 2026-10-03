"""Native execution of actual direct-SBI helper; no firmware/kernel/board run."""
import ctypes
from pathlib import Path
import subprocess
import tempfile
import unittest

PATCH = Path(__file__).resolve().parents[1] / "nix/patches/mainline/k230-boot-trace-sbi.patch"
POINTS = ("initcalls-before", "initcalls-after", "basic-before", "basic-after")


class BootTraceSbi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patch = PATCH.read_text()
        added = "\n".join(line[1:] for line in cls.patch.splitlines()
                          if line.startswith("+") and not line.startswith("+++"))
        start = added.index("/* Single-attempt SBI output;")
        end = added.index("} while (0)", start) + len("} while (0)")
        cls.helper = added[start:end] + "\n"
        cls.temp = tempfile.TemporaryDirectory()
        directory = Path(cls.temp.name)
        prefix = r'''
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#define __init
#define __aligned(n) __attribute__((aligned(n)))
#define __setup(key, fn) static const char *setup_key = key
#define BUILD_BUG_ON(x) _Static_assert(!(x), "buffer bound")
static bool k230_boot_trace_enabled, sbi_debug_console_available;
static int calls, result;
static unsigned int last_len;
static char wire[65];
int sbi_debug_console_write(const char *data, unsigned int len) {
    calls++; last_len = len;
    memcpy(wire, data, len); wire[len] = 0;
    return result;
}
'''
        suffix = r'''
static const char *records[] = {
    k230_sbi_initcalls_before, k230_sbi_initcalls_after,
    k230_sbi_basic_before, k230_sbi_basic_after,
};
void reset(void) {
    k230_boot_trace_enabled = false; k230_boot_trace_sbi_enabled = false;
    sbi_debug_console_available = false; calls = 0; result = 0;
    last_len = 0; wire[0] = 0;
}
void gates(int base, int available) {
    k230_boot_trace_enabled = base; sbi_debug_console_available = available;
}
int setup(char *s) { return k230_boot_trace_sbi_setup(s); }
int parse(char *s) {
    size_t n = strlen(setup_key);
    return strncmp(s, setup_key, n) ? 0 : k230_boot_trace_sbi_setup(s + n);
}
void mock_return(int ret) { result = ret; }
int mark(int index) {
    return k230_boot_trace_sbi_mark(records[index], strlen(records[index]));
}
int mark_length(unsigned int len) {
    return k230_boot_trace_sbi_mark(records[0], len);
}
void all_points(void) {
    K230_BOOT_SBI_MARK(k230_sbi_initcalls_before);
    K230_BOOT_SBI_MARK(k230_sbi_initcalls_after);
    K230_BOOT_SBI_MARK(k230_sbi_basic_before);
    K230_BOOT_SBI_MARK(k230_sbi_basic_after);
}
int call_count(void) { return calls; }
unsigned int length(void) { return last_len; }
const char *output(void) { return wire; }
const char *record(int index) { return records[index]; }
uintptr_t address(int index) { return (uintptr_t)records[index]; }
'''
        cls.libs = []
        for config in (True, False):
            source = directory / f"helper-{config}.c"
            output = directory / f"helper-{config}.so"
            source.write_text(("#define CONFIG_RISCV_SBI 1\n" if config else "")
                              + prefix + cls.helper + suffix)
            subprocess.run(["gcc", "-std=gnu11", "-Wall", "-Wextra", "-Werror",
                            "-shared", "-fPIC", str(source), "-o", str(output)],
                           check=True, capture_output=True)
            lib = ctypes.CDLL(str(output))
            lib.setup.argtypes = lib.parse.argtypes = [ctypes.c_char_p]
            lib.output.restype = lib.record.restype = ctypes.c_char_p
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

    def test_both_runtime_flags_required(self):
        self.lib.gates(1, 1)
        self.assertEqual(self.lib.mark(0), 0)
        self.lib.setup(b"1")
        self.lib.gates(0, 1)
        self.assertEqual(self.lib.mark(0), 0)
        self.assertEqual(self.lib.call_count(), 0)

    def test_invalid_bare_empty_flags_do_not_enable(self):
        for argument in (b"k230.boot_trace_sbi", b"k230.boot_trace_sbi=",
                         b"k230.boot_trace_sbi=0", b"k230.boot_trace_sbi=true",
                         b"k230.boot_trace_sbi=01", b"k230.boot_trace_sbi=1x"):
            with self.subTest(argument=argument):
                self.lib.reset(); self.lib.gates(1, 1)
                self.assertEqual(self.lib.parse(argument), 0)
                self.assertEqual(self.lib.mark(0), 0)
                self.assertEqual(self.lib.call_count(), 0)
        self.assertEqual(self.lib.parse(b"k230.boot_trace_sbi=1"), 1)

    def test_unavailable_extension_has_no_call(self):
        self.enable(); self.lib.gates(1, 0)
        self.assertEqual(self.lib.mark(0), 0)
        self.assertEqual(self.lib.call_count(), 0)

    def test_without_config_sbi_has_no_call(self):
        lib = self.libs[1]; self.enable(lib)
        self.assertEqual(lib.mark(0), 0)
        self.assertEqual(lib.call_count(), 0)

    def test_full_return_is_one_call_with_exact_public_bytes(self):
        self.enable()
        for index, point in enumerate(POINTS):
            record = f"\r\nK230_BOOT_SBI_V1 point={point}\r\n".encode()
            self.lib.mock_return(len(record))
            self.assertEqual(self.lib.mark(index), 1)
            self.assertEqual(self.lib.call_count(), index + 1)
            self.assertEqual(self.lib.length(), len(record))
            self.assertEqual(self.lib.output(), record)

    def test_partial_zero_error_or_oversize_return_never_retries(self):
        for result in (1, 0, -5, -95, 999):
            with self.subTest(result=result):
                self.lib.reset(); self.enable()
                self.lib.mock_return(result)
                self.assertEqual(self.lib.mark(0), 0)
                self.assertEqual(self.lib.call_count(), 1)

    def test_invalid_lengths_fail_before_call(self):
        self.enable()
        for length in (0, 65, 2**32-1):
            self.assertEqual(self.lib.mark_length(length), 0)
        self.assertEqual(self.lib.call_count(), 0)

    def test_four_points_still_only_four_attempts_on_zero_progress(self):
        self.enable(); self.lib.mock_return(0)
        self.lib.all_points()
        self.assertEqual(self.lib.call_count(), 4)

    def test_buffers_are_bounded_aligned_and_page_contained(self):
        for index in range(4):
            record = self.lib.record(index)
            address = self.lib.address(index)
            self.assertLessEqual(len(record) + 1, 64)
            self.assertEqual(address % 64, 0)
            self.assertLessEqual(address % 4096 + len(record), 4096)
            self.assertTrue(record.startswith(b"\r\nK230_BOOT_SBI_V1 "))
            self.assertTrue(record.endswith(b"\r\n"))

    def test_only_four_outer_sites_and_no_polling_fallback(self):
        self.assertEqual(self.patch.count("+\tK230_BOOT_SBI_MARK("), 4)
        self.assertEqual(self.helper.count("sbi_debug_console_write("), 1)
        self.assertNotIn("pr_info", self.helper)
        self.assertNotIn("nbcon_cpu", self.helper)
        self.assertNotIn("for (", self.helper)
        self.assertNotIn("while (", self.helper.replace("} while (0)", ""))
        self.assertNotIn("__initdata", self.helper)
        self.assertNotIn("__initconst", self.helper)
        self.assertNotIn("__init k230_boot_trace_sbi_mark", self.helper)


if __name__ == "__main__":
    unittest.main()
