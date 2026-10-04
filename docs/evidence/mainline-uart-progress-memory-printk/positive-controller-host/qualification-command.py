"""Actual NEW MemoryPrintk artifact qualification; run only after root success."""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import types
import zlib

os.umask(0o077)
# Actual selected archive is Zstd; this requires the operator's Python3.14.
from compression import zstd

directory = Path(__file__).resolve().parent
assert directory.stat().st_uid == os.getuid() and directory.stat().st_mode & 0o077 == 0
repo = Path('/home/jadams/tmp/k230-mainline-uart-progress-memory-printk-controller')
root = Path('/home/jadams/tmp/k230-mainline-probe-integration')
board = Path('/home/jadams/tmp/k230-mainline-uart-memory-printk-board')
base_bundle = Path('/nix/store/lznjjfx1kzm8mp2j0r06c87h2vdymkhd-k230-mainline-drm-trial-boot-files')
parser = argparse.ArgumentParser()
parser.add_argument('--bundle', type=Path, required=True)
parser.add_argument('--dev', type=Path, required=True)
parser.add_argument('--normal-report', type=Path, required=True)
args = parser.parse_args()
receipt_path = board / 'full-build-result.private.json'
build = json.loads(receipt_path.read_text())
expected_revision = (directory / 'expected-root-revision.txt').read_text().strip()
assert expected_revision == '1c59f8565ce6baab1e97ffad23e55556961af308'
assert build['returncode'] == 0 and build['revision'] == expected_revision
outputs = [Path(p) for p in build['output_paths']]
assert len(outputs) == len(set(outputs)) and all(p.exists() for p in outputs)
bundle, dev = args.bundle, args.dev
assert bundle in outputs and dev in outputs and bundle != base_bundle
assert bundle.name.endswith('-k230-mainline-drm-trial-boot-files') and dev.name.endswith('-dev')
controller = repo / 'tools/mainline-drm-initrd-shell-trial.py'
frozen = subprocess.check_output(['git', 'show', expected_revision + ':tools/mainline-drm-initrd-shell-trial.py'], cwd=root, text=True)
# Compare only the SAME new frozen controller, never old/new feature domains.
names = {'prepare_trial', 'normal_expectation', 'prepare_uart_progress', 'prepare_shell_comparison',
         'inspect_shell_initrd', 'inspect_uart_progress_kernel', 'inspect_uart_memory_kernel',
         'prepare_uart_memory_printk', 'shell_pid1_bootargs', 'shell_pid1_transport',
         'validate_uart_memory_selector', 'validate_uart_memory_no_stimulus_selector',
         'validate_uart_memory_printk_selector', 'observe_uart_progress', 'finish_uart_progress',
         'uart_memory_summary', 'uart_memory_printk_summary', 'linux_console_prefix', 'linux_console_backend'}
constants = {'SHELL_CONTROLS', 'SHELL_TRACE_FLAGS', 'NORMAL_WRAPPER_CRC32', 'UART_PROGRESS_FLAG',
             'UART_PROGRESS_MEMORY_FLAG', 'UART_MEMORY_FORMAT', 'UART_MEMORY_SOURCE_SHA256',
             'UART_MEMORY_PRINTK_FLAG', 'UART_MEMORY_PRINTK_FORMAT', 'UART_MEMORY_PRINTK_SOURCE_SHA256'}
def definitions(text):
    result = {}
    for n in ast.parse(text).body:
        if isinstance(n, ast.FunctionDef) and n.name in names:
            result[n.name] = ast.dump(n, include_attributes=False)
        elif isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and n.targets[0].id in constants:
            result[n.targets[0].id] = ast.dump(n.value, include_attributes=False)
    assert set(result) == names | constants
    return result
