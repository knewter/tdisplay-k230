#!/usr/bin/env python3
"""Qualify one bounded injected-motion pair on the cached-EDID candidate."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import unittest

_spec = importlib.util.spec_from_file_location('stable_detect', Path(__file__).with_name('landscape-hdmi-detect.py'))
detect = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(detect)
base, log, cap = detect.base, detect.log, detect.cap
Error = base.TraceError
SCHEMA = 'hdmi-stable-poll-proof-v1'


def load(path):
    return json.loads(path.read_text())


def identities():
    return {'tool_sha256': log.digest(Path(__file__)),
            'detect_sha256': log.digest(Path(detect.__file__)), 'dependencies': detect.dependencies()}


def boot_identity():
    return {'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'kernel': log.command('uname', '-r'), 'machine': log.command('uname', '-m'),
            'booted_system': os.path.realpath('/run/booted-system')}


def qualify_poll(rows):
    """Reject EDID reads/long complete holds without discarding boundary probes."""
    functions = [{k: v for k, v in r.items() if k != 'event'} for r in rows if r['event'] == 'function']
    held, rejected = detect.holder.intervals(functions)
    cycles = sorted({(h['pid'], h['poll_ns']) for h in held})
    readers = [r for r in functions if r['symbol'] in (
        'drm_bridge_connector_read_edid', 'lt9611_bridge_edid_read', 'lt9611_get_edid_block')]
    long = [h for h in held if h['held_lower_bound_ms'] > 100]
    # Reject ambiguous interior sequences; incomplete boundary probes remain explicit.
    ambiguous = [r for r in rejected if r['reason'] != 'capture boundary before probe completed']
    reasons = []
    if len(cycles) < 3: reasons.append('fewer than three complete polling cycles')
    if readers: reasons.append('EDID reader path occurred during stable observation')
    if long: reasons.append('poll-held interval exceeded100ms')
    if ambiguous: reasons.append('ambiguous interior polling sequence')
    return {'status': 'QUALIFIED' if not reasons else 'REJECTED', 'reasons': reasons,
            'complete_poll_cycles': len(cycles), 'poll_held_intervals': held,
            'rejected_poll_intervals': rejected, 'edid_reader_markers': readers,
            'over_100ms_poll_intervals': long,
            'interval_definition': 'detect_connector_status entry to drm_modeset_drop_locks entry in the same complete source-grounded LT9611 poll probe; not exact lock acquisition/release'}


def capture_run(directory, args, ipc, traced):
    directory.mkdir(mode=0o700)
    selected = log.control(ipc); log.idle_startup(ipc)
    subprocess.run(['sudo', '-u', 'shell', 'env', 'XDG_RUNTIME_DIR=/run/shell',
                    '/run/current-system/sw/bin/k230-shell-rust', '--surface', 'hide'],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    ipc.command('[app_id="k230-terminal"] focus'); time.sleep(5)
    session = detect.Session(directory, 'probe') if traced else None
    try:
        if session: session.prepare(); session.start()
        code = cap.capture(argparse.Namespace(profile='landscape-1280x800', variant='candidate',
            input='injected', operator_confirmed_contacts=False, seconds=180, drags=24,
            source_revision=args.source_revision, output=directory / 'capture'))
        if session: session.finish()
        base.immutable(selected, log.control(ipc))
        log.write_json(directory / 'control.json', {'control': selected, 'traced': traced,
            'capture_exit_code': code, **identities()})
        if code: raise Error('capture incomplete; retain this attempt without retry')
        base.benchmark(directory / 'capture')
    finally:
        if session: base.safe_close(session)


def board_run(args):
    smoke = load(args.smoke / 'smoke.json'); detect.checked(args.smoke); detect.cleanup_checked(args.smoke)
    identity = identities(); boot = boot_identity()
    fresh = load(args.smoke / 'candidate-smoke.json')
    if fresh != {'schema': SCHEMA, 'boot': boot, **identity}:
        raise Error('smoke is not from this candidate boot/controller')
    if (smoke.get('status') != 'QUALIFIED' or smoke.get('schema') != detect.SCHEMA or
        smoke.get('kernel') != boot['kernel'] or smoke.get('machine') != 'riscv64' or
        smoke.get('system') != args.expected_system or
        smoke.get('tool_sha256') != identity['detect_sha256'] or smoke.get('dependencies') != identity['dependencies']):
        raise Error('fresh candidate smoke identity differs')
    directory = base.new_directory(args.output); ipc = cap.IPC(); original = None
    globals_before = detect.global_state()
    try:
        original = log.control(ipc); base.immutable(smoke['control'], original); log.idle_startup(ipc)
        if (original['system'] != args.expected_system or original['persistent_system'] != args.expected_persistent_system or
            original['executable_sha256'] != args.expected_executable_sha256 or not original['debug_flag'] or
            boot['booted_system'] != args.expected_system): raise Error('candidate/preserved fallback runtime differs')
        log.write_json(directory / 'original.json', original)
        log.write_json(directory / 'qualified-smoke.json', smoke)
        log.write_json(directory / 'candidate-smoke.json', fresh)
        for name, traced in [('untraced', False), ('traced', True)]:
            print(json.dumps({'phase': 'starting', 'run': name}), flush=True)
            base.immutable(original, log.control(ipc))
            if detect.global_state() != globals_before or boot_identity() != boot: raise Error('boot/global controls changed')
            capture_run(directory / name, args, ipc, traced)
            print(json.dumps({'phase': 'captured', 'run': name}), flush=True)
    finally:
        try:
            if (directory / 'original.json').exists():
                ipc.command('card_shell benchmark-stop'); ipc.command('card_shell home')
                final = log.control(ipc); base.immutable(original, final)
                log.write_json(directory / 'normal.json', {'checked_at': base.now(), 'control': final,
                    'global_before': globals_before, 'global_after': detect.global_state(),
                    'boot_before': boot, 'boot_after': boot_identity(), 'home_command_succeeded': True,
                    'benchmark_stop_succeeded': True, 'idle_terminal': log.idle_startup(ipc),
                    'services': log.command('systemctl', 'is-active', 'shell.service', 'shell-ui.service').splitlines(),
                    'virtual_test_devices': sum('injected' in r.get('name', '').lower() or 'fixture' in r.get('name', '').lower() for r in ipc.request(100))})
        finally: ipc.close()
    log.write_json(directory / 'trial.json', {'schema': SCHEMA, 'status': 'CAPTURED',
        'runs': ['untraced', 'traced'], 'source_revision': args.source_revision, 'boot': boot, **identity})


def report(directory):
    trial = load(directory / 'trial.json'); smoke = load(directory / 'qualified-smoke.json')
    original = load(directory / 'original.json'); normal = load(directory / 'normal.json')
    if trial.get('schema') != SCHEMA or trial.get('status') != 'CAPTURED' or trial.get('runs') != ['untraced', 'traced']:
        raise Error('requires exact single untraced/traced pair')
    if load(directory / 'candidate-smoke.json') != {'schema': SCHEMA, 'boot': trial['boot'],
            **{k: trial[k] for k in ('tool_sha256', 'detect_sha256', 'dependencies')}}:
        raise Error('candidate smoke/boot identity differs')
    base.immutable(smoke['control'], original); base.immutable(original, normal['control'])
    if (normal['global_before'] != normal['global_after'] or normal['boot_before'] != trial['boot'] or
        normal['boot_after'] != trial['boot'] or normal['services'] != ['active', 'active'] or
        normal['virtual_test_devices'] != 0 or not normal['idle_terminal'].get('idle_shell_without_child_jobs') or
        normal.get('home_command_succeeded') is not True or normal.get('benchmark_stop_succeeded') is not True):
        raise Error('boot/control/normal cleanup incomplete')
    if (smoke.get('tool_sha256') != trial['detect_sha256'] or smoke.get('dependencies') != trial['dependencies']):
        raise Error('smoke/source dependency mismatch')
    runs = []; first_row = first_context = None
    for name, traced in [('untraced', False), ('traced', True)]:
        run = directory / name; control = load(run / 'control.json')
        base.immutable(original, control['control'])
        if (control.get('traced') is not traced or control.get('capture_exit_code') != 0 or
            any(control.get(k) != trial[k] for k in ('tool_sha256', 'detect_sha256', 'dependencies'))):
            raise Error('run identity/integrity differs')
        row, context, samples = base.benchmark(run / 'capture')
        if row['source_revision'] != trial['source_revision']: raise Error('capture source differs')
        if first_row is not None:
            for k in ('source_revision', 'runtime_identity', 'format', 'input_class'):
                if first_row[k] != row[k]: raise Error('paired runtime/workload differs: ' + k)
            if row['run'] == first_row['run'] or any(context[k] != first_context[k] for k in
                ('collector_sha256', 'injected_workload', 'output')): raise Error('paired run token/context differs')
        else: first_row, first_context = row, context
        item = {'name': name, 'benchmark': row, 'context': context,
                'over_100ms_samples': [s for s in samples if s['wall_ms'] > 100]}
        if traced:
            rows, meta = detect.checked(run); detect.cleanup_checked(run)
            if (meta['mode'] != 'probe' or meta['tool_sha256'] != trial['detect_sha256'] or
                meta['dependencies'] != trial['dependencies'] or
                not meta['markers']['start']['after_ns'] <= min(s['start_ns'] for s in samples) <=
                    max(s['end_ns'] for s in samples) <= meta['markers']['end']['before_ns']):
                raise Error('trace source or complete workload bracket differs')
            item.update(poll=qualify_poll(rows), trace=meta)
        runs.append(item)
    return {'schema': SCHEMA, 'status': runs[1]['poll']['status'], 'created_at': base.now(),
        'trial': trial, 'original': original, 'normal': normal, 'runs': runs,
        'report_tool_sha256': log.digest(Path(__file__)), 'limits': [
            'One untraced/traced injected24-drag pair; no retries or universal latency guarantee.',
            'Only selected kernel function entries; no syscall/scheduler, mutex pointer or exact acquisition/release proof.',
            'Source-grounded poll probes lack per-probe connector IDs; observed HDMI geometry and LT9611 callbacks ground the stable path.',
            'Input-to-presentation feedback is not native touch, glass contact or optical visibility.',
            'Prior baseline is a separate kernel/system/boot/process; compare identities explicitly, never as the same-process pair.',
            'Physical cable/input and persistent ordinary boot remain separate acceptance gates.']}


class Fixtures(unittest.TestCase):
    def rows(self):
        rows = []
        for poll in (1_000_000_000, 11_240_000_000, 21_480_000_000):
            for offset, symbol, parent in [(0, 'output_poll_execute', '[other]'),
                (1000, 'drm_helper_probe_detect_ctx', 'output_poll_execute'),
                (2000, 'detect_connector_status', 'drm_helper_probe_detect_ctx'),
                (3000, 'lt9611_bridge_detect', '[other]'),
                (400000, 'drm_modeset_drop_locks', 'drm_helper_probe_detect_ctx')]:
                rows.append(dict(event='function', pid=10, cpu=0, ts_ns=poll+offset, symbol=symbol, parent=parent))
        return rows

    def test_three_cycles_and_boundaries(self):
        rows = self.rows(); self.assertEqual(qualify_poll(rows)['status'], 'QUALIFIED')
        rows += [dict(rows[-4], ts_ns=rows[-1]['ts_ns']+1000)]
        result = qualify_poll(rows)
        self.assertEqual(result['status'], 'QUALIFIED')
        self.assertEqual(len(result['rejected_poll_intervals']), 1)

    def test_reject_reader_long_hold_missing_cycle_and_caller(self):
        for mutation in ('reader', 'long', 'missing', 'caller'):
            with self.subTest(mutation=mutation):
                rows = self.rows()
                if mutation == 'reader': rows.insert(4, dict(rows[3], symbol='drm_bridge_connector_read_edid', ts_ns=rows[3]['ts_ns']+1000))
                elif mutation == 'long': rows[4]['ts_ns'] += 200_000_000
                elif mutation == 'missing': rows = rows[:-5]
                else: rows[1]['parent'] = '[other]'
                self.assertEqual(qualify_poll(rows)['status'], 'REJECTED')


def main():
    p = argparse.ArgumentParser(description=__doc__); g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--self-test', action='store_true'); g.add_argument('--board-run', action='store_true')
    g.add_argument('--board-smoke', action='store_true')
    g.add_argument('--report', type=Path); p.add_argument('--output', type=Path); p.add_argument('--smoke', type=Path)
    p.add_argument('--source-revision'); p.add_argument('--expected-system'); p.add_argument('--expected-persistent-system')
    p.add_argument('--expected-executable-sha256'); args = p.parse_args()
    try:
        if args.self_test:
            r = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Fixtures))
            return 0 if r.wasSuccessful() else 1
        if args.output is None: p.error('--output required')
        if args.report:
            result = report(args.report); log.write_json(args.output, result)
            return 0 if result['status'] == 'QUALIFIED' else 2
        if args.board_smoke:
            detect.board_smoke(args)
            log.write_json(args.output / 'candidate-smoke.json', {'schema': SCHEMA,
                'boot': boot_identity(), **identities()})
            return 0
        if (args.smoke is None or not re.fullmatch('[0-9a-f]{40}', args.source_revision or '') or
            not re.fullmatch('[0-9a-f]{64}', args.expected_executable_sha256 or '') or
            any(not re.fullmatch(r'/nix/store/[a-z0-9]{32}-[A-Za-z0-9+._-]+', v or '') for v in
                (args.expected_system, args.expected_persistent_system))): p.error('explicit smoke/source/system/fallback/executable identities required')
        board_run(args)
    except (Error, log.TrialError, cap.CaptureError, OSError, ValueError, KeyError, EOFError, subprocess.SubprocessError) as error:
        print('stable-poll: ' + str(error), file=sys.stderr); return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
