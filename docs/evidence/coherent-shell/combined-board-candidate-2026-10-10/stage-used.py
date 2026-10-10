"""Deliver the inspected mainline normal bundle and run coherent stage prepare on the board.
No reboot, no boot-file or profile write. URL, address and raw UART stay private."""
import fcntl, hashlib, importlib.util, json, os, re, shlex, subprocess, sys, threading, time, urllib.parse, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import serial
os.umask(0o077)
home = Path.home(); d = home/'tmp/k230-coherent-combined-board-2026-10-10'
wt = home/'tmp/k230-coherent-closeout-2026-10-10'
bundle = (home/'.local/state/tdisplay-k230/retained-builds/coherent-combined-2026-10-10/candidate').resolve(strict=True)
on_board = Path('/nix/store/jsqi00cgac7v773xi3r1zc6ppib3sc7p-k230-coherent-shell-boot-files')
normal = json.loads((wt/'docs/evidence/hdmi-hotplug/live-switch/normal-hotplug-install-serial.json').read_text())['observed']; normal['uname'] = '7.3.0-rc5'
def load(name, f):
    s = importlib.util.spec_from_file_location(name, wt/'tools'/f); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
insp = load('insp', 'coherent-shell-boot-inspect.py'); rd = load('rd', 'mainline-drm-initrd-shell-trial.py')
manifest = insp.inspect(bundle)
assert manifest['host_inspection'] == 'PASS' and manifest['configuration'] == 'k230-mainline-drm-shell'
system = manifest['system']; h = system.split('/')[3][:32]
stage = f'/var/lib/k230/coherent-boot/{h}-20261010'
run = lambda *a: subprocess.run(a, check=True, text=True, capture_output=True).stdout
delta = sorted(set(run('nix-store', '-qR', str(bundle)).split()) - set(run('nix-store', '-qR', str(on_board)).split()))
files = {'manifest.json': (json.dumps(manifest, indent=2) + '\n').encode(),
         'stage.py': (wt/'tools/coherent-shell-board-stage.py').read_bytes(),
         'install.py': (wt/'tools/coherent-shell-board-install.py').read_bytes(),
         'inspect-runtime.py': (wt/'docs/evidence/coherent-shell/combined-board-candidate-2026-10-10/inspect-runtime.py').read_bytes()}
files['delta.nar'] = subprocess.run(['nix-store', '--export', *delta], check=True, capture_output=True).stdout
sums = {k: hashlib.sha256(v).hexdigest() for k, v in files.items()}
(d/'transfer.json').write_text(json.dumps(dict(bundle=str(bundle), on_board=str(on_board), delta_paths=len(delta), sha256=sums, stage=stage), indent=2) + '\n')
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        name = self.path.lstrip('/')
        if name not in files: self.send_error(404); return
        self.send_response(200); self.send_header('Content-Length', str(len(files[name]))); self.end_headers(); self.wfile.write(files[name])
    def log_message(self, *a): pass
class S(ThreadingHTTPServer):
    def handle_error(self, *a): pass
srv = S(('0.0.0.0', 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
host = urllib.parse.urlsplit((home/'tmp/k230-coordination/transfer-url.private.txt').read_text().strip()).hostname
base = f'http://{host}:{srv.server_address[1]}/'
q = shlex.quote; tmp = '/root/tmp/k230-coherent-combined-20261010'
cmds = ['set -euo pipefail', 'umask 077',
    'test "$(readlink -f /run/current-system)" = ' + q(normal['system']),
    'test "$(readlink -f /nix/var/nix/profiles/system)" = ' + q(normal['profile']),
    'test "$(uname -r)" = ' + q(normal['uname']), 'test "$(cat /proc/sys/kernel/random/boot_id)" = ' + q(normal['boot_id']), 'systemctl is-active --quiet shell shell-ui theme-helper',
    'test "$(df --output=avail -B1 /nix/store | tail -n1)" -gt ' + str(len(files['delta.nar']) + 256 * 1024**2),
    'mkdir -p ' + tmp]
for name in files:
    cmds += [f'curl -fsS --max-time 300 {q(base + name)} -o {tmp}/{name}', f"printf '%s  %s\\n' {sums[name]} {tmp}/{name} | sha256sum -c - >/dev/null"]
cmds += [f'nix-store --import < {tmp}/delta.nar >/dev/null',
    f'nix-store --add-root /nix/var/nix/gcroots/k230-coherent-combined-20261010-bundle --realise {q(str(bundle))} >/dev/null',
    f'test ! -e {stage}', 'mkdir -p /var/lib/k230/coherent-boot', f'mkdir -m 700 {stage}']
for name in ('Image', 'initrd.uimg', 'k230-tdisplay.dtb', 'bootargs.txt', 'store-paths'):
    cmds.append(f'cp -- {q(str(bundle) + "/" + name)} {stage}/{name}')
cmds += [f'cp -- {tmp}/{n} {stage}/{n}' for n in ('manifest.json', 'stage.py', 'install.py')]
token = uuid.uuid4().hex
cmds.append(f'{rd.BOARD_PYTHON} -I {stage}/stage.py prepare {stage} --token {token}')
with open('/tmp/k230-board.lock', 'a') as lock, (d/'stage-uart.private.log').open('xb', buffering=0) as log:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    s = rd.PrivateSession(serial, log)
    try:
        s.write(b'\r')
        assert s.wait_for(b'root@nixos', 20), 'no normal root prompt'
        up = uuid.uuid4().hex
        s.upload_text('/run/k230-mainline-coherent-combined-stage.json', json.dumps({'lines': cmds}, indent=1), up)
        prog = 'import json,subprocess; raise SystemExit(subprocess.call(["bash","-c",chr(10).join(json.load(open("/run/k230-mainline-coherent-combined-stage.json"))["lines"])+chr(10)]))'
        marker = 'K230_DEFAULT_STAGE_RC_' + token
        s.line(rd.BOARD_PYTHON + ' -I -c ' + q(prog) + "; printf '\\n" + marker + "=%s\\n' $?", interrupt=False)
        end = time.monotonic() + 900; m = None
        while time.monotonic() < end and not m:
            s.pump(); m = re.search(rb'\n' + marker.encode() + rb'=([0-9]+)\r?\n', s.buffer)
        assert m, 'stage completion unknown'
        text = s.buffer.replace(b'\r\n', b'\n')
        st = []
        if b'K230_COHERENT_STATE {' in text:
            a = text.rindex(b'K230_COHERENT_STATE {') + len(b'K230_COHERENT_STATE ')
            st = [re.sub(rb'[\r\n]', b'', text[a:text.index(b'\nK230_COHERENT_READY', a)])]
        print('rc', int(m[1]), 'state-lines', len(st)); assert int(m[1]) == 0 and len(st) == 1, 'board staging failed or result missing'
        if int(m[1]) == 0 and len(st) == 1:
            (d/'state.json').write_text(json.dumps(json.loads(st[0]), indent=2) + '\n'); print('state.json written', stage)
    finally:
        s.close(); srv.shutdown()
