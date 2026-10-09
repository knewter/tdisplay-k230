#!/usr/bin/env python3
"""Install a touch-qualified coherent boot bundle, retaining root rollback.

Runs on the reserved board. It preserves stage 1 and DT selectors. The boot
partition may require removing an old payload before its replacement fits;
the checked root backup and installation journal remain available throughout.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

BOOT = Path('/boot')
PROFILE = Path('/nix/var/nix/profiles/system')
MUTABLE = ('Image', 'initrd.uimg', 'k230-tdisplay.dtb', 'bootargs.txt')
PROTECTED = ('fw_jump_add_uboot_head.bin', 'force_dtb', 'lcd_dtb', 'hdmi_dtb')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def appearance():
    selection = Path('/home/shell/.local/state/omarchy/current/active')
    if not selection.exists() and not selection.is_symlink():
        return dict(generation=None, report_sha256=None)
    active = selection.resolve(strict=True)
    report = active / 'report.json'
    return dict(generation=active.name, report_sha256=digest(report) if report.exists() else None)


def validate_qualification(q, candidate):
    require(q.get('evidence_class') == 'operator-real-finger-report', 'operator evidence missing')
    for field in ('system', 'kernel', 'bundle'):
        require(q.get(field) == candidate[field], 'qualified ' + field + ' differs')
    require(q.get('shell_executable', '').startswith('/nix/store/'), 'qualified shell identity missing')
    require(q.get('checks') == {'home_to_all_apps': True, 'bottom_handle_to_overview': True,
                               'terminal_open_and_return': True}, 'navigation not accepted')


def save(path, value):
    temporary = path.with_name(path.name + '.new')
    with temporary.open('w') as stream:
        json.dump(value, stream, indent=2); stream.write('\n')
        stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)
    os.sync()


def replace_payload(source, target, expected):
    """Use rename when space permits; otherwise use the root-backed gap."""
    require(source.is_file() and digest(source) == expected, 'source payload differs')
    require(target.name in MUTABLE, 'refusing an unrelated boot file')
    require(not target.is_symlink(), 'boot payload must be a regular file')
    if target.exists() and digest(target) == expected:
        return 'unchanged'
    temporary = target.with_name(target.name + '.k230-new')
    require(not temporary.exists(), 'unfinished payload exists; inspect journal before recovery')
    size = source.stat().st_size
    free = shutil.disk_usage(target.parent).free
    old_size = target.stat().st_size if target.exists() else 0
    require(free + old_size > size + 1024**2, 'insufficient boot space even after replacement')
    method = 'atomic-rename'
    if free < size + 1024**2:
        require(target.name in ('Image', 'initrd.uimg'), 'small boot file unexpectedly lacks space')
        target.unlink(missing_ok=True); os.sync()
        method = 'root-backed-replacement'
    with source.open('rb') as inp, temporary.open('xb') as out:
        shutil.copyfileobj(inp, out, 1024**2); out.flush(); os.fsync(out.fileno())
    os.chmod(temporary, 0o644)
    require(digest(temporary) == expected, 'copied boot payload differs')
    os.replace(temporary, target); os.sync()
    require(digest(target) == expected, 'installed boot payload differs')
    return method


def preserve_rollback_roots(stage, state):
    args = (stage / 'backup/bootargs.txt').read_text()
    init = [v for v in args.removeprefix('bootargs=').split() if v.startswith('init=')]
    require(len(init) == 1 and init[0].endswith('/init'), 'normal init selector is ambiguous')
    old_system = init[0][len('init='):-len('/init')]
    for label, system in [('rollback-profile-root', state['normal_profile']),
                          ('rollback-init-root', old_system)]:
        require(re.fullmatch(r'/nix/store/[a-z0-9]{32}-nixos-system-[A-Za-z0-9._+-]+', system),
                'invalid rollback system path')
        subprocess.run(['nix-store', '--check-validity', system], check=True)
        subprocess.run(['nix-store', '--add-root', str(stage / label), '-r', system],
                       check=True, stdout=subprocess.DEVNULL)
    return old_system


def install(stage, qualification):
    require(not (stage / 'install-result.json').exists(), 'installation already recorded')
    filename = Path(__file__).with_name('stage.py')
    if not filename.exists():
        filename = Path(__file__).with_name('coherent-shell-board-stage.py')
    spec = importlib.util.spec_from_file_location('stage_tool', filename)
    tool = importlib.util.module_from_spec(spec); spec.loader.exec_module(tool)
    state = tool.check(stage); candidate = state['candidate']
    q = json.loads(qualification.read_text()); validate_qualification(q, candidate)
    require(str(Path('/run/current-system').resolve()) == candidate['system'], 'candidate is not running')
    require(str(Path('/run/booted-system/kernel').resolve()) == candidate['kernel'], 'matching kernel is not booted')
    args = Path('/proc/cmdline').read_text().split()
    require([v for v in args if v.startswith('init=')] == ['init=' + candidate['system'] + '/init'],
            'matching candidate init is not booted')
    pid = int(subprocess.check_output(['systemctl', 'show', 'shell-ui', '-p', 'MainPID', '--value'], text=True))
    require(os.readlink('/proc/' + str(pid) + '/exe') == q['shell_executable'], 'unqualified shell executable')
    old_system = preserve_rollback_roots(stage, state)
    journal = dict(phase='rollback-protected', system=candidate['system'],
                   normal_profile=state['normal_profile'], normal_boot_system=old_system,
                   before=state['normal_files'], appearance_before=appearance(), methods={},
                   qualification_sha256=digest(qualification), started_epoch_s=time.time())
    save(stage / 'install-state.json', journal)
    try:
        # Keep the old explicit init selector until all payloads are durable.
        for name in MUTABLE:
            journal['phase'] = 'replacing-' + name; save(stage / 'install-state.json', journal)
            journal['methods'][name] = replace_payload(stage / name, BOOT / name,
                                                     candidate['boot_files'][name]['sha256'])
        for name in PROTECTED:
            require(tool.identity(BOOT / name) == state['normal_files'][name], 'protected boot file changed')
        subprocess.run(['nix-env', '--profile', str(PROFILE), '--set', candidate['system']],
                       check=True, capture_output=True)
        require(str(PROFILE.resolve()) == candidate['system'], 'persistent profile not selected')
        require(not Path('/nix-path-registration').exists(), 'bootstrap registration unexpectedly present')
        journal.update(phase='installed', after={n: tool.identity(BOOT / n) for n in tool.NORMAL_FILES},
                       profile_after=str(PROFILE.resolve()), appearance_after=appearance(),
                       result='PASS', ordinary_boot_verified=False)
        save(stage / 'install-state.json', journal); save(stage / 'install-result.json', journal)
        return journal
    except BaseException:
        journal['phase'] = 'interrupted-or-failed'; save(stage / 'install-state.json', journal)
        raise


def rollback(stage):
    state = json.loads((stage / 'state.json').read_text())
    require(not Path('/nix-path-registration').exists(), 'bootstrap profile replacement present')
    for name, expected in state['normal_files'].items():
        require(digest(stage / 'backup' / name) == expected['sha256'], 'rollback backup differs: ' + name)
    for name in PROTECTED:
        require(digest(BOOT / name) == state['normal_files'][name]['sha256'], 'protected file differs: ' + name)
    methods = {}
    for name in MUTABLE:
        temporary = (BOOT / name).with_name(name + '.k230-new')
        # This suffix is exclusively owned by this installer; its backup was
        # verified above before removing a possibly interrupted copy.
        temporary.unlink(missing_ok=True)
        methods[name] = replace_payload(stage / 'backup' / name, BOOT / name,
                                       state['normal_files'][name]['sha256'])
    subprocess.run(['nix-env', '--profile', str(PROFILE), '--set', state['normal_profile']],
                   check=True, capture_output=True)
    require(str(PROFILE.resolve()) == state['normal_profile'], 'normal profile not restored')
    result = dict(result='PASS', phase='rollback-files-restored', methods=methods,
                  profile=str(PROFILE.resolve()), physical_restoration_verified=False)
    save(stage / 'rollback-result.json', result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=('install', 'rollback'))
    p.add_argument('stage', type=Path)
    p.add_argument('--qualification', type=Path)
    args = p.parse_args(); os.umask(0o077)
    require(re.fullmatch(r'/var/lib/k230/coherent-boot/[a-z0-9-]+', str(args.stage)), 'invalid staging path')
    if args.mode == 'install':
        require(args.qualification is not None, 'qualification required')
        result = install(args.stage, args.qualification)
    else:
        result = rollback(args.stage)
    print('K230_COHERENT_INSTALL ' + json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
