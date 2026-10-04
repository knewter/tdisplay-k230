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
repo = Path('/home/jadams/tmp/k230-mainline-uart-progress-post-sample-controller')
root = Path('/home/jadams/tmp/k230-mainline-probe-integration')
board = Path('/home/jadams/tmp/k230-mainline-uart-post-sample-board')
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
names = {'prepare_trial', 'normal_expectation', 'prepare_uart_progress', 'prepare_shell_comparison', 'inspect_shell_initrd', 'inspect_uart_progress_kernel', 'inspect_uart_breadcrumb_kernel', 'shell_pid1_bootargs', 'shell_pid1_transport', 'validate_uart_post_sample_selector'}
constants = {'SHELL_CONTROLS', 'SHELL_TRACE_FLAGS', 'UART_PROGRESS_FLAG', 'UART_PROGRESS_BREADCRUMBS_FLAG', 'UART_PROGRESS_BREADCRUMBS', 'UART_BREADCRUMB_SOURCE_SHA256', 'UART_PROGRESS_POST_SAMPLE_FLAG', 'UART_PROGRESS_POST_SAMPLE', 'UART_POST_SAMPLE_SOURCE_SHA256', 'NORMAL_WRAPPER_CRC32'}
def preparations(text):
    nodes = ast.parse(text).body
    found = {n.name: ast.dump(n, include_attributes=False) for n in nodes if isinstance(n, ast.FunctionDef) and n.name in names}
    for n in nodes:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and n.targets[0].id in constants:
            found[n.targets[0].id] = ast.dump(n.value, include_attributes=False)
    assert set(found) == names | constants, 'missing qualified preparation functions/constants'
    return found
assert preparations(controller.read_text()) == preparations(frozen), 'controller preparation differs from frozen root'
spec = importlib.util.spec_from_file_location('post_sample_positive_host', controller)
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
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
started = datetime.now(timezone.utc).isoformat()
p = trial.prepare_uart_progress(trial.prepare_trial(manifest_path, bundle, normal_path),
                                uart_progress_breadcrumbs=True, uart_progress_post_sample=True)
config_path = Path(p['uart_progress_kernel']['config'])
devs = [o for o in outputs if (o / 'lib/modules/7.3.0-rc5/build/.config') == config_path]
assert len(devs) == 1, 'matching build receipt lacks the qualified dev output'
params = p['bootargs'].removeprefix('bootargs=').split()
required = (*trial.SHELL_CONTROLS, 'rdinit=/bin/sh', trial.UART_PROGRESS_FLAG,
            trial.UART_PROGRESS_BREADCRUMBS_FLAG, trial.UART_PROGRESS_POST_SAMPLE_FLAG, 'init=' + p['system'] + '/init')
assert all(params.count(v) == 1 for v in required)
assert not any(v in params for v in trial.SHELL_TRACE_FLAGS)
assert p['bootargs'].endswith(' ' + trial.UART_PROGRESS_POST_SAMPLE_FLAG)
prior_args = p['bootargs'].removesuffix(' ' + trial.UART_PROGRESS_POST_SAMPLE_FLAG)
prior_transport = trial.shell_pid1_transport(prior_args, p['system'], uart_progress=True, uart_progress_breadcrumbs=True)
assert p['transport'] == 'setenv bootargs "' + p['bootargs'].removeprefix('bootargs=') + '"'
assert len(p['transport'].encode()) < 512
transport_path.write_text(p['transport'] + '\n')
private_path.write_text(json.dumps({**p, 'bundle': str(p['bundle'])}, indent=2) + '\n')
public = {
    'schema': 'k230-uart-progress-post-sample-positive-host-v1',
    'evidence_class': 'actual-host-artifact-preparation-only',
    'started_utc': started, 'completed_utc': datetime.now(timezone.utc).isoformat(),
    'controller_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
    'frozen_root_revision': revision, 'matching_build_returncode': build['returncode'],
    'bundle': str(bundle), 'system': p['system'], 'files': manifest['files'],
    'kernel_proof': p['uart_progress_kernel'], 'post_sample_proof': p['uart_progress_post_sample_kernel'],
    'archive_proof': p['shell_comparison'], 'bootargs': p['bootargs'],
    'literal_transport_bytes': len(p['transport'].encode()), 'prior_literal_transport_bytes': len(prior_transport.encode()),
    'sole_additional_gate': trial.UART_PROGRESS_POST_SAMPLE_FLAG,
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
print('Actual PostSample host preparation passed; private manifest and safe receipt saved.')
print('Bundle:', bundle)
print('Literal transport bytes:', public['literal_transport_bytes'])
