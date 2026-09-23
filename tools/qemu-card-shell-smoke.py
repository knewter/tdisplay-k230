#!/usr/bin/env python3
"""Boot a system QEMU guest and verify its installed card userspace over UART."""
import argparse
import json
import os
from pathlib import Path
import selectors
import subprocess
import time
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {'two-live-root-and-subsurface-clients', 'deck-drag-expand',
            'keyboard-focus-return', 'close-refusal-timeout', 'graceful-close', 'cancel-back-recovery'}


def guest_command(token):
    # Command echo never contains the complete DONE marker. The result requires
    # two actual guest reports, current random run IDs, and successful teardown.
    return ("if systemctl is-active --quiet card-shell-smoke.service && "
            "test -x /run/current-system/sw/bin/card-shell-guest-smoke; then "
            f"card-shell-guest-smoke --run-id {token} && "
            "systemctl restart card-shell-smoke.service && "
            f"card-shell-guest-smoke --run-id {token}-restart; result=$?; "
            "else echo 'card smoke integration unavailable in this image'; result=69; fi; "
            "if test \"$result\" -ne 0; then tail -n 30 /run/card-shell-smoke/sway.log 2>/dev/null || true; fi; "
            "systemctl stop card-shell-smoke.service || result=70; "
            "if systemctl is-active --quiet card-shell-smoke.service; then result=71; fi; "
            f"printf '\\nK230_CARD_%s %s %s\\n' GUEST_DONE {token} \"$result\"\n")


def check_reports(lines, token):
    reports = []
    for line in lines:
        if line.startswith('K230_CARD_GUEST_RESULT '):
            report = json.loads(line.split(' ', 1)[1])
            if report.get('run_id') in (token, token+'-restart'):
                reports.append(report)
    if {r.get('run_id') for r in reports} != {token, token+'-restart'} or len(reports) != 2:
        raise RuntimeError('missing fresh guest results before/after service restart')
    for report in reports:
        if (report.get('evidence_class') != 'qemu-system-guest-headless-injected' or
            report.get('machine') != 'riscv64' or not isinstance(report.get('uid'), int) or
            report['uid'] <= 0 or set(report.get('passed', [])) != REQUIRED):
            raise RuntimeError('guest result lacks required runtime assertions')
    return reports


def supervise(command, directory, timeout):
    token = uuid.uuid4().hex
    guest = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = bytearray()
    lines = []
    pending = ''
    sent = False
    next_probe = 0
    started = time.monotonic()
    selector = selectors.DefaultSelector()
    selector.register(guest.stdout, selectors.EVENT_READ)
    try:
        while time.monotonic()-started < timeout:
            now = time.monotonic()
            if not sent and now >= next_probe and guest.poll() is None:
                probe = f"printf '\\nK230_CARD_%s\\n' READY_{token}\n"
                guest.stdin.write(probe.encode()); guest.stdin.flush()
                next_probe = now+3
            for key, _ in selector.select(.25):
                chunk = os.read(key.fd, 65536)
                if not chunk:
                    raise RuntimeError('QEMU exited before smoke completion')
                output.extend(chunk)
                if len(output) > 16*1024*1024:
                    raise RuntimeError('guest transcript exceeded 16 MiB bound')
                pending += chunk.decode('utf-8', errors='replace').replace('\r', '')
                while '\n' in pending:
                    line, pending = pending.split('\n', 1)
                    lines.append(line)
                    if line == 'K230_CARD_READY_'+token and not sent:
                        guest.stdin.write(guest_command(token).encode()); guest.stdin.flush()
                        sent = True
                    if line.startswith('K230_CARD_GUEST_DONE '+token+' '):
                        if line != 'K230_CARD_GUEST_DONE '+token+' 0':
                            raise RuntimeError('guest smoke failed: '+line)
                        return check_reports(lines, token)
            if guest.poll() is not None:
                raise RuntimeError('QEMU exited before smoke completion')
        raise RuntimeError('guest smoke timed out; a boot prompt alone is not a pass')
    finally:
        selector.close()
        if guest.poll() is None:
            guest.terminate()
        try:
            guest.wait(timeout=5)
        except subprocess.TimeoutExpired:
            guest.kill(); guest.wait()
        for stream in (guest.stdin, guest.stdout):
            try:
                stream.close()
            except OSError:
                pass
        (directory/'serial.log').write_bytes(output)


