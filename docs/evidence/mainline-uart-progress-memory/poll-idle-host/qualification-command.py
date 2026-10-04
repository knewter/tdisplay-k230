"""Read-only actual artifact preparation; all baseline/raw material stays private."""
import ast
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zlib

os.umask(0o077)
directory = Path(__file__).resolve().parent
repo = Path('/home/jadams/tmp/k230-mainline-uart-progress-memory-poll-idle-controller')
root = Path('/home/jadams/tmp/k230-mainline-probe-integration')
board = Path('/home/jadams/tmp/k230-mainline-uart-memory-board')
receipt_path = board / 'full-build-result.private.json'
build = json.loads(receipt_path.read_text())
assert build['returncode'] == 0, 'actual matching full build did not succeed'
revision = build['revision']
assert isinstance(revision, str) and len(revision) == 40 and all(c in '0123456789abcdef' for c in revision), 'unknown frozen revision'
expected_revision = (directory / 'expected-root-revision.txt').read_text().strip()
assert revision == expected_revision, 'build receipt does not match the reviewed frozen root'
outputs = [Path(p) for p in build['output_paths']]
assert len(outputs) == len(set(outputs)) and all(p.exists() for p in outputs), 'missing or duplicate realized outputs'
bundles = [p for p in outputs if p.name.endswith('-k230-mainline-drm-trial-boot-files')]
assert len(bundles) == 1, 'unknown matching bundle output'
bundle = bundles[0]
controller = repo / 'tools/mainline-drm-initrd-shell-trial.py'
frozen = subprocess.check_output(['git', 'show', revision + ':tools/mainline-drm-initrd-shell-trial.py'], cwd=root, text=True)
names = {'prepare_trial', 'normal_expectation', 'prepare_uart_progress', 'prepare_shell_comparison', 'inspect_shell_initrd', 'inspect_uart_progress_kernel', 'inspect_uart_breadcrumb_kernel', 'shell_pid1_bootargs', 'validate_uart_post_sample_selector', 'validate_uart_memory_selector', 'inspect_uart_memory_kernel', 'validate_uart_memory_no_stimulus_selector', 'observe_uart_progress', 'uart_memory_summary'}
constants = {'SHELL_CONTROLS', 'SHELL_TRACE_FLAGS', 'UART_PROGRESS_FLAG', 'UART_PROGRESS_BREADCRUMBS_FLAG', 'UART_PROGRESS_BREADCRUMBS', 'UART_BREADCRUMB_SOURCE_SHA256', 'UART_PROGRESS_POST_SAMPLE_FLAG', 'UART_PROGRESS_POST_SAMPLE', 'UART_POST_SAMPLE_SOURCE_SHA256', 'NORMAL_WRAPPER_CRC32', 'UART_PROGRESS_MEMORY_FLAG', 'UART_MEMORY_FORMAT', 'UART_MEMORY_SOURCE_SHA256'}
def preparations(text, selected_names=None):
    if selected_names is None: selected_names = names
    nodes = ast.parse(text).body
    found = {n.name: ast.dump(n, include_attributes=False) for n in nodes if isinstance(n, ast.FunctionDef) and n.name in selected_names}
    for n in nodes:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and n.targets[0].id in constants:
            found[n.targets[0].id] = ast.dump(n.value, include_attributes=False)
    assert set(found) == selected_names | constants, 'missing qualified preparation functions/constants'
    return found
historical_names = names - {'validate_uart_memory_no_stimulus_selector', 'observe_uart_progress'}
assert preparations(controller.read_text(), historical_names) == preparations(frozen, historical_names), 'shared preparation differs from frozen build root'
plan_revision = '691279d0'
plan_source = subprocess.check_output(['git', 'show', plan_revision + ':tools/mainline-drm-initrd-shell-trial.py'], cwd=root, text=True)
assert preparations(controller.read_text()) == preparations(plan_source), 'controller preparation differs from reviewed 5j base'
spec = importlib.util.spec_from_file_location('memory_positive_host', controller)
trial = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = trial
spec.loader.exec_module(trial)
normal_path = directory / 'normal-report.json'
manifest_path = directory / 'candidate-manifest.json'
private_path = directory / 'prepared.private.json'
public_path = directory / 'positive-host-receipt.json'
transport_path = directory / 'transport.private.txt'
assert all(not p.exists() for p in (normal_path, manifest_path, private_path, public_path, transport_path)), 'qualification outputs must be fresh'
shutil.copyfile(board / 'normal-report.json', normal_path)
report = json.loads(normal_path.read_text())
manifest = {'system': str((bundle / 'system').resolve(strict=True)), 'files': {}}
for name, *_ in trial.LOADS:
    if name == 'fw_jump_add_uboot_head.bin':
        manifest['files'][name] = {**report['boot_files'][name], 'crc32': trial.NORMAL_WRAPPER_CRC32}
    else:
        raw = (bundle / name).read_bytes()
        manifest['files'][name] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'crc32': f'{zlib.crc32(raw):08x}'}
assert manifest == json.loads((board / 'candidate-manifest.json').read_text()), 'existing protected candidate manifest differs'
shutil.copyfile(board / 'candidate-manifest.json', manifest_path)
started = datetime.now(timezone.utc).isoformat()
p = trial.prepare_uart_progress(trial.prepare_trial(manifest_path, bundle, normal_path),
                                uart_progress_memory=True)
