import json,socket,struct,time,subprocess

def ipc(command='',kind=0):
 with socket.socket(socket.AF_UNIX) as s:
  s.settimeout(5);s.connect('/run/shell/sway-ipc.sock');b=command.encode();s.sendall(b'i3-ipc'+struct.pack('=II',len(b),kind)+b)
  def read(n):
   b=b''
   while len(b)<n:
    x=s.recv(n-len(b));assert x;b+=x
   return b
  h=read(14);return json.loads(read(struct.unpack('=II',h[6:])[0]))
def windows(n):
 r={n['id']:n['app_id']} if n.get('app_id') else {}
 for c in n.get('nodes',[])+n.get('floating_nodes',[]):r.update(windows(c))
 return r
before=windows(ipc(kind=4));assert before
subprocess.run(['runuser','-u','shell','--','env','XDG_RUNTIME_DIR=/run/shell','/nix/store/qbi2i7cq00i6z8mshh17bq8vcr7dk3ds-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust','--surface','hide'],check=True,timeout=5)
ipc('card_shell home');time.sleep(.3)
ipc('seat seat0 cursor set 284 1220; seat seat0 cursor press button1; seat seat0 cursor release button1');time.sleep(.35)
state=ipc('card_shell debug-scene')[0]['error'];assert 'active=1 ' in state,state
after=windows(ipc(kind=4));assert before==after,(before,after)
print('WINDOW_RETENTION_RESULT '+json.dumps({'before':before,'after':after,'equal':True,'evidence_class':'board-injected-pointer'}))
ipc('card_shell home');time.sleep(.3)
subprocess.run(['runuser','-u','shell','--','env','XDG_RUNTIME_DIR=/run/shell','/nix/store/qbi2i7cq00i6z8mshh17bq8vcr7dk3ds-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust','--surface','drawer'],check=True,timeout=5)
