import json,subprocess,sys,time,re,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from cadence_audit import identity,ipc
import argparse,importlib.util
s=importlib.util.spec_from_file_location('profile_trace',Path(__file__).parent/'tools/landscape-hdmi-stall-trace.py')
trace=importlib.util.module_from_spec(s);s.loader.exec_module(trace)

root=Path(__file__).parent
out=Path('/run/k230-source3-render-profile-20261021');out.mkdir(mode=0o700)
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
restore.write_text(restore.read_text().replace('rm -f ', 'if [ -f /run/k230-source3-render-profile-20261021/traced/trace-state.json ] && [ ! -f /run/k230-source3-render-profile-20261021/traced/trace-cleanup.json ]; then '+sys.executable+' '+str(root/'tools/landscape-hdmi-stall-trace.py')+' --cleanup /run/k230-source3-render-profile-20261021/traced/trace-state.json || true; fi\nrm -f ',1))
restore.chmod(0o700)
unit='k230-source3-render-profile-20261021'
subprocess.run(['systemd-run','--quiet','--unit='+unit,'--on-active=480s',str(restore)],check=True)
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
    trace.board_smoke(argparse.Namespace(output=out/'smoke'))
    meta['smoke']=json.loads((out/'smoke/smoke.json').read_text())
    assert meta['smoke']['status']=='QUALIFIED' and meta['smoke']['system']==m['system']
    pid=int(subprocess.check_output(['systemctl','show','shell','-p','MainPID','--value'],text=True))
    meta['target_pid']=pid;meta['fd_labels']=trace.fd_labels(pid)
    meta['target_threads_before']=[int(p.name) for p in Path('/proc',str(pid),'task').iterdir()]
    for label,traced in [('untraced',False),('traced',True),('untraced-return',False)]:
        directory=out/label;directory.mkdir(mode=0o700)
        session=trace.Session(directory,pid) if traced else None
        try:
            if session:session.prepare();session.start()
            r=subprocess.run([sys.executable,str(root/'collect.py'),'full',str(directory/'3-cards'),'6',m['source_revision'],m['system'],'3'],capture_output=True,text=True,timeout=90)
            (directory/'collector.private.log').write_text(r.stdout+r.stderr)
            if session:
                session.finish();events,details=trace.checked_events(directory)
                peers={p for e in events if e['event']=='switch' for p in (e['prev_pid'],e['next_pid']) if p!=pid}
                allowed={'shell.service','shell-ui.service','theme-helper.service','systemd-journald.service','sshd.service','dbus.service','systemd-udevd.service'}
                labels={}
                for peer in sorted(peers):
                    label_for_peer='idle' if peer==0 else 'trace-controller' if peer==__import__('os').getpid() else 'other-or-exited'
                    try:
                        groups=(Path('/proc')/str(peer)/'cgroup').read_text()
                        matches=[u for u in allowed if ('/'+u) in groups]
                        if len(matches)==1:label_for_peer=matches[0]
                        if (Path('/proc')/str(peer)/'comm').read_text().startswith('kworker/'):label_for_peer='kernel-worker'
                    except OSError:pass
                    labels[str(peer)]=label_for_peer
                (directory/'peer-labels.json').write_text(json.dumps({'labels':labels,'limits':'First switched-to peer only; intervening scheduling of unrelated tasks is not traced. No arbitrary process names or cgroup paths exported.'},indent=2)+'\n')
        finally:
            if session:
                trace.safe_close(session)
                cleanup=json.loads((directory/'trace-cleanup.json').read_text())
                assert cleanup['instance_removed'] and cleanup['global_controls_unchanged'] and cleanup['cleanup_timer_active'] is False
        meta['runs'].append({'label':label,'cards':3,'traced':traced,'exit':r.returncode})
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
