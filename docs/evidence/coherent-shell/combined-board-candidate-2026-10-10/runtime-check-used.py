import fcntl, importlib.util, json, os, re, shlex, threading, time, urllib.parse, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import serial
os.umask(0o077)
home=Path.home();d=home/'tmp/k230-coherent-combined-board-2026-10-10';wt=home/'tmp/k230-coherent-closeout-2026-10-10'
e=wt/'docs/evidence/coherent-shell/combined-board-candidate-2026-10-10'
spec=importlib.util.spec_from_file_location('rd',wt/'tools/mainline-drm-initrd-shell-trial.py');rd=importlib.util.module_from_spec(spec);spec.loader.exec_module(rd)
state=json.loads((d/'state.json').read_text());token=uuid.uuid4().hex
class H(BaseHTTPRequestHandler):
 def do_POST(self):
  name=self.path.removeprefix('/'+token+'/')
  if self.path!='/'+token+'/'+name or name not in ['help-native.png','runtime.json']: self.send_error(404);return
  size=int(self.headers.get('Content-Length','0'))
  if not 0<size<4*1024**2:self.send_error(413);return
  data=self.rfile.read(size)
  if len(data)!=size:self.send_error(400);return
  (e/name).write_bytes(data);self.send_response(200);self.end_headers();self.wfile.write(b'OK\n')
 def log_message(self,*a):pass
srv=ThreadingHTTPServer(('0.0.0.0',0),H);threading.Thread(target=srv.serve_forever,daemon=True).start()
host=urllib.parse.urlsplit((home/'tmp/k230-coordination/transfer-url.private.txt').read_text().strip()).hostname
endpoint=f'http://{host}:{srv.server_address[1]}/{token}'
with open('/tmp/k230-board.lock','a') as lock,(d/'runtime-uart.private.log').open('xb',buffering=0) as log:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);s=rd.PrivateSession(serial,log)
 try:
  s.write(b'\r');assert s.wait_for(b'root@nixos',20),'no root prompt'
  marker='K230_COMBINED_RUNTIME_RC_'+uuid.uuid4().hex
  cmd=shlex.join([rd.BOARD_PYTHON,'-I','/root/tmp/k230-coherent-combined-20261010/inspect-runtime.py',state['stage'],endpoint])
  s.line(cmd+"; printf '\\n"+marker+"=%s\\n' $?",interrupt=False)
  end=time.monotonic()+120;m=None
  while time.monotonic()<end and not m:
   s.pump();m=re.search(rb'\n'+marker.encode()+rb'=([0-9]+)\r?\n',s.buffer)
  assert m and int(m[1])==0,'runtime check failed or completion unknown'
  assert (e/'runtime.json').is_file() and (e/'help-native.png').is_file()
  report=json.loads((e/'runtime.json').read_text());assert report['boot_id']==json.loads((d/'candidate/serial-result.json').read_text())['observed']['boot_id']
  print('runtime check PASS; native Help and identities saved',flush=True)
 finally:s.close();srv.shutdown()
