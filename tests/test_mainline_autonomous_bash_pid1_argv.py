#!/usr/bin/env python3
"""Native pinned Hush and selected Linux argv execution; no board access."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

FIX = Path(__file__).resolve().parent / 'fixtures/mainline-autonomous-pid1'
NONCE = b'0123456789abcdef0123456789abcdef'
HUSH_SHA = '954771b8638977d12955c4da3c540a3929d47e4431a092c079192155b2d60011'


def vector(nonce):
    # This is byte substitution in independent checked-in scout vectors,
    # not a shell lexer or Linux command-line model.
    if not isinstance(nonce, bytes) or not re.fullmatch(b'[0-9a-f]{32}', nonce):
        raise ValueError('exact lowercase nonce required')
    return tuple((FIX / n).read_bytes().replace(NONCE, nonce) for n in
                 ('script.expected', 'bootargs.expected', 'transport.expected'))


class NativeArgv(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='k230-native-argv-')
        cls.hush = Path(cls.tmp.name) / 'hush'
        cls.linux = Path(cls.tmp.name) / 'linux'
        for source, out, includes in [('hush-native.c', cls.hush, ['-Wno-sign-compare', '-I', str(FIX / 'include')]),
                                      ('linux-native.c', cls.linux, [])]:
            p = subprocess.run([os.environ.get('CC', 'cc'), '-std=gnu11', '-Wall', '-Wextra',
                                '-Wno-unused-function', '-Wno-unused-variable', '-Wno-unused-parameter',
                                *includes, str(FIX / source), '-o', str(out)], capture_output=True)
            if p.returncode or p.stderr:
                raise AssertionError(p.stderr.decode())

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def hush_run(self, command, nonce=None, expected=None):
        args = [str(self.hush)]
        if nonce is not None:
            args += [nonce.decode('ascii'), expected.decode('ascii')]
        return subprocess.run(args, input=command, capture_output=True, timeout=3)

    def linux_run(self, command):
        return subprocess.run([str(self.linux)], input=command, capture_output=True, timeout=3)

    def test_pinned_full_hush_source(self):
        self.assertEqual(hashlib.sha256((FIX / 'cli_hush-v2022.10.c').read_bytes()).hexdigest(), HUSH_SHA)
        self.assertTrue((FIX / 'cli_hush-v2022.10.c').read_bytes().startswith(b'// SPDX-License-Identifier: GPL-2.0+'))

    def test_exact_independent_lengths_and_native_pipeline(self):
        script, raw, wire = vector(NONCE)
        self.assertEqual(tuple(map(len, (script, raw, wire))), (154, 477, 503))
        self.assertLessEqual(len(wire) + 1, 512)
        h = self.hush_run(wire, NONCE, wire)
        self.assertEqual(h.returncode, 0, h.stderr)
        self.assertEqual(h.stdout, raw)
        self.assertEqual(h.stderr, b'dispatch=setenv argc=3\nrc=0 commands=1 lookups=1 writes=0 expansions=0\n')
        k = self.linux_run(h.stdout)
        self.assertEqual(k.returncode, 0, k.stderr)
        self.assertEqual(k.stdout, b'-c\0' + script + b'\0')
        self.assertIn(b'rdinit=/bin/sh rdinit_set=1', k.stderr)

    def test_many_valid_nonces_exact_native_execution(self):
        for nonce in [b'0'*32, b'f'*32, b'a1'*16, b'0123456789abcdef'*2]:
            with self.subTest(nonce=nonce):
                script, raw, wire = vector(nonce)
                h = self.hush_run(wire, nonce, wire)
                self.assertEqual((h.returncode, h.stdout), (0, raw))
                self.assertIn(b'expansions=0', h.stderr)
                k = self.linux_run(raw)
                self.assertEqual((k.returncode, k.stdout), (0, b'-c\0'+script+b'\0'))

    def test_invalid_nonce_rejected_before_hush(self):
        _, _, wire = vector(NONCE)
        for bad in [b'', b'a'*31, b'a'*33, b'A'*32, b'g'*32, b'$(saveenv)'+b'a'*22,
                    b"'"+b'a'*31, b'\\'+b'a'*31, b';'+b'a'*31, b'\n'+b'a'*31]:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError): vector(bad)
                h = self.hush_run(wire, bad, wire)
                self.assertEqual(h.returncode, 64)
                self.assertEqual(h.stdout, b'')
                self.assertEqual(h.stderr, b'rejected-before-parser\n')

    def test_altered_special_syntax_rejected_before_parser(self):
        _, _, wire = vector(NONCE)
        changes = [wire+b';saveenv', wire+b'\nreset', wire.replace(b'$n', b'${n}'),
                   wire.replace(b'\\\\\\\\n', b'\\\\n'), wire.replace(b'5&&', b'6&&'),
                   wire.replace(b"'", b'"'), wire.replace(b'-- -c', b'-c'),
                   wire.replace(b'exec /bin/sh -i', b'exit'), wire+b' ', wire[:-1]]
        for altered in changes:
            with self.subTest(altered=altered):
                self.assertNotEqual(altered, wire)
                h = self.hush_run(altered, NONCE, wire)
                self.assertEqual((h.returncode, h.stdout, h.stderr),
                                 (64, b'', b'rejected-before-parser\n'))

    def test_native_hush_exposes_extra_command_without_executing_it(self):
        _, raw, wire = vector(NONCE)
        h = self.hush_run(wire+b';saveenv')
        self.assertNotEqual(h.returncode, 0)
        self.assertEqual(h.stdout, raw)
        self.assertIn(b'dispatch=saveenv argc=1', h.stderr)
        self.assertIn(b'commands=2', h.stderr)
        self.assertIn(b'writes=0', h.stderr)

    def test_native_hush_backslash_layer_is_not_posix(self):
        _, raw, wire = vector(NONCE)
        altered = wire.replace(b'\\\\\\\\n', b'\\\\n')
        h = self.hush_run(altered)
        self.assertEqual(h.returncode, 0)
        self.assertNotEqual(h.stdout, raw)
        self.assertEqual(h.stdout, raw.replace(b'\\\\n', b'\\n'))

    def test_native_hush_unquoted_variable_lookup_is_observed(self):
        h = self.hush_run(b'setenv bootargs $EUID')
        self.assertNotEqual(h.returncode, 0)
        self.assertRegex(h.stderr, b'expansions=[1-9]')

    def test_linux_assignment_repair_and_outer_quotes(self):
        script, raw, _ = vector(NONCE)
        k = self.linux_run(raw)
        self.assertEqual(k.stdout.split(b'\0'), [b'-c', script, b''])
        self.assertTrue(script.startswith(b'n='+NONCE+b';'))
        self.assertNotIn(b'"', k.stdout)
        self.assertIn(b'$$', k.stdout)
        self.assertIn(b'\\\\n', k.stdout)

    def test_linux_init_rdinit_order_clears_earlier_args(self):
        script, raw, _ = vector(NONCE)
        # Exercise actual setup reset loops on both orders, before post-- args.
        prefix, tail = raw.split(b' -- ', 1)
        init = next(x for x in prefix.split() if x.startswith(b'init='))
        for p in [b'auto '+init+b' rdinit=/bin/sh', b'auto rdinit=/bin/sh '+init]:
            k = self.linux_run(p+b' -- '+tail)
            self.assertEqual(k.returncode, 0)
            self.assertEqual(k.stdout, b'-c\0'+script+b'\0')
            self.assertIn(b'rdinit=/bin/sh rdinit_set=1', k.stderr)

    def test_linux_post_separator_options_are_argv_not_setup(self):
        _, raw, _ = vector(NONCE)
        k = self.linux_run(raw+b' init=/post-only rdinit=/post-only')
        self.assertEqual(k.returncode, 0)
        self.assertEqual(k.stdout.split(b'\0')[-3:], [b'init=/post-only', b'rdinit=/post-only', b''])
        self.assertIn(b'rdinit=/bin/sh rdinit_set=1', k.stderr)

    def test_selected_linux_excerpts_have_pinned_receipt(self):
        receipt = json.loads((FIX/'linux-source.json').read_text())
        self.assertEqual(receipt['source'], '/nix/store/0l4mgw9hr1j7pj247jsrxjd478fnlfy8-linux-mainline-k230-uart-progress-memory-printk-src')
        text=(FIX/'linux-selected-functions.h').read_text()
        for info in receipt['files'].values():
            self.assertEqual(len(info['sha256']), 64)
            for name, item in info['functions'].items():
                import re
                m=re.search(r'^(?:static )?(?:int|void|char \*)\s*(?:__init )?'+name+r'\(',text,re.M)
                self.assertIsNotNone(m)
                brace=text.index('{',m.start());depth=1;i=brace+1
                while depth:
                    depth += (text[i]=='{')-(text[i]=='}');i+=1
                excerpt=text[m.start():i]+'\n'
                self.assertEqual(hashlib.sha256(excerpt.encode()).hexdigest(),item['sha256'])
                actual=Path(receipt['source']) / next(f for f, v in receipt['files'].items() if v is info)
                if actual.exists():
                    data=actual.read_text()
                    self.assertEqual(hashlib.sha256(data.encode()).hexdigest(),info['sha256'])
                    self.assertIn(excerpt,data)


if __name__ == '__main__':
    unittest.main()
