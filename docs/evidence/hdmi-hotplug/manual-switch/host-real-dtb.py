#!/usr/bin/env python3
"""Exercise the controller with real compiled DTBs, mocked mounts/reboot only."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location('display_switch', root / 'tools/display_switch.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--bundle', type=Path, required=True)
parser.add_argument('--panel', type=Path, required=True)
parser.add_argument('--hdmi', type=Path, required=True)
args = parser.parse_args()
bundle = args.bundle.resolve(strict=True)
identity = json.loads((bundle / 'identity.json').read_text())
fdtput = bundle / 'inspect-tools/fdtput'
commands = []
with tempfile.TemporaryDirectory(prefix='k230-display-host-') as directory:
    fixture = Path(directory)
    boot = fixture / 'boot'
    boot.mkdir()
    for name in ('Image', 'k230-tdisplay.dtb', 'bootargs.txt'):
        (boot / name).write_bytes((bundle / name).read_bytes())
    (boot / 'force_dtb').write_text(module.PANEL)
    current = fixture / 'current'
    current.symlink_to(identity['system'])
    drm = fixture / 'drm'
    (drm / 'card1-DSI-1').mkdir(parents=True)
    (drm / 'card1-DSI-1/status').write_text('connected\n')
    def run(command, **kwargs):
        if command[0] == str(fdtput):
            return subprocess.run(command, **kwargs)
        commands.append(command[:3])
        if command[0] == 'MOCK-systemctl':
            assert (boot / module.MARKER).exists()
            assert (boot / 'force_dtb').read_text() == module.HDMI
            assert (boot / module.PANEL).read_bytes() == (bundle / module.PANEL).read_bytes()
        return subprocess.CompletedProcess(command, 0)
    controller = module.DisplaySwitch(dict(kernel=identity['kernel'], panel=str(args.panel),
        hdmi=str(args.hdmi), mount='MOCK-mount', systemctl='MOCK-systemctl', fdtput=str(fdtput)),
        boot, current, drm, fixture / 'lock', run)
    controller.mutate('hdmi')
    selected_hdmi_sha = module.digest(boot / module.HDMI)
    bootargs = subprocess.check_output([str(bundle / 'inspect-tools/fdtget'), str(boot / module.HDMI), '/chosen', 'bootargs'], text=True).strip()
    assert bootargs == identity['bootargs']
    assert controller.mutate('restore')
    assert (boot / 'force_dtb').read_text() == module.PANEL
    assert not (boot / module.MARKER).exists()
    assert not controller.mutate('restore')
    assert commands == [ ['MOCK-mount','-o','remount,rw'], ['MOCK-mount','-o','remount,ro'],
        ['MOCK-systemctl','reboot','--no-block'], ['MOCK-mount','-o','remount,rw'], ['MOCK-mount','-o','remount,ro'] ]
print(json.dumps(dict(result='PASS', evidence_class='host real DTBs with mocked mount/reboot',
    bundle=str(bundle), system=identity['system'], kernel=identity['kernel'],
    source_panel_sha256=module.digest(args.panel), source_hdmi_sha256=module.digest(args.hdmi),
    selected_hdmi_sha256=selected_hdmi_sha, panel_payload_unchanged=True, restored_selector=module.PANEL,
    marker_removed=True, board_touched=False), indent=2))
