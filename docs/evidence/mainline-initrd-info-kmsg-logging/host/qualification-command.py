"""Fixed actual-artifact qualification; copy into a fresh 0700 ~/tmp directory.

No UART or build. Requires host Python 3.14 native zstd and fdtget.
Only safe result.json may be published; other generated files remain private.
"""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

os.umask(0o077)
d = Path(__file__).resolve().parent
assert d.stat().st_uid == os.getuid() and d.stat().st_mode & 0o077 == 0
repo = Path.home() / 'tmp/k230-mainline-probe-integration'
previous = Path.home() / 'tmp/k230-mainline-current-p2-initrd-info-20261005'
fullpath = Path.home() / 'tmp/k230-mainline-uart-memory-printk-board/full-build-result.private.json'
controller = repo / 'tools/mainline-drm-system-trial.py'
EXPECTED_SOURCE_SHA256 = 'f5f23057119cb79228ebb868e7f92524a6f9a6f230b9931d438013d34b8da0c5'
assert hashlib.sha256(controller.read_bytes()).hexdigest() == EXPECTED_SOURCE_SHA256
parser = argparse.ArgumentParser()
parser.add_argument('--bundle', type=Path, required=True)
parser.add_argument('--dev', type=Path, required=True)
parser.add_argument('--normal-report', type=Path, required=True)
a = parser.parse_args()
assert str(a.bundle) == '/nix/store/p2kdar89q7dhwdajjy0mrhmxxzcgsalw-k230-mainline-drm-trial-boot-files'
assert str(a.dev) == '/nix/store/24hbalyljs6gn6fzkkl24znv8a0x6jdl-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-dev'
full = json.loads(fullpath.read_text())
assert full['returncode'] == 0 and full['revision'] == '1c59f8565ce6baab1e97ffad23e55556961af308'
assert str(a.bundle) in full['output_paths'] and str(a.dev) in full['output_paths']
assert a.normal_report.is_file() and not a.normal_report.is_symlink()
assert a.normal_report.stat().st_uid == os.getuid() and a.normal_report.stat().st_mode & 0o077 == 0
recovery = json.loads((previous / 'reset-armed-normal-result.json').read_text())
before, after = recovery['normal_preflight'], recovery['normal_postflight']
assert before['boot_id'] != after['boot_id']
assert all(before[key] == after[key] for key in ('system', 'profile', 'kernel', 'uname', 'init'))
assert before['boot_files'] == after['boot_files'] and len(after['boot_files']) == 8
assert after['services'] == ['active'] * 3 and after['nix_path_registration_absent']
anchor = json.loads(a.normal_report.read_text())
assert anchor['boot_id'] == after['boot_id']
assert all(anchor[key] == after[key] for key in ('system', 'profile', 'kernel', 'services'))
assert {name: item['sha256'] for name, item in anchor['boot_files'].items()} == after['boot_files']
normal, manifest = d / 'normal-report.json', d / 'candidate-manifest.json'
assert all(not (d / name).exists() for name in ('normal-report.json', 'candidate-manifest.json', 'prepared.private.json', 'result.json'))
shutil.copyfile(a.normal_report, normal)
shutil.copyfile(previous / 'candidate-manifest.json', manifest)
started = dt.datetime.now(dt.timezone.utc).isoformat()
spec = importlib.util.spec_from_file_location('initrd_debug_actual', controller)
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)
artifact = t.rd.prepare_uart_memory_printk(t.rd.prepare_trial(manifest, a.bundle, normal))
old = json.loads((repo / 'docs/evidence/mainline-uart-progress-memory-printk/positive-controller-host/result.json').read_text())
for current, previous_key in (('uart_progress_kernel', 'kernel_proof'), ('uart_progress_memory_printk_kernel', 'memory_printk_proof'), ('shell_comparison', 'archive_proof')):
    assert artifact[current] == old[previous_key]
assert Path(artifact['uart_progress_kernel']['config']) == a.dev / 'lib/modules/7.3.0-rc5/build/.config'
assert hashlib.sha256(manifest.read_bytes()).hexdigest() == old['manifest_sha256']
p = t.prepare(a.bundle, manifest, normal, wait_initramfs_in_initcall=True,
              without_boot_markers=True, initrd_info_kmsg_logging=True)
baseline = t.prepare(a.bundle, manifest, normal, wait_initramfs_in_initcall=True,
                     without_boot_markers=True)
