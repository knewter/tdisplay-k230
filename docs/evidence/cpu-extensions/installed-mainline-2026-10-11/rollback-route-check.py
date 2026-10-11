#!/usr/bin/env python3
"""Read-only board check that the theme installer's rollback route is intact.

Mirrors coherent-shell-board-install.py rollback() preconditions without any
write: rollback roots valid, staged backups match their recorded hashes and
protected /boot files unchanged. It performs no recovery.
"""
import hashlib, json, os, subprocess, sys
from pathlib import Path

STAGE = Path('/var/lib/k230/coherent-boot/925i44g1rmqyjcbz8hziyz3vvkx95waf-20261010')
PROTECTED = ('fw_jump_add_uboot_head.bin', 'force_dtb', 'lcd_dtb', 'hdmi_dtb')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


state = json.loads((STAGE / 'state.json').read_text())
report = {'stage': str(STAGE), 'current_system': os.path.realpath('/run/current-system'),
          'profile': os.path.realpath('/nix/var/nix/profiles/system'),
          'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
          'normal_profile_recorded': state['normal_profile'], 'roots': {}, 'backups': {}, 'protected': {}}
for label in ('rollback-profile-root', 'rollback-init-root'):
    target = os.path.realpath(STAGE / label)
    valid = subprocess.run(['nix-store', '--check-validity', target], capture_output=True).returncode == 0
    report['roots'][label] = {'target': target, 'valid': valid}
for name, expected in state['normal_files'].items():
    report['backups'][name] = sha(STAGE / 'backup' / name) == expected['sha256']
for name in PROTECTED:
    report['protected'][name] = sha(Path('/boot') / name) == state['normal_files'][name]['sha256']
report['status'] = 'PASS' if (all(r['valid'] for r in report['roots'].values())
                              and all(report['backups'].values()) and all(report['protected'].values())
                              and report['roots']['rollback-profile-root']['target'] == state['normal_profile']) else 'FAIL'
print('K230_ROLLBACK_ROUTE ' + json.dumps(report, sort_keys=True))
sys.exit(report['status'] != 'PASS')
