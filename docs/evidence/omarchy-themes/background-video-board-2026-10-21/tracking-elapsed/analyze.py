from pathlib import Path
import argparse,importlib.util,json,re,collections

def load(path):
    s=importlib.util.spec_from_file_location('elapsed_budget',path)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def analyze(raw,benchmark):
    rows,_=benchmark.parse_rows(raw)
    heads=[r for r in rows if r['event']=='session'];assert len(heads)==1
    run=heads[0]['run'];timing={};costs={}
    fields={'run','frame_id','scheduled_ns','delay_ms','start_ns','commit_start_ns','end_ns'}
    for line in raw.decode().splitlines():
        if line.startswith('K230_CARD_SHELL repaint-timing '):
            parts=line.split()[2:];assert all(re.fullmatch(r'[a-z_]+=[0-9]+',p) for p in parts)
            r={k:int(v) for k,v in (p.split('=') for p in parts)}
            assert set(r)==fields and len(parts)==len(fields) and str(r['run'])==run
            assert r['start_ns']<=r['commit_start_ns']<=r['end_ns']
            assert r['frame_id'] not in timing;timing[r['frame_id']]=r
        if line.startswith('K230_CARD_SHELL repaint-cost '):
            r={k:int(v) for k,v in (p.split('=') for p in line.split()[2:])}
            assert r['frame_id'] not in costs;costs[r['frame_id']]=r
    assert timing
    presented={r['frame_id']:r['t_ns'] for r in rows if r['event']=='present' and r['presented']}
    submissions={r['frame_id'] for r in rows if r['event']=='submit'}
    frames=[]
    for f,r in sorted(timing.items(),key=lambda kv:kv[1]['start_ns']):
        v={'frame_id':f,'start_ns':r['start_ns'],'end_ns':r['end_ns'],'requested_delay_ms':r['delay_ms'],
           'render_wall_ms':(r['end_ns']-r['start_ns'])/1e6,
           'precommit_wall_ms':(r['commit_start_ns']-r['start_ns'])/1e6,
           'commit_wall_ms':(r['end_ns']-r['commit_start_ns'])/1e6,'has_correlated_input':f in submissions,
           'scheduler_lateness_ms':None if not r['scheduled_ns'] else (r['start_ns']-r['scheduled_ns'])/1e6-r['delay_ms']}
        if f in presented:v['submit_to_present_ms']=(presented[f]-r['commit_start_ns'])/1e6
        if f in costs:
            v['attempts']=costs[f]['attempts'];v['render_cpu_ms']=costs[f]['render_cpu_ns']/1e6
            if v['attempts']==1:v['render_wall_minus_cpu_ms']=v['render_wall_ms']-v['render_cpu_ms']
        frames.append(v)
    def summary(values):
        return {'count':len(values),**({'p50':benchmark.percentile(values,.5),'p95':benchmark.percentile(values,.95),'max':max(values)} if values else {})}
    groups={}
    for name,subset in [('all_committed',frames),('correlated', [f for f in frames if f['has_correlated_input']])]:
        groups[name]={k:summary([f[k] for f in subset if f.get(k) is not None]) for k in ['render_wall_ms','precommit_wall_ms','commit_wall_ms','scheduler_lateness_ms','submit_to_present_ms','render_wall_minus_cpu_ms']}
    return {'run':run,'cards':heads[0]['cards'],'groups':groups,'frames':frames,
            'limits':'Benchmark-only instrumentation adds overhead. Scheduler lateness includes Sway scene work after timer request and timer/event-loop dispatch, not a kernel-only measurement. CPU comparison excludes accumulated failed render attempts. Backend timestamps are not optical visibility. No acceptance metric replaced.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('benchmark',type=Path);a=p.parse_args()
    b=load(a.benchmark);v={f.parent.name:analyze(f.read_bytes(),b) for f in sorted(a.directory.glob('*/telemetry.log'))}
    assert v;(a.directory/'elapsed-analysis.json').write_text(json.dumps(v,indent=2)+'\n')
    helpers=Path(__file__).resolve().parent.parent
    costs=load(helpers/'analyze-card-costs.py')
    budget=costs.replay(a.directory,json.loads((a.directory/'manifest.json').read_text()))
    (a.directory/'budget-analysis.json').write_text(json.dumps(budget,indent=2)+'\n')
    cadence=load(helpers/'tracking-cadence/analyze.py')
    diagnostic={f.parent.name:cadence.describe(f.read_bytes()) for f in sorted(a.directory.glob('*/telemetry.log'))}
    for name,r in diagnostic.items():
        frozen=next(r for r in budget['runs'] if r['run']==v[name]['run'])['metrics']['tracking_present_interval_ms']
        assert (r['tracking_present_interval_ms']['count'],r['tracking_present_interval_ms']['p95'])==(frozen['count'],frozen['p95'])
    (a.directory/'cadence-diagnostics.json').write_text(json.dumps(diagnostic,indent=2)+'\n')
    for name,r in v.items():print(name,json.dumps(r['groups']['correlated']))
