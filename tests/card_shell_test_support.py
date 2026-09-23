"""Run the real cached cross-built compositor; never substitute string checks."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def binaries():
    sway = os.environ.get('CARD_SHELL_SWAY')
    client = os.environ.get('CARD_SHELL_CLIENT')
    if not sway:
        output = subprocess.check_output(['nix', 'eval', '--raw', '.#card-shell.outPath'], cwd=ROOT, text=True)
        wrapper = Path(output) / 'bin/.sway-wrapped'
        if not wrapper.exists():
            raise RuntimeError('Build nix build .#card-shell --max-jobs 1 --cores 8 first, or set CARD_SHELL_SWAY to the unwrapped executable')
        sway = re.search(r'exec (/nix/store/[^ ]+/bin/sway) ', wrapper.read_text()).group(1)
    if not client:
        expr = f'let f=builtins.getFlake {json.dumps(str(ROOT))}; p=import f.inputs.nixpkgs {{system=builtins.currentSystem;}}; in (p.callPackage (f.outPath + "/nix/card-composition-probe-client") {{}}).outPath'
        output = subprocess.check_output(['nix', 'eval', '--impure', '--raw', '--expr', expr], cwd=ROOT, text=True)
        client = str(Path(output) / 'bin/card-composition-probe-client')
        if not Path(client).exists():
            raise RuntimeError('Build the native nix/card-composition-probe-client derivation first, or set CARD_SHELL_CLIENT to its executable')
    return sway, client


def exercise(group, required, disabled=False):
    sway, client = binaries()
    with tempfile.TemporaryDirectory(prefix='card-shell-' + group + '-') as directory:
        command = [sys.executable, str(ROOT / 'tests/card_shell_runtime.py'), '--sway', sway,
                   '--client', client, '--output', directory]
        if disabled:
            command.append('--disabled')
        subprocess.run(command, cwd=ROOT, check=True)
        if not disabled:
            result = json.loads((Path(directory) / 'result.json').read_text())
            assert set(required) <= set(result['passed']), result
            assert result['evidence_class'] == 'headless-qemu-injected-input'
    print(f'PASS {group}: actual Sway/Wayland protocol runtime; physical acceptance remains open')
