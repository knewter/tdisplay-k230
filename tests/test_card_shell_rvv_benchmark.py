#!/usr/bin/env python3
"""Reject incomplete/mismatched paired evidence without weakening card budgets."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('rvv_benchmark',ROOT/'tools/card-shell-rvv-benchmark.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
REPORT=json.loads((ROOT/'docs/evidence/card-shell/mirror-order/board/pixman.json').read_text())


def fixture():
    return [{'pair':pair,'policy':policy,'measurement_complete':True,'restored_shell_and_seatd':True,
             'boot_id':'same-boot','current_system':M.SYSTEM,'package':M.PACKAGE,'client_sha256':'a'*64,
             'producer_sha256':'b'*64,'library_sha256':'c'*64,'interaction_exit_code':0,'interaction_failures':[],
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
        for key in ['boot_id','current_system','package','client_sha256','producer_sha256','library_sha256']:
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
            out=Path(directory)/'plan'
            self.assertEqual(M.main(['--prepare','--revision','a'*40,'--output',str(out)]),0)
            result=json.loads((out/'plan.json').read_text())
            self.assertFalse(result['board_commands_executed'])
            self.assertEqual(result['status'],'PLANNED_ONLY')
            self.assertEqual([v[1] for v in result['sequence']],['no-rvv','auto','auto','no-rvv','no-rvv','auto'])
        for invalid in (0,4,True):
            with self.assertRaises(ValueError):M.order(invalid)


if __name__=='__main__':unittest.main()
