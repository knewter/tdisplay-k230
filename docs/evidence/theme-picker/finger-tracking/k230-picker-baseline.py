#!/usr/bin/env python3
"""Bounded injected picker browsing. Run as root only after Settings is visible.
No activation CLI, compositor changes, service restarts, or media capture.
Output is private diagnostic JSON; review before publishing.
"""
import argparse, json, os, re, struct, subprocess, threading, time
from pathlib import Path

def verify_device(device):
    if not re.fullmatch(r'/dev/input/event[0-9]+',device):
        raise ValueError('expected an input event device')
    p=Path('/sys/class/input')/Path(device).name/'device/name'
    if p.read_text().strip()!='K230 injected touchscreen':
        raise RuntimeError('fixture name mismatch')
    if not str(p.resolve()).startswith('/sys/devices/virtual/input/'):
        raise RuntimeError('refusing a physical input device')

# Native touch implementation copied from tools/card-shell-acceptance.py.
def native_touch(device, x, y, x2=None, y2=None, held=None):
    """Write Linux input_event packets; kernel timestamps remain authoritative.

    One write per SYN frame avoids starting five evemu processes per movement.
    Absolute deadlines avoid accumulating process/sleep overhead. This is still
    software input, not physical touch or a guaranteed delivery rate.
    """
    verify_device(device)
    points=[(x,y)] if x2 is None else [(x,y),(x2,y2)]
    if any(not (0<=px<568 and 0<=py<1232) for px,py in points):
        raise ValueError('touch coordinates outside native panel')
    event=struct.Struct('@llHHi')
    def position(px,py):
        dx=px*1024//568;dy=py*2400//1232
        return [(3,53,dx),(3,54,dy),(3,0,dx),(3,1,dy)]
    fd=os.open(device,os.O_WRONLY|os.O_CLOEXEC)
    def frame(events):
        packet=b''.join(event.pack(0,0,*values) for values in [*events,(0,0,0)])
        if os.write(fd,packet)!=len(packet):raise OSError('short input-event write')
    try:
        frame([(3,47,0),(3,57,7),(3,48,3),(1,330,1),*position(x,y)])
        start=time.monotonic()
        if x2 is None:time.sleep(.08)
        else:
            for i in range(1,21):
                time.sleep(max(0,start+i*.01-time.monotonic()))
                frame(position(x+(x2-x)*i//20,y+(y2-y)*i//20))
        if held:held()
    finally:
        try:frame([(3,57,-1),(1,330,0)])
        finally:os.close(fd)


def prop(unit,field):
    return subprocess.check_output(['systemctl','show',unit,'-p',field,'--value'],text=True,timeout=5).strip()

def stat(pid):
    s=(Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split()
    return {'ticks':int(s[11])+int(s[12]),'start_ticks':int(s[19]),
            'rss_bytes':int(s[21])*os.sysconf('SC_PAGE_SIZE')}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--device',required=True)
    ap.add_argument('--expect-rust-exe',required=True)
    ap.add_argument('--state-root',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--label',required=True)
    ap.add_argument('--settings-ready',action='store_true',required=True)
    a=ap.parse_args()
    if os.geteuid()!=0:raise RuntimeError('requires root on the reserved board')
    os.umask(0o077)
    if a.output.exists():raise RuntimeError('refusing to overwrite evidence')
    verify_device(a.device)
    identities={}
    for unit in ['shell-ui.service','shell.service','theme-helper.service']:
        pid=int(prop(unit,'MainPID'))
        if pid<=0:raise RuntimeError('unit not running: '+unit)
        identities[unit]={'pid':pid,'exe':os.readlink('/proc/'+str(pid)+'/exe'),
                          'cgroup':prop(unit,'ControlGroup'),'start_ticks':stat(pid)['start_ticks']}
    if identities['shell-ui.service']['exe']!=a.expect_rust_exe:
        raise RuntimeError('unexpected Rust executable')
    active=a.state_root/'active'
    before=str(active.resolve(strict=True))
    start=time.monotonic();epoch=time.time();stop=threading.Event()
    samples=[];phases=[];errors=[]
    def sample():
        row={'monotonic_s':time.monotonic(),'generation':str(active.resolve(strict=True)),'units':{}}
        for unit,identity in identities.items():
            values=stat(identity['pid'])
            if values['start_ticks']!=identity['start_ticks']:raise RuntimeError('PID identity changed')
            cpu=Path('/sys/fs/cgroup'+identity['cgroup'])/'cpu.stat'
            values['cgroup_cpu']=dict((k,int(v)) for k,v in (line.split() for line in cpu.read_text().splitlines()))
            row['units'][unit]=values
        samples.append(row)
        if row['generation']!=before:raise RuntimeError('active generation changed; stop browsing')
    def monitor():
        while not stop.is_set():
            try:sample()
            except Exception as e:errors.append(str(e));stop.set();return
            stop.wait(.5)
    def phase(name,seconds,touch=None):
        if stop.is_set():raise RuntimeError('monitor failed: '+str(errors))
        item={'name':name,'start_monotonic_s':time.monotonic()};phases.append(item)
        if touch:
            native_touch(a.device,*touch)
            item['injection_end_monotonic_s']=time.monotonic()
        if stop.wait(seconds):raise RuntimeError('monitor failed: '+str(errors))
        item['end_monotonic_s']=time.monotonic()
    report={'label':a.label,'provenance':'injected-input-event; not physical finger proof',
            'cold_definition':'first picker open in this process; disk cache was not cleared',
            'start_epoch_s':epoch,'start_monotonic_s':start,'clock_ticks_per_second':os.sysconf('SC_CLK_TCK'),
            'booted_system':str(Path('/run/booted-system').resolve()),
            'current_system':str(Path('/run/current-system').resolve()),'kernel_release':os.uname().release,
            'active_background_count':len(json.loads((Path(before)/'report.json').read_text())['backgrounds']),
            'identities':identities,'generation_before':before,'phases':phases,'samples':samples,'errors':errors}
    thread=threading.Thread(target=monitor,daemon=True);thread.start()
    try:
        phase('settings-baseline',2)
        phase('first-open',10,(480,130))
        for i,(x,x2) in enumerate([(430,190)]*3+[(190,430)]*3):
            phase('theme-swipe-'+str(i),1.2,(x,430,x2,430))
        for i,(x,x2) in enumerate([(430,190)]*2+[(190,430)]*2):
            phase('background-swipe-'+str(i),1.2,(x,990,x2,990))
        phase('idle-first',15)
        phase('back',1,(90,52))
        phase('warm-open',5,(480,130))
        for i,(x,x2) in enumerate([(430,190)]*3+[(190,430)]*3):
            phase('warm-theme-swipe-'+str(i),1.2,(x,430,x2,430))
        phase('idle-warm',15)
        report['status']='CAPTURED_REQUIRES_REVIEW'
    except Exception as e:
        errors.append(str(e));report['status']='FAILED'
    finally:
        stop.set();thread.join(timeout=2)
        report['generation_after']=str(active.resolve(strict=True))
        report['generation_unchanged']=report['generation_after']==before and all(s['generation']==before for s in samples)
        report['end_monotonic_s']=time.monotonic()
        # Journal collection happens after all timing samples, not during swipes.
        try:
            raw=subprocess.run(['journalctl','-o','json','--since','@'+str(epoch),
                 '-u','shell-ui.service','-u','theme-helper.service','--no-pager'],
                 capture_output=True,text=True,timeout=20,check=True).stdout
            events=[]
            for line in raw.splitlines():
                entry=json.loads(line);msg=entry.get('MESSAGE','')
                if not isinstance(msg,str):continue
                if re.match(r'^rust-shell \d+ms ',msg) or 'THEME_TIMING' in msg:
                    events.append({'monotonic_us':entry.get('__MONOTONIC_TIMESTAMP'),
                                   'unit':entry.get('_SYSTEMD_UNIT'),'message':msg})
            report['events']=events
        except Exception as e:
            errors.append('journal collection failed: '+str(e));report['status']='FAILED'
        a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(report['status'],a.output)
    return 0 if report['status']=='CAPTURED_REQUIRES_REVIEW' and report['generation_unchanged'] else 1

if __name__=='__main__':raise SystemExit(main())
