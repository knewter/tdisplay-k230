import json, subprocess, hashlib
from pathlib import Path

def ipc(command='', kind=0):
    import socket,struct
    p=command.encode()
    with socket.socket(socket.AF_UNIX) as s:
        s.settimeout(10);s.connect('/run/shell/sway-ipc.sock')
        s.sendall(b'i3-ipc'+struct.pack('=II',len(p),kind)+p)
        def read(n):
            b=b''
            while len(b)<n:
                q=s.recv(n-len(b));assert q;b+=q
            return b
        n,_=struct.unpack('=II',read(14)[6:]);r=json.loads(read(n))
    if kind==0:assert all(v.get('success') for v in r)
    return r

def appids(n):
    return ([n['app_id']] if n.get('app_id') else [])+sum((appids(c) for c in n.get('nodes',[])+n.get('floating_nodes',[])),[])

def identity():
    p=subprocess.check_output(['systemctl','show','shell','-p','MainPID','--value'],text=True).strip()
    exe=Path('/proc',p,'exe').resolve()
    out=[o for o in ipc(kind=3) if o['active']]
    return {'system':str(Path('/run/current-system').resolve()),'profile':str(Path('/nix/var/nix/profiles/system').resolve()),'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'sway_exe':str(exe),'sway_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'outputs':[{k:o[k] for k in ['name','rect','transform','current_mode','max_render_time']} for o in out],'apps':appids(ipc(kind=4)),'wallpaper':json.loads(Path('/run/shell/k230-wallpaper-status.json').read_text())}

if __name__=='__main__':print(json.dumps(identity()))
