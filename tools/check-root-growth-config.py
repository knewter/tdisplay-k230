#!/usr/bin/env python3
"""Evaluate growth selection/ordering; this does not prove disk mutation or boot."""
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
expr = 'let f=builtins.getFlake '+json.dumps(str(root))+''';
  b=f.nixosConfigurations.k230.config;
  q=f.nixosConfigurations.k230-qemu.config;
  r=f.nixosConfigurations.k230-rvv-trial.config;
  s=b.systemd.services.k230-root-growth;
in {
  enabled=b.k230.rootGrowth.enable;
  qemuHasService=q.systemd.services ? k230-root-growth;
  rvvEnabled=r.k230.rootGrowth.enable;
  package=f.packages.x86_64-linux.root-growth.outPath;
  rootDevice=b.fileSystems."/".device;
  stockPartitionGrowth=b.boot.growPartition;
  independentFilesystemGrowth=b.fileSystems."/".autoResize;
  wantedBy=s.wantedBy; requiredBy=s.requiredBy; requires=s.requires;
  after=s.after; before=s.before; service=s.serviceConfig;
}'''
d = json.loads(subprocess.check_output(['nix', 'eval', '--impure', '--json', '--expr', expr], cwd=root, text=True))
assert d['enabled'] and d['rvvEnabled'] and not d['qemuHasService']
assert d['rootDevice'] == '/dev/disk/by-label/NIXOS_SD'
assert not d['stockPartitionGrowth'] and not d['independentFilesystemGrowth']
assert d['wantedBy'] == ['multi-user.target'] and not d['requiredBy'] and not d['requires']
assert 'local-fs.target' in d['after'] and 'shell.service' in d['before']
s = d['service']
assert s['Type'] == 'oneshot' and s['RemainAfterExit']
assert s['ExecStart'] == d['package']+'/bin/k230-root-growth --apply'
assert s['TimeoutStartSec'] == '180s' and s['KillMode'] == 'control-group'
print(json.dumps({'status': 'PASS', 'evidence_class': 'host-Nix-configuration-evaluation', 'configuration': d}, indent=2))
