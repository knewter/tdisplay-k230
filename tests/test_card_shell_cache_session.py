#!/usr/bin/env python3
"""Host checks for the opt-in board cache trial controls; no board access."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('existing_board_tests',ROOT/'tests/test_card_shell_board_tools.py')
existing=importlib.util.module_from_spec(spec);spec.loader.exec_module(existing)
H=existing.H


class ScaledCacheSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='cache-session-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.runtime=self.root/'run'
        self.runtime.mkdir()
        account=patch.object(H.pwd,'getpwnam',return_value=types.SimpleNamespace(
            pw_uid=os.getuid(),pw_gid=os.getgid(),pw_dir=str(self.root)))
        account.start();self.addCleanup(account.stop)

    def test_default_off_and_explicit_on_reach_transient_compositor_and_manifest(self):
        for policy,expected in ((None,'0'),('on','1')):
            with self.subTest(policy=policy):
                if (self.runtime/'state.json').exists():
                    (self.runtime/'state.json').unlink()
                fake=existing.Fake()
                session=H.Session(self.runtime,fake)
                plan=dict(existing.PLAN)
                if policy:plan['scaled_cache']=policy
                session.arm(plan);session.start()
                starts=[args for args in fake.trace if args[0]=='systemd-run' and '--unit='+H.UNIT in args]
                self.assertEqual(len(starts),1)
                cache_env=[arg for arg in starts[0] if arg.startswith('--setenv=SWAY_K230_CARD_SCALED_CACHE=')]
                self.assertEqual(cache_env,['--setenv=SWAY_K230_CARD_SCALED_CACHE='+expected])
                self.assertEqual(session.state['scaled_cache'],policy or 'off')
                output=self.root/('export-'+(policy or 'off'))
                session.collect(output)
                self.assertEqual(json.loads((output/'session.json').read_text())['scaled_cache'],policy or 'off')

    def test_invalid_programmatic_policy_never_mutates_normal_services(self):
        for invalid in ('enabled','1','',None,True):
            with self.subTest(invalid=invalid):
                fake=existing.Fake()
                session=H.Session(self.runtime,fake)
                with self.assertRaises(ValueError):session.arm({**existing.PLAN,'scaled_cache':invalid})
                self.assertEqual(fake.trace,[])
                self.assertTrue(fake.active('shell.service'))
                self.assertFalse((self.runtime/'state.json').exists())

    def test_prepare_cli_persists_opt_in_policy_without_board_actions(self):
        output=self.root/'prepared'
        result=H.main(['--prepare','--package',existing.PLAN['package'],
                       '--config',existing.PLAN['normal_config'],'--client',existing.PLAN['client'],
                       '--revision',existing.PLAN['source_revision'],'--scaled-cache','on',
                       '--output',str(output)])
        self.assertEqual(result,0)
        self.assertEqual(json.loads((output/'plan.json').read_text())['scaled_cache'],'on')

    def test_scaled_cache_export_requires_exact_unsigned_numeric_fields(self):
        valid='K230_CARD_SHELL scaled-cache hits=12 misses=3 fallbacks=1 bytes=4096'
        prefix='00:00:04.664 [INFO] [sway/card_shell.c:276] '
        invalid=(valid+' extra=1',valid.replace(' bytes=4096',''),
                 valid.replace('bytes=4096','bytes=-1'),valid.replace('hits=12','hits=secret'),
                 valid.replace(' bytes=4096',' hits=1'))
        text='\n'.join(prefix+row for row in (valid,*invalid))+'\n'
        self.assertEqual(H.normalized_journal(text),valid+'\n')


if __name__=='__main__':unittest.main()
