#!/usr/bin/env python3
"""Reject incomplete/mismatched paired evidence without weakening card budgets."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from rvv_candidate_fixture import candidate

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('rvv_benchmark',ROOT/'tools/card-shell-rvv-benchmark.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
REPORT=json.loads((ROOT/'docs/evidence/card-shell/mirror-order/board/pixman.json').read_text())


def fixture():
    return [{'pair':pair,'policy':policy,'measurement_complete':True,'restored_shell_and_seatd':True,
             'boot_id':'same-boot','current_system':'candidate-system','package':'candidate-package','client_sha256':'a'*64,
             'producer_sha256':'b'*64,'library_sha256':'c'*64,'interaction_exit_code':0,'interaction_failures':[],
             'candidate_manifest_sha256':'d'*64,'kernel_image_sha256':'e'*64,
             'runtime':{'pixman_policy':policy,'pixman_disable':'rvv' if policy=='no-rvv' else '',
                        'mapping_and_policy_verified':True},'budget':M.compact_budget(REPORT)}
            for pair,policy in M.order(3)]


class PairedEvidence(unittest.TestCase):
    def test_complete_failed_measurements_stay_failed_budgets(self):
        result=M.summarize(fixture(),3)
        self.assertEqual(result['measurement_status'],'COMPLETE')
        self.assertFalse(result['all_card_budgets_pass'])
        self.assertEqual(len(result['pairs']),3)
        self.assertEqual(result['pairs'][0]['auto_rvv']['board_budget_gate'],'FAIL')
    def test_missing_repeated_or_reordered_runs_rejected(self):
        runs=fixture()
        for bad in [runs[:-1],runs+[runs[-1]],list(reversed(runs))]:
            with self.assertRaises(RuntimeError):M.summarize(bad,3)
    def test_every_pair_uses_same_identity_and_observed_policy(self):
        for key in ['boot_id','current_system','package','client_sha256','producer_sha256','library_sha256',
                    'candidate_manifest_sha256','kernel_image_sha256']:
            with self.subTest(key=key):
                runs=fixture();runs[-1][key]='changed'
                with self.assertRaises(RuntimeError):M.summarize(runs,3)
        runs=fixture();runs[1]['runtime']['pixman_disable']='rvv'
        with self.assertRaises(RuntimeError):M.summarize(runs,3)
    def test_failed_recovery_or_missing_coverage_never_complete(self):
        runs=fixture();runs[-1]['restored_shell_and_seatd']=False
        with self.assertRaises(RuntimeError):M.summarize(runs,3)
        for field in ('outer','inner','count'):
            report=copy.deepcopy(REPORT)
            if field=='outer':report['missing_evidence']=['missing provenance']
            elif field=='inner':report['runs'][0]['missing_evidence']=['missing frame coverage']
            else:report['runs']=report['runs'][:1]
            with self.subTest(field=field):
                with self.assertRaises(RuntimeError):M.compact_budget(report)
    def test_interaction_failure_retained_separately(self):
        runs=fixture();runs[0]['interaction_exit_code']=1;runs[0]['interaction_failures']=['upward-throw-close-request']
        result=M.summarize(runs,3)
        self.assertEqual(result['measurement_status'],'COMPLETE')
        self.assertFalse(result['all_interaction_checks_observed'])
    def test_host_prepare_does_not_claim_board_work(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            manifest,_=candidate(root,M.identity)
            out=root/'plan'
            with mock.patch.object(M.identity,'STORE',mock.Mock(fullmatch=lambda value: True)):
                self.assertEqual(M.main(['--prepare','--manifest',str(manifest),'--revision','a'*40,'--output',str(out)]),0)
            result=json.loads((out/'plan.json').read_text())
            self.assertFalse(result['board_commands_executed'])
            self.assertEqual(result['status'],'PLANNED_ONLY')
            self.assertEqual([v[1] for v in result['sequence']],['no-rvv','auto','auto','no-rvv','no-rvv','auto'])
            self.assertEqual(result['candidate_manifest_sha256'],M.sha(manifest))
            self.assertEqual(result['system'],str(root/'system'))
            self.assertEqual(result['board_commands_executed'],False)
        for invalid in (0,4,True):
            with self.assertRaises(ValueError):M.order(invalid)

    def test_candidate_guards_reject_missing_stale_and_mismatched_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            manifest,value=candidate(root,M.identity)
            arguments=['--prepare','--manifest',str(manifest),'--revision','a'*40,
                       '--output',str(root/'plan')]
            with mock.patch.object(M.identity,'STORE',mock.Mock(fullmatch=lambda value: True)):
                with self.assertRaises(FileNotFoundError):M.main(arguments[:2]+[str(root/'missing.json')]+arguments[3:])
                (root/'client').write_text('stale')
                with self.assertRaisesRegex(RuntimeError,'stale candidate file: client'):M.main(arguments)
                (root/'client').write_text('built candidate client')
                value['card_package']=str(root/'old-package')
                manifest.write_text(json.dumps(value))
                with self.assertRaisesRegex(RuntimeError,'missing candidate package: card_package'):M.main(arguments)
                value['card_package']=str(root/'card_package')
                (root/'system'/'boot.json').write_text(json.dumps({'org.nixos.bootspec.v1':{
                    'kernel':'/nix/store/stale/Image','toplevel':str(root/'system')}}))
                manifest.write_text(json.dumps(value))
                with self.assertRaisesRegex(RuntimeError,'kernel is not bound'):M.main(arguments)

    def test_mapped_library_must_be_exact_candidate_file(self):
        manifest={'pixman_library':'/nix/store/candidate/lib/libpixman-1.so'}
        maps='a b c d e /nix/store/candidate/lib/libpixman-1.so\n'
        self.assertEqual(M.identity.require_mapped_library(maps,manifest),[manifest['pixman_library']])
        with self.assertRaises(RuntimeError):M.identity.require_mapped_library(maps.replace('candidate','old'),manifest)
        with self.assertRaises(RuntimeError):M.identity.require_mapped_library('',manifest)


if __name__=='__main__':unittest.main()
