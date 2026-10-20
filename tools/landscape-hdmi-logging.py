#!/usr/bin/env python3
"""Bounded DEBUG/INFO/INFO/DEBUG diagnostic on the installed landscape shell."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import time
import unittest
import uuid


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


capture = module('logging_capture', 'hdmi-shell-capture-board.py')
baseline = module('logging_baseline', 'landscape-hdmi-baseline.py')
SCHEMA = 'landscape-hdmi-logging-v1'
ORDER = ('DEBUG', 'INFO', 'INFO', 'DEBUG')
DROPIN = Path('/run/systemd/system/shell.service.d/97-k230-hdmi-log-trial.conf')
FLAGS = ('WLR_RENDERER', 'WLR_PIXMAN_OUTPUT_TURN', 'WLR_PIXMAN_QUARTER_TURN',
         'WLR_PIXMAN_DRAW_TRACE', 'SWAY_K230_CPU_FRAME_TIMING',
         'SWAY_K230_TOUCH_ROUTE_TRACE', 'SWAY_K230_CARD_REDUCED_MOTION')


class TrialError(RuntimeError):
    pass


def command(*args, timeout=30):
    return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL, timeout=timeout).strip()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exec_arguments(value):
    """Only the known simple Nix-store Sway invocation may be overridden."""
    matches = re.findall(r'argv\[\]=(.*?) ; ignore_errors=', value)
    if len(matches) != 1:
        raise TrialError('cannot identify one effective ExecStart')
    args = shlex.split(matches[0])
    if (len(args) != 4 or args[1] != '-d' or args[2] != '-c' or
            not re.fullmatch(r'/nix/store/[a-z0-9]{32}-[A-Za-z0-9+._-]+/bin/sway', args[0]) or
            not re.fullmatch(r'/nix/store/[a-z0-9]{32}-[A-Za-z0-9+._/-]+', args[3])):
        raise TrialError('unexpected ExecStart; refuse to replace unknown arguments')
    return args


def override_text(args):
    # Revalidate rather than trusting a restore file or shell quoting.
    checked = exec_arguments('{ argv[]=' + ' '.join(args) + ' ; ignore_errors=no }')
    checked[1] = '-V'
    return '[Service]\nExecStart=\nExecStart=' + ' '.join(checked) + '\n'


def owned_override(path, expected, mode):
    if path.is_symlink() or (path.exists() and path.read_text() != expected):
        raise TrialError('owned logging drop-in was replaced; preserve it and stop')
    if mode == 'INFO':
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(expected)
    elif mode == 'DEBUG':
        if path.exists():
            path.unlink()
    else:
        raise TrialError('unknown logging mode')


def app_nodes(node):
    result = [node] if node.get('app_id') else []
    for key in ('nodes', 'floating_nodes'):
        for child in node.get(key, []):
            result.extend(app_nodes(child))
    return result


def idle_startup(ipc, proc_root=Path('/proc')):
    apps = app_nodes(ipc.tree())
    if len(apps) != 1 or apps[0]['app_id'] != 'k230-terminal':
        raise TrialError('preserve user apps: expected only the standard startup terminal')
    pid = apps[0].get('pid')
    if type(pid) is not int or pid <= 0:
        raise TrialError('cannot identify startup terminal process')
    children = (proc_root/f'{pid}/task/{pid}/children').read_text().split()
    if len(children) != 1:
        raise TrialError('startup terminal has an unexpected child workload')
    child = children[0]
    proc = proc_root / child
    if (proc.joinpath('comm').read_text().strip() not in ('bash', 'sh') or
            not re.search(r'^State:\s+S\b', proc.joinpath('status').read_text(), re.M) or
            proc.joinpath(f'task/{child}/children').read_text().strip()):
        raise TrialError('startup terminal has an active job; preserve it')
    return {'app_id': 'k230-terminal', 'idle_shell_without_child_jobs': True}


def expected_output(rows):
    if len(rows) != 1:
        raise TrialError('requires exactly one active output')
    row = rows[0]; mode = row.get('current_mode') or {}; rect = row.get('rect') or {}
    if (row.get('name'), row.get('transform'), row.get('scale'), mode.get('width'),
            mode.get('height'), mode.get('refresh'), rect.get('width'), rect.get('height')) != (
            'HDMI-A-1', 'normal', 1, 1280, 800, 59910, 1280, 800):
        raise TrialError('requires unchanged HDMI 1280x800@59.91 normal scale1')


def control(ipc):
    proc = Path('/proc') / str(ipc.pid)
    args = [a.decode() for a in proc.joinpath('cmdline').read_bytes().split(b'\0') if a]
    modes = [a for a in args if a in ('-d', '-V')]
    if len(modes) != 1 or len(args) != 4 or args[2] != '-c':
        raise TrialError('unexpected live compositor arguments')
    env = dict(x.split(b'=', 1) for x in proc.joinpath('environ').read_bytes().split(b'\0') if b'=' in x)
    output = capture.output_state(ipc.outputs()); expected_output(output)
    return {'pid': ipc.pid, 'debug_flag': modes[0] == '-d', 'verbose_flag': modes[0] == '-V',
            'arguments_without_logging': args[2:], 'config_sha256': digest(Path(args[3])),
            'executable_sha256': digest(proc/'exe'), 'system': str(Path('/run/current-system').resolve()),
            'persistent_system': str(Path('/nix/var/nix/profiles/system').resolve()),
            'environment': {k: env.get(k.encode(), b'').decode() for k in FLAGS},
            'output': output}


def counters(pid):
    proc = Path('/proc') / str(pid)
    stat = proc.joinpath('stat').read_text().rsplit(')', 1)[1].split()
    status = proc.joinpath('status').read_text()
    result = {'utime_ticks': int(stat[11]), 'stime_ticks': int(stat[12]),
              'clock_ticks_per_second': os.sysconf('SC_CLK_TCK')}
    for key in ('voluntary_ctxt_switches', 'nonvoluntary_ctxt_switches'):
        m = re.search(r'^' + key + r':\s*(\d+)$', status, re.M)
        if m: result[key] = int(m[1])
    try:
        result['schedstat'] = list(map(int, proc.joinpath('schedstat').read_text().split()))
    except OSError:
        result['schedstat'] = None
    return result


def wait_ready(previous_pid=None):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        ipc = None
        try:
            ipc = capture.IPC()
            if previous_pid is not None and ipc.pid == previous_pid:
                raise TrialError('old compositor still active')
            idle_startup(ipc)
            if command('systemctl', 'is-active', 'shell.service', 'shell-ui.service').splitlines() != ['active', 'active']:
                raise TrialError('shell services not ready')
            return ipc
        except (OSError, TrialError, subprocess.SubprocessError, capture.CaptureError):
            if ipc: ipc.close()
            time.sleep(.25)
    raise TrialError('shell readiness deadline expired')


def restore(directory):
    state = json.loads((directory/'restore-state.json').read_text())
    expected = override_text(state['exec_arguments'])
    try:
        current = capture.IPC()
    except OSError:
        current = None  # recover a stopped compositor as well
    if current:
        try: idle_startup(current)
        finally: current.close()
    owned_override(DROPIN, expected, 'DEBUG')
    command('systemctl', 'daemon-reload')
    command('systemctl', 'restart', 'shell.service', timeout=60)
    ipc = wait_ready()
    try:
        # Keep the operator-selected landscape mode across session restarts.
        ipc.command('output HDMI-A-1 mode 1280x800@59.910Hz transform normal scale 1')
        ipc.command('card_shell benchmark-stop'); ipc.command('card_shell home')
        restored = control(ipc)
        restored.update(benchmark_stop_succeeded=True, home_command_succeeded=True,
                        owned_dropin_absent=not DROPIN.exists(), session_restarted=True,
                        virtual_test_devices=sum('injected' in x.get('name', '').lower() or
                            'fixture' in x.get('name', '').lower() for x in ipc.request(100)),
                        services=command('systemctl', 'is-active', 'shell.service', 'shell-ui.service').splitlines(),
                        idle_terminal=idle_startup(ipc))
        original = state['original']
        for key in ('debug_flag', 'verbose_flag', 'arguments_without_logging', 'config_sha256',
                    'executable_sha256', 'system', 'persistent_system', 'environment', 'output'):
            if restored[key] != original[key]:
                raise TrialError('restore differs from original control: ' + key)
        if restored['virtual_test_devices'] or not restored['owned_dropin_absent']:
            raise TrialError('restore left diagnostic state active')
        write_json(directory/'restore.json', restored)
        return restored
    finally:
        ipc.close()


def with_restoration(action, cleanup):
    try:
        return action()
    finally:
        cleanup()


def board_run(args):
    directory = args.output.resolve()
    if directory.exists():
        raise TrialError('trial directory must not already exist')
    directory.mkdir(parents=True, mode=0o700)
    if DROPIN.exists() or DROPIN.is_symlink():
        raise TrialError('logging drop-in already exists; preserve it')
    ipc = capture.IPC()
    try:
        idle_startup(ipc); original = control(ipc)
    finally:
        ipc.close()
    if (original['system'] != args.expected_system or original['persistent_system'] != args.expected_system or
            original['executable_sha256'] != args.expected_executable_sha256 or not original['debug_flag']):
        raise TrialError('installed runtime differs from the explicitly selected baseline')
    invocation = exec_arguments(command('systemctl', 'show', 'shell.service', '-p', 'ExecStart', '--value'))
    override = override_text(invocation)
    unit = 'k230-hdmi-log-trial-' + uuid.uuid4().hex[:8] + '-restore'
    state = {'schema': SCHEMA, 'original': original, 'exec_arguments': invocation, 'restore_unit': unit}
    write_json(directory/'restore-state.json', state)
    # The timer owns no SSH pipe and survives disconnects. The script and state
    # live outside /run/shell, which systemd removes when the shell stops.
    command('systemd-run', '--quiet', '--unit=' + unit, '--on-active=900s',
            sys.executable, str(Path(__file__).resolve()), '--restore', str(directory))
    if command('systemctl', 'is-active', unit + '.timer') != 'active':
        raise TrialError('independent restore timer did not arm')

    def cleanup():
        restore(directory)
        command('systemctl', 'stop', unit + '.timer')
        write_json(directory/'cleanup.json', {'restored': True, 'restore_timer_active':
            subprocess.run(['systemctl', 'is-active', '--quiet', unit + '.timer']).returncode == 0})

    def run_all():
        for index, mode in enumerate(ORDER, 1):
            print(json.dumps({'phase': 'starting', 'index': index, 'mode': mode}), flush=True)
            ipc = capture.IPC(); old_pid = ipc.pid
            try: idle_startup(ipc)
            finally: ipc.close()
            owned_override(DROPIN, override, mode)
            command('systemctl', 'daemon-reload')
            command('systemctl', 'restart', 'shell.service', timeout=60)
            ipc = wait_ready(old_pid)
            try:
                ipc.command('output HDMI-A-1 mode 1280x800@59.910Hz transform normal scale 1')
                warm_started = time.monotonic(); time.sleep(30)
                idle_startup(ipc)
                cmd = ['sudo', '-u', 'shell', 'env', 'XDG_RUNTIME_DIR=/run/shell',
                       '/run/current-system/sw/bin/k230-shell-rust', '--surface', 'hide']
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, check=True)
                ipc.command('[app_id="k230-terminal"] focus')
                selected = control(ipc)
                if selected['debug_flag'] != (mode == 'DEBUG') or selected['verbose_flag'] != (mode == 'INFO'):
                    raise TrialError('actual logging flag does not match selected mode')
                selected['settle_seconds'] = time.monotonic() - warm_started
                selected['counters_before'] = counters(ipc.pid)
                run_dir = directory / f'{index}-{mode.lower()}'
                capture_args = argparse.Namespace(profile='landscape-1280x800', variant='candidate',
                    input='injected', operator_confirmed_contacts=False, seconds=180, drags=24,
                    source_revision=args.source_revision, output=run_dir)
                code = capture.capture(capture_args)
                selected['counters_after'] = counters(ipc.pid)
                context = json.loads((run_dir/'context.json').read_text())
                raw = capture.journal('@' + str(int(context['started_unix'])), pid=ipc.pid)
                selected['log_volume'] = {'lines': len(raw.splitlines()), 'bytes': len(raw.encode()),
                                          'bounded_limit_reached': len(raw.splitlines()) >= 20000,
                                          'window': 'capture start rounded down to seconds through final export'}
                selected.update(schema=SCHEMA, index=index, mode=mode, capture_exit_code=code)
                write_json(run_dir/'logging-control.json', selected)
                print(json.dumps({'phase': 'captured', 'index': index, 'mode': mode, 'exit_code': code}), flush=True)
                if code: raise TrialError('incomplete capture; preserve its evidence')
            finally:
                ipc.close()
    with_restoration(run_all, cleanup)


def distribution(values):
    return {'sample_count': len(values), 'p95_ms': baseline.perf.percentile(values, .95),
            'p99_ms': baseline.perf.percentile(values, .99), 'max_ms': max(values),
            'over_100ms_count': sum(x > 100 for x in values)}


def load_run(directory, index, mode):
    row, context = baseline.load(directory, 1)
    control_row = json.loads((directory/'logging-control.json').read_text())
    if (control_row.get('schema') != SCHEMA or control_row.get('index') != index or
            control_row.get('mode') != mode or control_row.get('capture_exit_code') != 0 or
            control_row.get('debug_flag') is not (mode == 'DEBUG') or
            control_row.get('verbose_flag') is not (mode == 'INFO') or
            control_row.get('settle_seconds', 0) < 30):
        raise TrialError('inconsistent logging selection, completion or settling')
    if row['drag_count'] != 24 or row['input_to_present_ms']['sample_count'] != 864:
        raise TrialError('requires exactly24 complete35-move drags')
    if control_row.get('output') != context['output']:
        raise TrialError('output differs between control and capture')
    volume = control_row.get('log_volume') or {}
    if (volume.get('bounded_limit_reached') is not False or
            any(type(volume.get(k)) is not int or volume[k] <= 0 for k in ('lines', 'bytes'))):
        raise TrialError('missing or truncated log-volume context')
    if not re.fullmatch('[0-9a-f]{64}', str(control_row.get('config_sha256', ''))):
        raise TrialError('missing configuration identity')
    if (type(control_row.get('pid')) is not int or control_row['pid'] <= 0 or
            not isinstance(control_row.get('environment'), dict) or
            not isinstance(control_row.get('arguments_without_logging'), list) or
            not str(control_row.get('system', '')).startswith('/nix/store/') or
            control_row.get('persistent_system') != control_row.get('system') or
            row['runtime_identity']['compositor_executable'].rsplit('sha256:', 1)[-1] != control_row.get('executable_sha256')):
        raise TrialError('missing or inconsistent runtime control identity')
    item = json.loads((directory/'metadata.json').read_text())['runs'][0]
    rows, _, costs = baseline.perf.parse_log((directory/item['log']).read_bytes(), item['run'])
    submits = {r['input_id']: r for r in rows if r['event'] == 'submit'}
    presents = {r['frame_id']: r for r in rows if r['event'] == 'present'}
    samples = []
    for r in rows:
        if r['event'] != 'input': continue
        sub = submits[r['input_id']]; pres = presents[sub['frame_id']]
        samples.append({'input_id': r['input_id'], 'kind': r['kind'], 'frame_id': sub['frame_id'],
            'dispatch_to_submit_ms': (sub['t_ns'] - r['t_ns']) / 1e6,
            'submit_to_present_ms': (pres['t_ns'] - sub['t_ns']) / 1e6,
            'dispatch_to_present_ms': (pres['t_ns'] - r['t_ns']) / 1e6,
            'build_cpu_ms': costs[sub['frame_id']] / 1e6})
    row.update(index=index, logging_mode=mode,
        dispatch_to_present=distribution([r['dispatch_to_present_ms'] for r in samples]),
        dispatch_to_submit=distribution([r['dispatch_to_submit_ms'] for r in samples]),
        submit_to_present=distribution([r['submit_to_present_ms'] for r in samples]),
        over_100ms_samples=[r for r in samples if r['dispatch_to_present_ms'] > 100],
        logging_control=control_row)
    return row, context, samples


def report(directory):
    loaded = [load_run(directory/f'{i}-{mode.lower()}', i, mode) for i, mode in enumerate(ORDER, 1)]
    first, first_context, _ = loaded[0]
    for row, context, samples in loaded[1:]:
        for key in ('source_revision', 'runtime_identity', 'format', 'physical_geometry', 'logical_geometry', 'input_class'):
            if row[key] != first[key]: raise TrialError('mixed runtime/workload: ' + key)
        for key in ('collector_sha256', 'injected_workload', 'output'):
            if context[key] != first_context[key]: raise TrialError('mixed capture context: ' + key)
        for key in ('arguments_without_logging', 'config_sha256', 'executable_sha256',
                    'system', 'persistent_system', 'environment', 'output'):
            if row['logging_control'].get(key) != first['logging_control'].get(key):
                raise TrialError('mixed control: ' + key)
    if len({r['logging_control']['pid'] for r, _, _ in loaded}) != 4:
        raise TrialError('every workload must restart the same compositor')
    if len({r['run'] for r, _, _ in loaded}) != 4:
        raise TrialError('workloads reuse a benchmark run identity')
    summaries = {}
    for mode in ('DEBUG', 'INFO'):
        samples = [s['dispatch_to_present_ms'] for row, _, values in loaded if row['logging_mode'] == mode for s in values]
        summaries[mode] = distribution(samples)
    cleanup = json.loads((directory/'cleanup.json').read_text())
    restored = json.loads((directory/'restore.json').read_text())
    if cleanup != {'restored': True, 'restore_timer_active': False}:
        raise TrialError('cleanup or independent timer state is incomplete')
    for key in ('debug_flag', 'verbose_flag', 'arguments_without_logging', 'config_sha256',
                'executable_sha256', 'system', 'persistent_system', 'environment', 'output'):
        if restored.get(key) != first['logging_control'].get(key): raise TrialError('restored state differs: ' + key)
    if (restored.get('owned_dropin_absent') is not True or restored.get('virtual_test_devices') != 0 or
            restored.get('services') != ['active', 'active'] or restored.get('home_command_succeeded') is not True):
        raise TrialError('normal service restoration is incomplete')
    return {'schema': SCHEMA, 'created_at': datetime.now(timezone.utc).isoformat(),
            'status': 'MEASURED', 'performance_acceptance': 'NOT_EVALUATED',
            'order': list(ORDER), 'runs': [r for r, _, _ in loaded], 'by_mode': summaries,
            'limits': ['This tests DEBUG logging contribution; INFO benchmark logging remains enabled.',
                       'Direct IPC timing is not native-input, finger or optical latency.',
                       'Four runs do not prove absence of rare stalls or a specific blocking syscall.',
                       'No persistent default, renderer change or portrait acceptance is implied.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--board-run', action='store_true'); modes.add_argument('--report', type=Path)
    modes.add_argument('--restore', type=Path); modes.add_argument('--self-test', action='store_true')
    parser.add_argument('--source-revision'); parser.add_argument('--expected-system')
    parser.add_argument('--expected-executable-sha256'); parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        if args.self_test:
            return 0 if unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Fixtures)).wasSuccessful() else 1
        if args.restore: restore(args.restore)
        elif args.report:
            result = report(args.report)
            if args.output: write_json(args.output, result)
            else: print(json.dumps(result, indent=2))
        else:
            if (args.output is None or not re.fullmatch('[0-9a-f]{40}', args.source_revision or '') or
                    not re.fullmatch('[0-9a-f]{64}', args.expected_executable_sha256 or '') or
                    not re.fullmatch(r'/nix/store/[a-z0-9]{32}-[A-Za-z0-9+._-]+', args.expected_system or '')):
                parser.error('board trial needs explicit source, system, executable hash and new output directory')
            board_run(args)
    except (TrialError, capture.CaptureError, baseline.perf.InvalidTrace, OSError, ValueError,
            KeyError, subprocess.SubprocessError) as error:
        print('landscape-logging: ' + str(error), file=sys.stderr)
        return 2
    return 0


class Fixtures(unittest.TestCase):
    def test_exec_override_rejects_unknown_arguments(self):
        args = ['/nix/store/'+'a'*32+'-sway/bin/sway', '-d', '-c', '/nix/store/'+'b'*32+'-sway.conf']
        text = '{ path=x ; argv[]='+' '.join(args)+' ; ignore_errors=no }'
        self.assertEqual(exec_arguments(text), args)
        self.assertIn(' -V -c ', override_text(args))
        for bad in (text.replace(' -d ', ' -V '), text.replace(' -d ', ' -d --extra '),
                    text.replace('/bin/sway', '/bin/sh'), text.replace('-sway.conf', '-sway.conf;true')):
            with self.subTest(bad=bad), self.assertRaises(TrialError): exec_arguments(bad)

    def test_owned_override_preserves_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'owned.conf'
            owned_override(path, 'owned', 'INFO'); self.assertEqual(path.read_text(), 'owned')
            owned_override(path, 'owned', 'DEBUG'); self.assertFalse(path.exists())
            path.write_text('someone else')
            with self.assertRaises(TrialError): owned_override(path, 'owned', 'DEBUG')
            self.assertEqual(path.read_text(), 'someone else')

    def test_cleanup_runs_after_failure(self):
        calls = []
        def failed(): calls.append('trial'); raise TrialError('fixture failure')
        with self.assertRaises(TrialError): with_restoration(failed, lambda: calls.append('restore'))
        self.assertEqual(calls, ['trial', 'restore'])

    def test_idle_guard_preserves_apps_and_terminal_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name, text in {'123/task/123/children':'124', '124/comm':'bash',
                               '124/status':'State:\tS (sleeping)\n',
                               '124/task/124/children':''}.items():
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
            class IPCFixture:
                def tree(self): return {'app_id':'k230-terminal','pid':123}
            self.assertTrue(idle_startup(IPCFixture(),root)['idle_shell_without_child_jobs'])
            (root/'124/task/124/children').write_text('125')
            with self.assertRaises(TrialError): idle_startup(IPCFixture(),root)
            (root/'124/task/124/children').write_text('')
            (root/'124/status').write_text('State:\tR (running)\n')
            with self.assertRaises(TrialError): idle_startup(IPCFixture(),root)
            class OtherApp:
                def tree(self): return {'app_id':'editor','pid':123}
            with self.assertRaises(TrialError): idle_startup(OtherApp(),root)

    def make_trial(self, directory):
        for index, mode in enumerate(ORDER, 1):
            target = directory/f'{index}-{mode.lower()}'
            baseline.Fixtures().make(target, 1)
            manifest = json.loads((target/'metadata.json').read_text()); item = manifest['runs'][0]
            # Real fixture shape: 35 motions + release for each of 24 drags.
            run = item['run'] = f'logging{index}'
            item['compositor_executable'] += ' sha256:' + 'f'*64
            write_json(target/'metadata.json', manifest)
            ctx = json.loads((target/'context.json').read_text())
            ctx['compositor']['compositor_executable'] = item['compositor_executable']
            write_json(target/'context.json', ctx)
            rows = [f'K230_CARD_BENCH v=1 run={run} event=session t_ns=1 clock=monotonic backend=drm renderer=pixman width=1280 height=800 output_format=ARGB8888 input=injected cards=1']
            for n in range(1, 865):
                gesture=(n-1)//36+1; kind='release' if n%36==0 else 'motion'; stamp=n*20000000
                rows.extend([f'K230_CARD_BENCH v=1 run={run} event=input input_id={n} gesture_id={gesture} kind={kind} source=injected t_ns={stamp}',
                    f'K230_CARD_BENCH v=1 run={run} event=submit input_id={n} frame_id={n} t_ns={stamp+2000000} update_cpu_ns=1 final={int(kind=="release")}',
                    f'K230_CARD_BENCH v=1 run={run} event=present frame_id={n} t_ns={stamp+10000000} presented=1 clock=monotonic',
                    f'K230_CARD_SHELL repaint-cost run={run} frame_id={n} render_cpu_ns=3000000 prepare_cpu_ns=1 build_cpu_ns=3000000 commit_cpu_ns=1 attempts=1 failed_attempts=0'])
            (target/item['log']).write_text('\n'.join(rows)+'\n')
            ctx = json.loads((target/'context.json').read_text())
            ctrl = dict(schema=SCHEMA, index=index, mode=mode, capture_exit_code=0,
                debug_flag=mode=='DEBUG', verbose_flag=mode=='INFO', settle_seconds=30,
                output=ctx['output_before'], config_sha256='e'*64, executable_sha256='f'*64,
                arguments_without_logging=['-c','/nix/store/config'], system='/nix/store/system',
                persistent_system='/nix/store/system', environment={}, pid=index,
                log_volume=dict(lines=10,bytes=100,bounded_limit_reached=False))
            write_json(target/'logging-control.json', ctrl)
        restored = json.loads((directory/'1-debug/logging-control.json').read_text())
        restored.update(owned_dropin_absent=True, virtual_test_devices=0, services=['active','active'], home_command_succeeded=True)
        write_json(directory/'restore.json', restored)
        write_json(directory/'cleanup.json', dict(restored=True, restore_timer_active=False))

    def test_report_separates_modes_without_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp); self.make_trial(directory); result = report(directory)
            self.assertEqual(result['status'], 'MEASURED')
            self.assertEqual(result['performance_acceptance'], 'NOT_EVALUATED')
            self.assertEqual(result['by_mode']['INFO']['sample_count'], 1728)
            self.assertEqual(result['by_mode']['DEBUG']['p99_ms'], 10)

    def test_report_rejects_invalid_control_and_coverage(self):
        for mutation in ('flag', 'order', 'config', 'system', 'output', 'pid', 'executable', 'warmup', 'log_limit', 'coverage', 'restore', 'timer'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                directory=Path(tmp); self.make_trial(directory); run=directory/'2-info'
                ctrl=json.loads((run/'logging-control.json').read_text())
                if mutation=='flag': ctrl['debug_flag']=True
                elif mutation=='order': ctrl['mode']='DEBUG'
                elif mutation=='config': ctrl['config_sha256']='a'*64
                elif mutation=='system': ctrl['system']='/nix/store/other'
                elif mutation=='output': ctrl['output'][0]['transform']='90'
                elif mutation=='pid': ctrl['pid']=1
                elif mutation=='executable': ctrl['executable_sha256']='a'*64
                elif mutation=='warmup': ctrl['settle_seconds']=0
                elif mutation=='log_limit': ctrl['log_volume']['bounded_limit_reached']=True
                elif mutation=='coverage':
                    log=run/'landscape1.log'; raw=log.read_text().splitlines();raw.pop(next(i for i,l in enumerate(raw) if 'event=present' in l));log.write_text('\n'.join(raw)+'\n')
                elif mutation=='restore':
                    restored=json.loads((directory/'restore.json').read_text());restored['owned_dropin_absent']=False;write_json(directory/'restore.json',restored)
                elif mutation=='timer': write_json(directory/'cleanup.json',dict(restored=True,restore_timer_active=True))
                write_json(run/'logging-control.json',ctrl)
                with self.assertRaises((TrialError,baseline.perf.InvalidTrace)): report(directory)


if __name__ == '__main__':
    sys.exit(main())