suffix = ' rd.systemd.log_level=info rd.systemd.log_target=kmsg'
assert p['bootargs'] == baseline['bootargs'] + suffix
info = t.prepare(a.bundle, manifest, normal, wait_initramfs_in_initcall=True,
                 without_boot_markers=True, initrd_info_logging=True)
assert p['bootargs'] == info['bootargs'].replace('rd.systemd.log_target=console', 'rd.systemd.log_target=kmsg')
assert len(info['bootargs'].removeprefix('bootargs=').encode()) == 355
assert len(t.volatile_bootargs_command(info).encode()) == 373
assert p['initrd_info_kmsg_logging'] is True
command = t.volatile_bootargs_command(p)
assert len(p['bootargs'].removeprefix('bootargs=').encode()) == 352
assert len(command.encode()) == 370 and len(command.encode()) < 512
assert t.volatile_bootargs_command(baseline) == 'setenv bootargs "' + baseline['bootargs'].removeprefix('bootargs=') + '"'
assert len(t.volatile_bootargs_command(baseline).encode()) == 317
assert all(p[key] == baseline[key] for key in ('manifest', 'normal', 'helper_text', 'system', 'kernel', 'pid1'))
assert p['manifest']['files'] == old['files']
assert p['kernel'] == artifact['uart_progress_kernel']['kernel']
pid1_sha = hashlib.sha256(Path(p['pid1']).read_bytes()).hexdigest()
assert pid1_sha == artifact['shell_comparison']['executables']['init']['sha256']
assert "assert not Path('/nix-path-registration').exists()" in p['helper_text']
assert all(token not in p['bootargs'] for token in ('rdinit=', ' -- ', 'k230.uart_progress', 'k230.boot_trace', 'nohz=', 'nohlt'))
subprocess.run(['sha256sum', '--check', 'SHA256SUMS'], cwd=a.bundle, capture_output=True, check=True, timeout=30)
dt_args = subprocess.check_output(['fdtget', '-t', 's', str(a.bundle / 'k230-tdisplay-mainline-drm.dtb'), '/chosen', 'bootargs'], text=True, timeout=20).strip()
assert dt_args == (a.bundle / 'bootargs.txt').read_text().strip().removeprefix('bootargs=')
(d / 'prepared.private.json').write_text(json.dumps(p, indent=2, default=str) + '\n')
safe = dict(schema='k230-initrd-info-kmsg-logging-actual-host-v1',
    evidence_class='actual-existing-artifact-host-preparation-only',
    started_utc=started, completed_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
    controller_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
    controller_source_sha256=EXPECTED_SOURCE_SHA256,
    qualification_command_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    original_full_build_revision=full['revision'], original_full_build_returncode=0,
    original_full_build_receipt_sha256=hashlib.sha256(fullpath.read_bytes()).hexdigest(),
    bundle=str(a.bundle), system=p['system'], kernel=p['kernel'], dev=str(a.dev),
    files=old['files'], manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
    kernel_proof=artifact['uart_progress_kernel'], memory_printk_artifact_proof=artifact['uart_progress_memory_printk_kernel'],
    archive_proof=artifact['shell_comparison'], pid1=p['pid1'], pid1_sha256=pid1_sha,
    archived_systemd_matches=True, bootargs=p['bootargs'], raw_arguments_bytes=352,
    literal_command_bytes=370, default_marker_free_command_bytes=317,
    sole_policy_transform='rd.systemd.log_target=console -> rd.systemd.log_target=kmsg',
    previous_info_console_raw_arguments_bytes=355, previous_info_console_literal_command_bytes=373, same_artifacts_manifest_loads_normal_helper=True,
    protected_recovery_precedes_host_prepare=True,
    protected_recovery_receipt_sha256=hashlib.sha256((previous / 'reset-armed-normal-result.json').read_bytes()).hexdigest(),
    normal_anchor_class='matches prior independently checked recovery; host preparation is not a new board preflight',
    bundle_SHA256SUMS_passed=True, DT_original_bootargs_match=True,
    uart_opened=False, implicit_build_performed=False, physical_result='UNVERIFIED',
    ordinary_root='UNVERIFIED', panel_glass='UNVERIFIED')
(d / 'result.json').write_text(json.dumps(safe, indent=2) + '\n')
print('Actual initrd info/kmsg preparation PASS: same artifacts, exact352/370 bytes, previous fresh recovery anchor; no UART/build.')
