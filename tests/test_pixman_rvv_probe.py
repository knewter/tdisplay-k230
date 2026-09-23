#!/usr/bin/env python3
"""Exercise the patched upstream detector with kernel capability responses."""
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class Probe(unittest.TestCase):
    def test_standard_syscall_and_safe_fallback(self):
        archive = os.environ.get("PIXMAN_SOURCE_TAR")
        if not archive:
            raise RuntimeError("Set PIXMAN_SOURCE_TAR to the pinned Pixman source tarball")
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            with tarfile.open(archive) as source:
                for name in ("meson.build", "pixman/pixman-riscv.c"):
                    path = work / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(source.extractfile("pixman-0.46.4/" + name).read())
            subprocess.run(["patch", "-p1", "-i", str(ROOT / "nix/patches/pixman-rvv-hwprobe.patch")], cwd=work, check=True, capture_output=True)
            text = (work / "pixman/pixman-riscv.c").read_text()
            start = text.index("static int\nis_rvv_1_0_available")
            detector = text[start:text.index("\n}", start)+2]
            program = r"""
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <errno.h>
#define SYS_riscv_hwprobe 258
#define RISCV_HWPROBE_KEY_IMA_EXT_0 4
#define RISCV_HWPROBE_IMA_V 4
struct riscv_hwprobe { int64_t key; uint64_t value; };
static int fail;
static uint64_t features;
static long probe_syscall(long number, struct riscv_hwprobe *pair,
                          int count, int cpus, int mask, int flags) {
    assert(number == SYS_riscv_hwprobe && count == 1);
    assert(cpus == 0 && mask == 0 && flags == 0);
    assert(pair->key == RISCV_HWPROBE_KEY_IMA_EXT_0 && pair->value == 0);
    if (fail) { errno = fail; return -1; }
    pair->value = features;
    return 0;
}
#define syscall probe_syscall
""" + detector + r"""
int main(void) {
    fail=ENOSYS; assert(!is_rvv_1_0_available());
    fail=EINVAL; assert(!is_rvv_1_0_available());
    fail=EPERM; assert(!is_rvv_1_0_available());
    fail=0; features=0; assert(!is_rvv_1_0_available());
    features=59; assert(!is_rvv_1_0_available());
    features=4; assert(is_rvv_1_0_available());
    features=63; assert(is_rvv_1_0_available());
    return 0;
}
"""
            c = work / "probe.c"
            c.write_text(program)
            binary = work / "probe"
            subprocess.run(["cc", "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined", str(c), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)

if __name__ == "__main__":
    unittest.main()