assert definitions(controller.read_text()) == definitions(frozen)
spec = importlib.util.spec_from_file_location('memory_printk_positive_host', controller)
trial = importlib.util.module_from_spec(spec); sys.modules[spec.name] = trial; spec.loader.exec_module(trial)
normal_path, manifest_path = directory / 'normal-report.json', directory / 'candidate-manifest.json'
private_path, public_path = directory / 'prepared.private.json', directory / 'positive-host-receipt.json'
transport_path = directory / 'transport.private.txt'
assert all(not p.exists() for p in (normal_path, manifest_path, private_path, public_path, transport_path))
assert args.normal_report.is_file() and not args.normal_report.is_symlink()
shutil.copyfile(args.normal_report, normal_path)
report = json.loads(normal_path.read_text())
manifest = {'system': str((bundle / 'system').resolve(strict=True)), 'files': {}}
for name, *_ in trial.LOADS:
    if name == 'fw_jump_add_uboot_head.bin':
        manifest['files'][name] = {**report['boot_files'][name], 'crc32': trial.NORMAL_WRAPPER_CRC32}
    else:
        content = (bundle / name).read_bytes()
        manifest['files'][name] = {'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest(), 'crc32': f'{zlib.crc32(content):08x}'}
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
started = datetime.now(timezone.utc).isoformat()
trial.validate_uart_memory_printk_selector(True, True, True, True, True, 'minimal', False)
p = trial.prepare_uart_memory_printk(trial.prepare_trial(manifest_path, bundle, normal_path))
assert Path(p['uart_progress_kernel']['config']) == dev / 'lib/modules/7.3.0-rc5/build/.config'
assert p['uart_progress_memory_kernel']['source'] == '/nix/store/0l4mgw9hr1j7pj247jsrxjd478fnlfy8-linux-mainline-k230-uart-progress-memory-printk-src'
assert p['uart_progress_memory_kernel']['worker_sha256'] == '30e8eb1ee365d62665c9d3ffd674e973736f3d04405d53f0f5dc12c3ee23f5f2'
base_receipt = json.loads((repo / 'docs/evidence/mainline-uart-progress-memory/no-stimulus-host/result.json').read_text())
assert p['uart_progress_kernel']['config_sha256'] == base_receipt['kernel_proof']['config_sha256']
assert p['shell_comparison']['loader_sha256'] == base_receipt['archive_proof']['loader_sha256']
assert p['shell_comparison']['bash'] == base_receipt['archive_proof']['bash']
for name, info in p['shell_comparison']['executables'].items():
    assert info == base_receipt['archive_proof']['executables'][name]
# Reconstruct the base transform for the NEW selected system, then only newgate.
base_args = trial.shell_pid1_bootargs((bundle / 'bootargs.txt').read_text(), p['system']) + ' ' + trial.UART_PROGRESS_FLAG + ' ' + trial.UART_PROGRESS_MEMORY_FLAG
assert p['bootargs'].split() == base_args.split() + [trial.UART_MEMORY_PRINTK_FLAG]
assert not any(x.split('=', 1)[0] in ('nohlt', 'hlt', 'earlycon', 'keep_bootcon', 'quiet') for x in p['bootargs'].split())
assert p['uart_progress_memory_no_stimulus'] is True and p['uart_progress_memory_printk'] is True
base_transport = trial.shell_pid1_transport(base_args, p['system'], uart_progress=True, uart_progress_memory=True)
assert len(p['transport'].encode()) < 512 and len(p['transport'].encode()) - len(base_transport.encode()) == len(trial.UART_MEMORY_PRINTK_FLAG) + 1
assert p['transport'] == 'setenv bootargs "' + p['bootargs'].removeprefix('bootargs=') + '"'
# Match artifact chosen args and compare actual hardware DT modulo sole bootargs.
def chosen(path):
    return subprocess.check_output(['fdtget', '-t', 's', str(path), '/chosen', 'bootargs'], text=True, timeout=20).strip()
def hardware(path):
    output = subprocess.check_output(['dtc', '-I', 'dtb', '-O', 'dts', str(path)], stderr=subprocess.PIPE, timeout=20)
    normalized, count = re.subn(rb'(?m)^[ \t]*bootargs = "[^\n]*";\n', b'', output)
    assert count == 1
    return normalized
new_dtb = bundle / 'k230-tdisplay-mainline-drm.dtb'
old_dtb = base_bundle / new_dtb.name
assert chosen(new_dtb) == (bundle / 'bootargs.txt').read_text().strip().removeprefix('bootargs=')
assert chosen(old_dtb) == (base_bundle / 'bootargs.txt').read_text().strip().removeprefix('bootargs=')
hardware_bytes = hardware(new_dtb)
assert hardware_bytes == hardware(old_dtb), 'selected hardware DT changed beyond chosen bootargs'
subprocess.run(['sha256sum', '--check', 'SHA256SUMS'], cwd=bundle, check=True, capture_output=True, timeout=30)
transport_path.write_text(p['transport'] + '\n')
private_path.write_text(json.dumps({**p, 'bundle': str(bundle)}, indent=2) + '\n')
public = {
    'schema': 'k230-uart-progress-memory-printk-positive-host-v1',
    'evidence_class': 'actual-new-host-artifact-preparation-only',
    'started_utc': started, 'completed_utc': datetime.now(timezone.utc).isoformat(),
    'controller_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
    'controller_source_sha256': hashlib.sha256(controller.read_bytes()).hexdigest(),
    'frozen_root_revision': expected_revision, 'matching_full_build_returncode': build['returncode'],
    'bundle': str(bundle), 'system': p['system'], 'dev': str(dev), 'files': manifest['files'],
    'kernel_proof': p['uart_progress_kernel'], 'memory_printk_proof': p['uart_progress_memory_printk_kernel'],
    'archive_proof': p['shell_comparison'], 'bootargs': p['bootargs'],
    'literal_transport_bytes': len(p['transport'].encode()), 'base_selected_memory_literal_transport_bytes': len(base_transport.encode()),
    'sole_added_gate': trial.UART_MEMORY_PRINTK_FLAG, 'poll_idle_selected': False,
    'controller_input_policy': 'zero-candidate-input', 'receipt_status_planned': 'NOT_REQUESTED', 'rx_status_planned': 'NOT_TESTED',
    'same_ast_as_frozen_new_root': True, 'same_config_as_base_memory': True,
    'actual_hardware_DTB_equal_except_chosen_bootargs': True,
    'normalized_hardware_DTB_sha256': hashlib.sha256(hardware_bytes).hexdigest(),
    'same_archived_executables_and_loader_as_base_memory': True,
    'load_ranges_and_hashes_and_CRCs_validated': True, 'bundle_SHA256SUMS_passed': True,
    'protected_wrapper_anchored_to_prior_normal_report_and_crc': True,
    'registration_absence_assertion_in_prepost_helper': "assert not Path('/nix-path-registration').exists() and not Path('/nix-path-registration').is_symlink()" in p['helper_text'],
    'manifest_sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    'full_build_receipt_sha256': hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
    'qualification_command_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'uart_opened': False, 'board_commands_sent': False, 'implicit_build_performed': False,
    'performed_protected_board_preflight': False, 'physical_result': 'UNVERIFIED',
}
assert public['registration_absence_assertion_in_prepost_helper']
public_path.write_text(json.dumps(public, indent=2) + '\n')
print('Actual NEW MemoryPrintk host qualification passed; no UART/build.')
print('Bundle:', bundle)
print('Literal transport bytes:', public['literal_transport_bytes'])