trial.validate_uart_memory_poll_idle_selector(True, True, True, True, True, 'minimal')
no_stimulus = dict(p, uart_progress_memory_no_stimulus=True)
previous_path = repo / 'docs/evidence/mainline-uart-progress-memory/no-stimulus-host/result.json'
previous = json.loads(previous_path.read_text())
for name, value in {'bundle': str(bundle), 'system': p['system'], 'files': manifest['files'], 'kernel_proof': p['uart_progress_kernel'], 'memory_proof': p['uart_progress_memory_kernel'], 'archive_proof': p['shell_comparison'], 'bootargs': p['bootargs']}.items():
    assert previous[name] == value, 'previous actual Memory artifact/preparation changed: ' + name
config_path = Path(p['uart_progress_kernel']['config'])
devs = [o for o in outputs if (o / 'lib/modules/7.3.0-rc5/build/.config') == config_path]
assert len(devs) == 1, 'matching build receipt lacks the qualified dev output'
# Only transport is extended; explicitly prove every previous transport output.
import types
frozen_module = types.ModuleType('poll_idle_frozen_base')
frozen_module.__file__ = str(controller)
sys.modules[frozen_module.__name__] = frozen_module
exec(compile(plan_source, str(controller), 'exec'), frozen_module.__dict__)
base_args = trial.shell_pid1_bootargs((bundle / 'bootargs.txt').read_text(), p['system'])
transports = [(base_args, {}), (base_args + ' ' + trial.UART_PROGRESS_FLAG, {'uart_progress': True})]
transports.append((transports[1][0] + ' ' + trial.UART_PROGRESS_BREADCRUMBS_FLAG, {'uart_progress': True, 'uart_progress_breadcrumbs': True}))
transports.append((transports[2][0] + ' ' + trial.UART_PROGRESS_POST_SAMPLE_FLAG, {'uart_progress': True, 'uart_progress_breadcrumbs': True, 'uart_progress_post_sample': True}))
transports.append((p['bootargs'], {'uart_progress': True, 'uart_progress_memory': True}))
for args, flags in transports:
    assert trial.shell_pid1_transport(args, p['system'], **flags) == frozen_module.shell_pid1_transport(args, p['system'], **flags)
q = trial.prepare_uart_memory_poll_idle(no_stimulus)
assert q['bootargs'].split() == p['bootargs'].split() + ['nohlt'], 'polling must add exactly one bare token'
assert len(p['transport'].encode()) == 381 and len(q['transport'].encode()) == 387
assert q['transport'] == 'setenv bootargs "' + q['bootargs'].removeprefix('bootargs=') + '"'
assert all(q[name] == p[name] for name in p if name not in ('bootargs', 'transport'))
assert q['uart_progress_memory_no_stimulus'] is True
transport_path.write_text(q['transport'] + '\n')
private_path.write_text(json.dumps({**q, 'bundle': str(q['bundle'])}, indent=2) + '\n')
public = {
    'schema': 'k230-uart-progress-memory-poll-idle-positive-host-v1',
    'evidence_class': 'actual-host-artifact-preparation-only',
    'started_utc': started, 'completed_utc': datetime.now(timezone.utc).isoformat(),
    'controller_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
    'frozen_root_revision': revision, 'matching_build_returncode': build['returncode'],
    'bundle': str(bundle), 'system': p['system'], 'files': manifest['files'],
    'kernel_proof': p['uart_progress_kernel'], 'memory_proof': p['uart_progress_memory_kernel'],
    'archive_proof': p['shell_comparison'], 'bootargs': q['bootargs'],
    'literal_transport_bytes': len(q['transport'].encode()), 'previous_memory_literal_transport_bytes': len(p['transport'].encode()),
    'poll_idle_kernel_proof': q['uart_progress_memory_poll_idle_kernel'],
    'uart_progress_memory_poll_idle': True,
    'controller_input_policy': 'zero-candidate-input',
    'uart_progress_memory_no_stimulus': True,
    'candidate_stimulus_attempts_planned': 0, 'receipt_status_planned': 'NOT_REQUESTED', 'rx_status_planned': 'NOT_TESTED',
    'additional_kernel_tokens': ['nohlt'], 'only_one_bare_nohlt_added': True,
    'all_five_previous_transport_outputs_unchanged': True,
    'same_actual_artifacts_and_qualification_as_previous_memory': True,
    'unchanged_preparation_and_parser_ast_equal_reviewed_5k_base': True, 'reviewed_5k_base': plan_revision,
    'previous_positive_receipt_sha256': hashlib.sha256(previous_path.read_bytes()).hexdigest(),
    'controller_source_sha256': hashlib.sha256(controller.read_bytes()).hexdigest(),
    'same_preparation_functions_and_constants_as_frozen_root': True,
    'matching_dev_output_realized': str(devs[0]),
    'protected_normal_report_accepted_host_only': True,
    'protected_wrapper_anchored_to_prior_normal_report_and_crc': True,
    'registration_absence_assertion_in_prepost_helper': "assert not Path('/nix-path-registration').exists() and not Path('/nix-path-registration').is_symlink()" in p['helper_text'],
    'load_ranges_validated': True, 'actual_payload_wrapper_archive_checks': True,
    'manifest_sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    'full_build_receipt_sha256': hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
    'qualification_command_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'uart_opened': False, 'board_commands_sent': False, 'implicit_build_performed': False,
    'performed_protected_board_preflight': False, 'physical_result': 'UNVERIFIED',
}
assert public['registration_absence_assertion_in_prepost_helper']
public_path.write_text(json.dumps(public, indent=2) + '\n')
print('Actual existing Memory idle-polling host qualification passed; no UART/build.')
print('Bundle:', bundle)
print('Literal transport bytes:', public['literal_transport_bytes'])
