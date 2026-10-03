"""Host execution of the actual added marker helper; no kernel or board run."""
import ctypes
from pathlib import Path
import subprocess
import tempfile
import unittest


PATCH = Path(__file__).resolve().parents[1] / "nix/patches/mainline/k230-boot-trace.patch"
PAIRS = (
    "basic-setup", "initcalls", "initramfs-wait", "root-console", "init-access",
    "namespace", "integrity-keys", "async-wait", "initmem-readonly", "init-exec",
)


class BootTrace(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patch = PATCH.read_text()
        added = "\n".join(line[1:] for line in cls.patch.splitlines()
                          if line.startswith("+") and not line.startswith("+++"))
        start = added.index("/* Optional K230 boot diagnosis.")
        end = added.index("\n}\n", added.index("static void k230_boot_trace_mark")) + 3
        cls.helper = added[start:end]
        cls.temp = tempfile.TemporaryDirectory()
        directory = Path(cls.temp.name)
        prefix = r'''
#include <stdbool.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#define __init
#define __setup(key, fn) static const char *setup_key = key
static int nesting, enters, exits, bad;
static size_t used;
static char wire[4096];
static void nbcon_cpu_emergency_enter(void) { if (nesting++) bad++; enters++; }
static void nbcon_cpu_emergency_exit(void) { if (--nesting) bad++; exits++; }
static void report(const char *fmt, ...) {
    va_list args;
    if (nesting != 1) bad++;
    va_start(args, fmt);
    int n = vsnprintf(wire + used, sizeof(wire) - used, fmt, args);
    va_end(args);
    if (n < 0 || (size_t)n >= sizeof(wire) - used) bad++;
    else used += n;
}
#define pr_info report
'''
        suffix = r'''
void reset(void) {
    nesting = enters = exits = bad = 0; used = 0; wire[0] = 0;
    k230_boot_trace_enabled = false; k230_boot_trace_seq = 0;
}
int setup(char *s) { return k230_boot_trace_setup(s); }
/* Exercise the registered key prefix; the kernel's full parser is not mocked. */
int parse(char *s) {
    size_t n = strlen(setup_key);
    return strncmp(s, setup_key, n) ? 0 : k230_boot_trace_setup(s + n);
}
void mark(const char *s) { k230_boot_trace_mark(s); }
const char *output(void) { return wire; }
int health(void) { return bad || nesting || enters != exits; }
int calls(void) { return enters; }
'''
        (directory / "helper.c").write_text(prefix + cls.helper + suffix)
        subprocess.run(["gcc", "-std=gnu11", "-Wall", "-Wextra", "-Werror",
                        "-shared", "-fPIC", str(directory / "helper.c"),
                        "-o", str(directory / "helper.so")], check=True, capture_output=True)
        cls.lib = ctypes.CDLL(str(directory / "helper.so"))
        cls.lib.setup.argtypes = [ctypes.c_char_p]
        cls.lib.parse.argtypes = [ctypes.c_char_p]
        cls.lib.mark.argtypes = [ctypes.c_char_p]
        cls.lib.output.restype = ctypes.c_char_p

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.lib.reset()

    def test_disabled_has_no_output_or_emergency_side_effect(self):
        self.lib.mark(b"init-exec-enter")
        self.assertEqual(self.lib.output(), b"")
        self.assertEqual(self.lib.calls(), 0)
        self.assertEqual(self.lib.health(), 0)

    def test_only_exact_one_enables(self):
        for value in (b"", b"0", b"true", b"1x", b"01", b"1 "):
            with self.subTest(value=value):
                self.lib.reset()
                self.assertEqual(self.lib.setup(value), 0)
                self.lib.mark(b"basic-setup-enter")
                self.assertEqual(self.lib.output(), b"")
                self.assertEqual(self.lib.calls(), 0)
        self.assertEqual(self.lib.setup(b"1"), 1)
        self.lib.mark(b"basic-setup-enter")
        self.assertEqual(self.lib.output(), b"K230_BOOT_TRACE_V1 seq=1 step=basic-setup-enter\n")
        self.assertEqual(self.lib.health(), 0)

    def test_bare_or_empty_registered_flag_does_not_enable(self):
        for argument in (b"k230.boot_trace", b"k230.boot_trace=", b"k230.boot_trace=0"):
            with self.subTest(argument=argument):
                self.lib.reset()
                self.assertEqual(self.lib.parse(argument), 0)
                self.lib.mark(b"basic-setup-enter")
                self.assertEqual(self.lib.output(), b"")
                self.assertEqual(self.lib.calls(), 0)
        self.assertEqual(self.lib.parse(b"k230.boot_trace=1"), 1)
        self.lib.mark(b"basic-setup-enter")
        self.assertEqual(self.lib.calls(), 1)

    def test_each_print_briefly_enters_and_exits_emergency(self):
        self.lib.setup(b"1")
        expected = []
        for pair in PAIRS:
            for side in ("enter", "exit"):
                step = f"{pair}-{side}"
                self.lib.mark(step.encode())
                expected.append(f"K230_BOOT_TRACE_V1 seq={len(expected)+1} step={step}\n")
                # No emergency state survives a marker into bracketed work.
                self.assertEqual(self.lib.health(), 0)
        self.assertEqual(self.lib.output().decode(), "".join(expected))
        self.assertEqual(self.lib.calls(), 20)

    def test_output_is_capped_even_if_exec_fallbacks_repeat(self):
        self.lib.setup(b"1")
        for _ in range(100):
            self.lib.mark(b"init-exec-enter")
        lines = self.lib.output().splitlines()
        self.assertEqual(len(lines), 32)
        self.assertEqual(lines[-1], b"K230_BOOT_TRACE_V1 seq=32 step=init-exec-enter")
        self.assertEqual(self.lib.calls(), 32)
        self.assertEqual(self.lib.health(), 0)

    def test_only_fixed_pairs_are_inserted_into_main(self):
        import re
        sites = re.findall(r'^\+\s*k230_boot_trace_mark\("([a-z-]+)"\);$', self.patch, re.M)
        self.assertCountEqual(sites, [f"{pair}-{side}" for pair in PAIRS for side in ("enter", "exit")])
        self.assertEqual(self.patch.count("+++ b/"), 1)
        self.assertIn("+++ b/init/main.c", self.patch)

    def test_live_marker_and_state_are_not_in_freed_init_sections(self):
        self.assertIn("static void k230_boot_trace_mark", self.helper)
        self.assertIn("static bool k230_boot_trace_enabled;", self.helper)
        self.assertIn("static unsigned int k230_boot_trace_seq;", self.helper)
        self.assertNotIn("__initdata", self.helper)
        self.assertNotIn("__init k230_boot_trace_mark", self.helper)
        self.assertIn('__setup("k230.boot_trace=", k230_boot_trace_setup);', self.helper)


if __name__ == "__main__":
    unittest.main()
