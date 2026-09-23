#!/usr/bin/env python3
"""Prevent physical evidence from passing on stale boots or lost boot data."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('board', Path(__file__).resolve().parents[1]/'tools/check-root-growth.py')
board = importlib.util.module_from_spec(spec)
spec.loader.exec_module(board)


def reports():
    before = dict(status='PASS', phase='before', boot_id='boot-one', selected_system='new',
        current_system='old', protected={'firmware':'unchanged', 'sentinel':'unchanged'},
        filesystem_available_bytes=70*1024**2,
        guard={'layout': {'disk_bytes':128*1024**3, 'root_sectors':4245496, 'root_uuid':'uuid'},
               'filesystem_bytes_before':4245496*512},
        **{key:True for key in ('shell_active', 'seatd_active', 'wifi_associated',
            'wifi_ipv4', 'wifi_https_200', 'credentials_root_0600')})
    after = copy.deepcopy(before)
    after.update(phase='after', boot_id='boot-two', current_system='new',
        filesystem_available_bytes=120*1024**3,
        growth_unit={'ActiveState':'active','SubState':'exited','Result':'success','ExecMainStatus':'0'})
    sectors = 128*1024**3//512-262144-33
    after['guard']['layout']['root_sectors'] = sectors
    after['guard']['filesystem_bytes_before'] = sectors*512-3584
    after['growth_journal'] = [dict(status='grown', mutation_requested=True,
        layout=copy.deepcopy(before['guard']['layout']), root_sectors_after=sectors,
        filesystem_bytes_before=before['guard']['filesystem_bytes_before'],
        filesystem_bytes_after=after['guard']['filesystem_bytes_before'])]
    repeat = copy.deepcopy(after)
    repeat.update(phase='repeat',boot_id='boot-three')
    repeat['growth_journal'][0].update(status='no-change',layout=copy.deepcopy(after['guard']['layout']),
        filesystem_bytes_before=after['guard']['filesystem_bytes_before'])
    return before, after, repeat


class BoardEvidence(unittest.TestCase):
    def test_first_and_repeat(self):
        a,b,c=reports()
        board.verify(a,'before'); board.verify(b,'after',a); board.verify(c,'repeat',b)

    def test_reject_bad_first_boot_evidence(self):
        a,b,_=reports()
        mutations = [
            lambda r:r.update(boot_id=a['boot_id']),
            lambda r:r.update(current_system='old'),
            lambda r:r.update(selected_system='different'),
            lambda r:r['protected'].update(sentinel='lost'),
            lambda r:r['protected'].update(firmware='changed'),
            lambda r:r['guard']['layout'].update(root_uuid='new'),
            lambda r:r['growth_unit'].update(Result='timeout'),
            lambda r:r.update(growth_journal=[]),
            lambda r:r['growth_journal'].append(r['growth_journal'][0]),
            lambda r:r['growth_journal'][0].update(status='no-change'),
            lambda r:r['growth_journal'][0].update(mutation_requested=False),
            lambda r:r['growth_journal'][0].update(filesystem_bytes_after=1),
            lambda r:r['growth_journal'][0]['layout'].update(root_sectors=1),
            lambda r:r.update(filesystem_available_bytes=a['filesystem_available_bytes']),
        ]
        mutations += [lambda r,k=k:r.update({k:False}) for k in
                      ('shell_active','seatd_active','wifi_associated','wifi_ipv4',
                       'wifi_https_200','credentials_root_0600')]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                bad=copy.deepcopy(b);mutate(bad)
                with self.assertRaises(RuntimeError):board.verify(bad,'after',a)

    def test_reject_stale_or_changing_repeat(self):
        a,b,c=reports()
        for key,value in [('boot_id',b['boot_id']),('current_system','old')]:
            bad=copy.deepcopy(c);bad[key]=value
            with self.assertRaises(RuntimeError):board.verify(bad,'repeat',b)
        c['growth_journal'][0]['status']='grown'
        with self.assertRaises(RuntimeError):board.verify(c,'repeat',b)
        with self.assertRaises(RuntimeError):board.verify(b,'after',b)
        a['status']='FAIL'
        with self.assertRaises(RuntimeError):board.verify(b,'after',a)


if __name__ == '__main__':
    unittest.main()
