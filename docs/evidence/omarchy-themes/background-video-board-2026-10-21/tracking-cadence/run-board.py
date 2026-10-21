import json,subprocess,sys,time,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from cadence_audit import identity,ipc

root=Path(__file__).parent
py=sys.executable
revision='d39abadfab3fb4e6c0d8d201d06d9a82a73d22ad'
before=identity()
assert before['system']=='/nix/store/2igpibpw4nn0clbda7p35dp5bhg28n35-nixos-system-nixos-26.11.20260919.20b1ddd'
assert before['profile']==before['system']
assert before['sway_sha256']=='4fc7bf3a0c0818c9eb3d286de4579999b3fbbaf9abe0e4317c017bca1dc663ba'
assert len(before['outputs'])==1 and before['outputs'][0]['max_render_time']==8
assert before['apps']==['k230-terminal'] and before['wallpaper']['state']=='still'
restore=root/'restore.sh'
restore.write_text('#!/bin/sh\n/run/current-system/sw/bin/swaymsg -s /run/shell/sway-ipc.sock output DSI-1 max_render_time 8\n/run/current-system/sw/bin/swaymsg -s /run/shell/sway-ipc.sock card_shell benchmark-stop\n/run/current-system/sw/bin/swaymsg -s /run/shell/sway-ipc.sock card_shell home\n')
restore.chmod(0o700)
guard='k230-source3-cadence-20261021'
subprocess.run(['systemd-run','--unit='+guard,'--on-active=300s','--timer-property=AccuracySec=1s',str(restore)],check=True,capture_output=True)
meta={'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'source_revision':revision,'before':before,'guard':guard,'interaction':'persistent uinput; no real-finger or optical timing claim','runs':[]}
try:
    for label,allowance,cards in [('a8',8,3),('b12',12,3),('a8-return',8,3),('a8-one',8,1),('b12-one',12,1)]:
        ipc('output DSI-1 max_render_time '+str(allowance))
        assert identity()['outputs'][0]['max_render_time']==allowance
        dest=root/label
        r=subprocess.run([py,str(root/'collect.py'),'full',str(dest),'6',revision,before['system'],str(cards)],capture_output=True,text=True,timeout=90)
        (root/(label+'.private.log')).write_text(r.stdout+r.stderr)
        meta['runs'].append({'label':label,'allowance_ms':allowance,'cards':cards,'exit':r.returncode})
        (root/'result.json').write_text(json.dumps(meta,indent=2)+'\n')
        print(json.dumps(meta['runs'][-1]),flush=True)
        if r.returncode:raise RuntimeError('collector failed '+label)
finally:
    ipc('output DSI-1 max_render_time 8')
    ipc('card_shell benchmark-stop');ipc('card_shell home')
    meta['after']=identity()
    assert meta['after']['outputs'][0]['max_render_time']==8
    assert meta['after']['wallpaper']['generation']==before['wallpaper']['generation']
    assert meta['after']['apps']==before['apps']
    subprocess.run(['systemctl','stop',guard+'.timer'],check=True,capture_output=True)
    meta['finished_utc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
    meta['restored']=True
    (root/'result.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps({'restored':True,'runs':len(meta['runs'])}),flush=True)
