import json,subprocess,sys,time,re,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from cadence_audit import identity,ipc

root=Path(__file__).parent
m=json.loads((root/'descriptor.json').read_text())
before=identity()
assert before['system']==m['system'] and before['profile']==m['system']
assert before['sway_sha256']==m['normal_sha256']
assert before['apps']==['k230-terminal'] and before['wallpaper']['state']=='still'
assert len(before['outputs'])==1 and before['outputs'][0]['max_render_time']==8
assert before['outputs'][0]['transform']=='270'
override=Path('/run/systemd/system/shell.service.d/94-source3-cadence-timing.conf')
assert not override.exists()
stable=root/'recovery';stable.mkdir(mode=0o700)
start=subprocess.check_output(['systemctl','show','shell.service','-p','ExecStart','--value'],text=True)
old=re.search(r'path=([^;]+);',start).group(1).strip()
argv=re.search(r'argv\[\]=([^;]+);',start).group(1).strip()
assert argv==old or argv.startswith(old+' ')
args=argv[len(old):];assert re.fullmatch(r'[ /A-Za-z0-9_.+?=:-]*',args)
assert re.fullmatch(r'/nix/store/[0-9a-z]{32}-k230-card-shell-hdmi-trial',m['candidate'])
assert hashlib.sha256(Path(m['candidate_exe']).read_bytes()).hexdigest()==m['candidate_sha256']
restore=stable/'restore.sh'
restore.write_text('#!/bin/sh\nset -eu\nrm -f '+str(override)+'\nsystemctl daemon-reload\nsystemctl restart shell.service shell-ui.service theme-helper.service\n')
restore.chmod(0o700)
unit='k230-source3-cadence-elapsed-20261021-attempt2'
subprocess.run(['systemd-run','--quiet','--unit='+unit,'--on-active=300s',str(restore)],check=True)
assert subprocess.run(['systemctl','is-active','--quiet',unit+'.timer']).returncode==0
gc=Path('/nix/var/nix/gcroots/source3-cadence-elapsed-20261021')
if gc.exists():assert gc.is_symlink() and str(gc.resolve())==m['candidate']
else:gc.symlink_to(m['candidate'])
meta={'source_revision':m['source_revision'],'descriptor':m,'before':before,'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'runs':[],'restore_unit':unit}
(stable/'before.private.json').write_text(json.dumps({**meta,'normal_exec_start':start},indent=2)+'\n')
def ready(sha,timeout=60):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        try:
            v=identity()
            if v['sway_sha256']==sha and v['apps']==['k230-terminal'] and v['wallpaper']['state']=='still':return v
        except Exception:pass
        time.sleep(.3)
    raise RuntimeError('expected compositor/terminal/wallpaper did not become ready')
try:
    override.parent.mkdir(parents=True,exist_ok=True)
    override.write_text('[Service]\nExecStart=\nExecStart='+m['candidate']+'/bin/sway'+args+'\n')
    subprocess.run(['systemctl','daemon-reload'],check=True)
    subprocess.run(['systemctl','restart','shell.service','shell-ui.service','theme-helper.service'],check=True,timeout=80)
    meta['candidate']=ready(m['candidate_sha256'])
    for cards in [1,3]:
        dest=root/(str(cards)+'-cards')
        r=subprocess.run([sys.executable,str(root/'collect.py'),'full',str(dest),'6',m['source_revision'],m['system'],str(cards)],capture_output=True,text=True,timeout=90)
        (root/(str(cards)+'-collector.private.log')).write_text(r.stdout+r.stderr)
        meta['runs'].append({'cards':cards,'exit':r.returncode})
        (root/'result.json').write_text(json.dumps(meta,indent=2)+'\n')
        print(json.dumps(meta['runs'][-1]),flush=True)
        if r.returncode:raise RuntimeError('collector failed')
finally:
    subprocess.run([str(restore)],check=True,timeout=80)
    meta['restored']=ready(m['normal_sha256'])
    assert meta['restored']['system']==before['system']
    assert meta['restored']['boot_id']==before['boot_id']
    assert meta['restored']['outputs']==before['outputs']
    assert meta['restored']['wallpaper']['generation']==before['wallpaper']['generation']
    assert not override.exists()
    meta['test_input_devices']=sum(p.read_text().strip()=='K230 injected touchscreen' for p in Path('/sys/class/input').glob('event*/device/name'))
    assert meta['test_input_devices']==0
    meta['normal_services']={n:subprocess.run(['systemctl','is-active','--quiet',n]).returncode==0 for n in ['shell','shell-ui','theme-helper']}
    assert all(meta['normal_services'].values())
    subprocess.run(['systemctl','stop',unit+'.timer'],check=True)
    meta['restore_timer_active']=subprocess.run(['systemctl','is-active','--quiet',unit+'.timer']).returncode==0
    assert not meta['restore_timer_active']
    meta['finished_utc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
    (root/'result.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps({'restoration':'verified','runs':len(meta['runs'])}),flush=True)
