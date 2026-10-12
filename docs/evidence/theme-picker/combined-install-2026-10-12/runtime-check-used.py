import fcntl,importlib.util,json,os,re,shlex,sys,threading,time,urllib.parse,uuid
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import serial
os.umask(0o077)
wt=Path.home()/'tmp/k230-theme-board-2026-10-12';d=Path.home()/'tmp/k230-theme-board-run-2026-10-12';e=wt/'docs/evidence/theme-picker/combined-install-2026-10-12';mode=sys.argv[1];assert mode in ('candidate','ordinary')
spec=importlib.util.spec_from_file_location('rd',wt/'tools/mainline-drm-initrd-shell-trial.py');rd=importlib.util.module_from_spec(spec);spec.loader.exec_module(rd)
state=json.loads((d/'state.json').read_text());token=uuid.uuid4().hex
class H(BaseHTTPRequestHandler):
 def do_POST(self):
  if self.path!='/'+token+'/'+mode+'-runtime.json':self.send_error(404);return
  size=int(self.headers.get('Content-Length','0'))
  if not 0<size<32768:self.send_error(413);return
  data=self.rfile.read(size);json.loads(data)
  (e/(mode+'-runtime.json')).write_bytes(data);self.send_response(200);self.end_headers();self.wfile.write(b'OK\n')
 def log_message(self,*args):pass
srv=ThreadingHTTPServer(('0.0.0.0',0),H);threading.Thread(target=srv.serve_forever,daemon=True).start()
host=urllib.parse.urlsplit((Path.home()/'tmp/k230-coordination/transfer-url.private.txt').read_text().strip()).hostname
endpoint=f'http://{host}:{srv.server_address[1]}/{token}'
with open('/tmp/k230-board.lock','a') as lock,(d/(mode+'-runtime-'+uuid.uuid4().hex+'.private.log')).open('xb',buffering=0) as log:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);s=rd.PrivateSession(serial,log)
 try:
  s.write(b'\r');assert s.wait_for(b'root@nixos',20),'no root prompt'
  s.upload_text('/run/k230-mainline-theme-expected.json',(d/'expected.json').read_text(),token)
  s.upload_text('/run/k230-mainline-theme-runtime.py',(e/'inspect-runtime.py').read_text(),token)
  marker='K230_THEME_RUNTIME_RC_'+uuid.uuid4().hex
  cmd=shlex.join([rd.BOARD_PYTHON,'-I','/run/k230-mainline-theme-runtime.py',state['stage'],endpoint,mode])
  s.line(cmd+"; printf '\n"+marker+"=%s\n' $?",interrupt=False)
  end=time.monotonic()+150;m=None
  while time.monotonic()<end and not m:s.pump();m=re.search(rb'\n'+marker.encode()+rb'=([0-9]+)\r?\n',s.buffer)
  assert m and int(m[1])==0,'runtime guard failed; private UART retained'
  assert b'K230_THEME_RUNTIME_PASS' in s.buffer and (e/(mode+'-runtime.json')).exists()
  report=json.loads((e/(mode+'-runtime.json')).read_text());assert report['result']=='PASS'
  before=json.loads((e/('preflight.json' if mode=='candidate' else 'candidate-runtime.json')).read_text());assert report['boot_id']!=before['boot_id'],'fresh boot not observed'
  print('PASS:',mode,'exact userspace/boot/output identities, active services, retained appearance',flush=True)
 finally:s.close();srv.shutdown()
