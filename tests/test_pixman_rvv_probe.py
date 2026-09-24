#!/usr/bin/env python3
"""Exercise the patched upstream detector with kernel capability responses."""
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
import importlib.util
import json
import contextlib
import io
from types import SimpleNamespace
from unittest import mock
from rvv_candidate_fixture import candidate

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pixman_rvv_compare', ROOT / 'tools/pixman-rvv-compare.py')
DRIVER = importlib.util.module_from_spec(spec)
spec.loader.exec_module(DRIVER)

class Probe(unittest.TestCase):
    def test_manifest_requires_built_files_bootspec_and_exact_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            manifest,values=candidate(root,DRIVER.identity)
            with mock.patch.object(DRIVER.identity,'STORE',mock.Mock(fullmatch=lambda value: True)):
                self.assertEqual(DRIVER.identity.load(manifest)['system'],values['system'])
                with self.assertRaises(FileNotFoundError):DRIVER.identity.load(root/'missing.json')
                with self.assertRaisesRegex(RuntimeError,'staged candidate manifest hash'):
                    DRIVER.identity.load(manifest,expected_sha256='0'*64)
                (root/'kernel'/'Image').write_text('stale image')
                with self.assertRaisesRegex(RuntimeError,'stale candidate file: kernel_image'):
                    DRIVER.identity.load(manifest)
                (root/'kernel'/'Image').write_text('built candidate kernel_image')
                values['pixman_library']=str(root/'missing.so')
                manifest.write_text(json.dumps(values))
                with self.assertRaisesRegex(RuntimeError,'missing candidate file: pixman_library'):
                    DRIVER.identity.load(manifest)

    def test_board_runner_stages_helper_and_exact_manifest_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            manifest,values=candidate(root,DRIVER.identity)
            report={'status':'PASS','token':'1'*32,'candidate_manifest_sha256':DRIVER.digest(manifest),
                    'identity_helper_sha256':DRIVER.digest(DRIVER.IDENTITY_FILE),
                    'evidence_class':'physical-board-pixman-pixels','case_count':192,'differing_cases':0}
            calls=[]
            def run(command,**kwargs):
                calls.append(command)
                if 'console.py' in command[1]:
                    return SimpleNamespace(stdout='K230_PIXELS_RESULT '+json.dumps(report)+'\n')
                return SimpleNamespace(stdout='')
            with mock.patch.object(DRIVER.identity,'STORE',mock.Mock(fullmatch=lambda value: True)), \
                 mock.patch.object(DRIVER.identity,'require_pixel_linkage'), \
                 mock.patch.object(DRIVER.uuid,'uuid4',return_value=SimpleNamespace(hex='1'*32)), \
                 mock.patch.object(DRIVER.fcntl,'flock'), mock.patch.object(DRIVER.subprocess,'run',side_effect=run):
                with contextlib.redirect_stdout(io.StringIO()):
                    DRIVER.main(['--board','--manifest',str(manifest),'--package',values['pixel_probe'],
                                 '--output',str(root/'result')])
            staged=[call for call in calls if 'push-file.py' in call[1]]
            self.assertEqual(len(staged),3)
            self.assertIn(str(DRIVER.IDENTITY_FILE),staged[1])
            self.assertIn(str(manifest),staged[2])
            self.assertIn('--manifest-sha256',calls[-1][-1])
            self.assertIn(DRIVER.digest(manifest),calls[-1][-1])
            self.assertEqual(json.loads((root/'result'/'result.json').read_text())['status'],'PASS')

    def test_one_time_boot_accepts_candidate_system_with_unchanged_boot_partition(self):
        identity=DRIVER.identity
        value={'system':'/nix/store/candidate-system','sha256':{'kernel_image':'a'*64}}
        with mock.patch.object(identity.os.path,'realpath',return_value='/nix/store/old-system'):
            with self.assertRaisesRegex(RuntimeError,'system is not running'):identity.require_board(value)
        with mock.patch.object(identity.os.path,'realpath',return_value=value['system']), \
             mock.patch.object(identity.Path,'read_bytes',return_value=b'OTHER BOARD\0'):
            with self.assertRaisesRegex(RuntimeError,'wrong physical board'):identity.require_board(value)
        with mock.patch.object(identity.os.path,'realpath',return_value=value['system']), \
             mock.patch.object(identity.Path,'read_bytes',return_value=b'LILYGO T-Display-K230\0'), \
             mock.patch.object(identity,'digest',side_effect=AssertionError('/boot/Image is the old persistent selection')):
            identity.require_board(value)

    def test_pixel_probe_loader_path_and_observed_library_are_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            manifest,value=candidate(root,DRIVER.identity)
            soname=root/'libpixman-1.so.0'
            soname.symlink_to(root/'pixman_library')
            dynamic=f' 0x1 (NEEDED) Shared library: [libpixman-1.so.0]\n 0x1d (RUNPATH) Library runpath: [{root}]\n'
            with mock.patch.object(DRIVER.identity.subprocess,'run',return_value=SimpleNamespace(stdout=dynamic)):
                DRIVER.identity.require_pixel_linkage(value)
            with mock.patch.object(DRIVER.identity.subprocess,'run',return_value=SimpleNamespace(stdout=dynamic.replace(str(root),'/old'))):
                with self.assertRaisesRegex(RuntimeError,'loader path differs'):
                    DRIVER.identity.require_pixel_linkage(value)
            DRIVER.identity.require_loaded_pixel_library(f'calling init: {soname}\n',value)
            with self.assertRaisesRegex(RuntimeError,'loaded a different Pixman'):
                DRIVER.identity.require_loaded_pixel_library('calling init: /old/libpixman-1.so.0\n',value)

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