def configuration_expr(fixture):
    selection = 'f.nixosConfigurations.k230-qemu'
    if fixture:
        selection = '('+selection+'.extendModules { modules = [ (f.outPath + "/nix/qemu-card-shell-smoke.nix") ]; })'
    return f'let f=builtins.getFlake {json.dumps(str(ROOT))}; s={selection}; in '


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture-image', action='store_true', help='explicit QEMU-only module; does not prove default image integration')
    parser.add_argument('--output', type=Path, help='new or empty evidence directory; default creates a temporary directory')
    parser.add_argument('--timeout', type=int, default=600)
    parser.add_argument('--qemu', default='qemu-system-riscv64')
    parser.add_argument('--no-build', action='store_true', help='require already-realized evaluated artifacts')
    args = parser.parse_args()
    if args.timeout < 1 or args.timeout > 3600:
        parser.error('--timeout must be 1..3600 seconds')
    if args.output is None:
        args.output = Path(tempfile.mkdtemp(prefix='k230-card-qemu-'))
    print('QEMU guest evidence: '+str(args.output), flush=True)
    if args.output.exists() and any(args.output.iterdir()):
        parser.error('--output must be new or empty')
    args.output.mkdir(parents=True, exist_ok=True); args.output.chmod(0o700)
    prefix = configuration_expr(args.fixture_image)
    supported = subprocess.check_output(['nix', 'eval', '--impure', '--json', '--expr', prefix+
        's.config.systemd.services ? card-shell-smoke'], cwd=ROOT, text=True).strip()
    if supported != 'true':
        parser.error('selected k230-qemu image has no card-shell smoke integration; default task 5.1 remains open (use --fixture-image only for explicit tooling validation)')
    paths = {}
    for key, expression in {'kernel': 's.config.system.build.kernel',
                            'initrd': 's.config.system.build.netbootRamdisk',
                            'toplevel': 's.config.system.build.toplevel'}.items():
        if args.no_build:
            command = ['nix', 'eval', '--impure', '--raw', '--expr', prefix+expression+'.outPath']
        else:
            command = ['nix', 'build', '--impure', '--no-link', '--print-out-paths', '--max-jobs', '1', '--cores', '8', '--expr', prefix+expression]
        paths[key] = subprocess.check_output(command, cwd=ROOT, text=True).strip()
    params = json.loads(subprocess.check_output(['nix', 'eval', '--impure', '--json', '--expr', prefix+'s.config.boot.kernelParams'], cwd=ROOT, text=True))
    kernel, initrd = Path(paths['kernel'])/'Image', Path(paths['initrd'])/'initrd'
    if not kernel.is_file() or not initrd.is_file() or not (Path(paths['toplevel'])/'init').is_file():
        raise RuntimeError('selected QEMU image artifacts are not realized')
    command = [args.qemu, '-machine', 'virt', '-m', os.environ.get('MEM', '6G'), '-nographic',
               '-kernel', str(kernel), '-initrd', str(initrd),
               '-append', ' '.join(params)+f" earlycon=sbi init={paths['toplevel']}/init"]
    manifest = {'image_kind': 'explicit-fixture-image' if args.fixture_image else 'selected-qemu-image',
                'artifacts': paths, 'command': command,
                'limits': ['No board boot, panel, real touch, optical or performance acceptance.',
                           'Fixture mode does not satisfy default system-image integration.']}
    (args.output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    reports = supervise(command, args.output, args.timeout)
    if any(r.get('system_toplevel') != paths['toplevel'] for r in reports):
        raise RuntimeError('guest system identity differs from selected artifact')
    if reports[0].get('compositor_pid') == reports[1].get('compositor_pid'):
        raise RuntimeError('guest compositor did not restart')
    if reports[0].get('compositor') != reports[1].get('compositor'):
        raise RuntimeError('guest compositor changed executable across restart')
    result = dict(manifest, status='PASS', evidence_class='qemu-system-guest-headless-injected', reports=reports)
    (args.output/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
