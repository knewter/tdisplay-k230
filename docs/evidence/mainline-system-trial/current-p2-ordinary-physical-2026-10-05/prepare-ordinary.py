import datetime as dt, hashlib, importlib.util, json, os, shutil, subprocess
from pathlib import Path
os.umask(0o077)
d = Path(__file__).resolve().parent
repo = Path.home() / 'tmp/k230-mainline-probe-integration'
previous = Path.home() / 'tmp/k230-mainline-autonomous-pid1-board'
recovery = json.loads((previous / 'reset-normal-result.json').read_text())
after = recovery['normal_postflight']
assert after['boot_id'] != recovery['normal_preflight']['boot_id']
assert after['boot_files'] == recovery['normal_preflight']['boot_files']
assert after['services'] == ['active'] * 3 and after['nix_path_registration_absent'] is True
shutil.copyfile(d / 'artifact-qualification/normal-report.json', d / 'normal-report.json')
shutil.copyfile(d / 'artifact-qualification/candidate-manifest.json', d / 'candidate-manifest.json')
assert json.loads((d / 'normal-report.json').read_text())['boot_id'] == after['boot_id']
proof = json.loads((d / 'artifact-qualification/result.json').read_text())
spec = importlib.util.spec_from_file_location('ordinary_prepare', repo / 'tools/mainline-drm-system-trial.py')
t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
p = t.prepare(Path(proof['bundle']), d / 'candidate-manifest.json', d / 'normal-report.json', wait_initramfs_in_initcall=True, without_boot_markers=True)
args = p['bootargs']; command = t.volatile_bootargs_command(p)
assert len(args.removeprefix('bootargs=').encode()) == 299 and len(command.encode()) == 317
assert all(x not in args for x in ('rdinit=', ' -- ', 'k230.uart_progress', 'k230.boot_trace', 'nohz=', 'nohlt'))
assert p['kernel'] == proof['kernel_proof']['kernel']
pid1_sha = hashlib.sha256(Path(p['pid1']).read_bytes()).hexdigest()
assert pid1_sha == proof['archive_proof']['executables']['init']['sha256']
assert p['manifest']['files'] == proof['files']
assert "assert not Path('/nix-path-registration').exists()" in p['helper_text']
source_sha = hashlib.sha256((repo / 'tools/mainline-drm-system-trial.py').read_bytes()).hexdigest()
revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
(d / 'prepared-ordinary.private.json').write_text(json.dumps(p, indent=2, default=str) + '\n')
safe = dict(schema='k230-current-p2-ordinary-host-v1', evidence_class='actual-existing-artifact-host-preparation-only', completed_utc=dt.datetime.now(dt.timezone.utc).isoformat(), controller_revision=revision, controller_source_sha256=source_sha, bundle=proof['bundle'], system=p['system'], kernel=p['kernel'], pid1=p['pid1'], pid1_sha256=pid1_sha, archive_pid1_matches=True, expected_bootargs=args, raw_arguments_bytes=299, literal_command_bytes=317, controls=list(p['diagnostic_controls']), without_boot_markers=True, manifest_files=p['manifest']['files'], protected_normal_recovery_precedes_prepare=True, uart_opened=False, build_performed=False, ordinary_init='NOT_RUN', panel_glass='UNVERIFIED')
(d / 'ordinary-host-result.json').write_text(json.dumps(safe, indent=2) + '\n')
ready = dict(controller_revision=revision, controller_source_sha256=source_sha, protected_normal_recovery_result_sha256=hashlib.sha256((previous / 'reset-normal-result.json').read_bytes()).hexdigest(), normal_recovery='VERIFIED_NEW_OPERATOR_RESET', actual_ordinary_host_prepare='PASS')
(d / 'readiness.private.json').write_text(json.dumps(ready, indent=2) + '\n')
print('Actual ordinary preparation PASS: same artifacts, archived systemd, exact299/317 bytes, fresh protected recovery; no UART/build.')
