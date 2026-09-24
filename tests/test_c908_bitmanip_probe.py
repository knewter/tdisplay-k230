#!/usr/bin/env python3
"""Host-only scalar/fault checks and RV64GC object inspection."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'nix/c908-bitmanip-probe.c'


class Probe(unittest.TestCase):
    def test_native_scalar_vectors_and_fault_harness(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / 'probe'
            subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-fno-lto',
                            str(SOURCE), '-o', str(binary)], check=True, capture_output=True)
            result = subprocess.run([str(binary), '--self-test'], check=True,
                                    capture_output=True, text=True, timeout=5)
            lines = result.stdout.splitlines()
            self.assertEqual(len(lines), 1)
            self.assertTrue(lines[0].startswith('K230_BITMANIP_SELF_TEST '))
            report = json.loads(lines[0].split(' ', 1)[1])
            self.assertEqual(report, {'status': 'PASS',
                                      'evidence_class': 'host-scalar-and-fault-harness',
                                      'vectors': 16})
            invalid = subprocess.run([str(binary), '--probe'], capture_output=True,
                                     text=True, timeout=2)
            self.assertEqual(invalid.returncode, 2)
            self.assertIn('requires a RISC-V build', invalid.stderr)

    def test_cross_object_stays_baseline_and_contains_isolated_instructions(self):
        compiler = os.environ.get('C908_RISCV_CC') or shutil.which('riscv64-unknown-linux-gnu-gcc')
        objdump = os.environ.get('C908_RISCV_OBJDUMP') or shutil.which('riscv64-unknown-linux-gnu-objdump')
        if not compiler or not objdump:
            self.skipTest('cross compiler/objdump not supplied; native host guard still runs')
        with tempfile.TemporaryDirectory() as directory:
            obj = Path(directory) / 'probe.o'
            subprocess.run([compiler, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                            '-fno-lto', '-march=rv64gc', '-mabi=lp64d', '-c',
                            str(SOURCE), '-o', str(obj)], check=True, capture_output=True, timeout=30)
            attributes = subprocess.run(['readelf', '-A', str(obj)], check=True,
                                        capture_output=True, text=True).stdout
            isa = next(line for line in attributes.splitlines() if 'Tag_RISCV_arch' in line).lower()
            for extension in ('zba', 'zbb', 'zbc', 'zbs', 'v1p0'):
                self.assertNotIn(extension, isa)
            assembly = subprocess.run([objdump, '-d', str(obj)], check=True,
                                      capture_output=True, text=True).stdout
            for instruction in ('sh1add', 'andn', 'clmul', 'bset'):
                self.assertIn(instruction, assembly)


if __name__ == '__main__':
    unittest.main()
