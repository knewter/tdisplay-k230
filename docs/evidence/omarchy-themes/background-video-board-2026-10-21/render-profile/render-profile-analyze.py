"""Join qualified numeric scheduler/syscall events to compositor render windows."""
from pathlib import Path
import argparse,collections,importlib.util,json,re

def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def overlap(a,b,c,d):
    return max(0,min(b,d)-max(a,c))

def off_cpu(window,switches):
    a,b=window
    result={'runnable_ns':0,'blocked_ns':0,'unknown_ns':0}
    previous_end=None
    for s in switches:
        first,last=s['start_ns'],s['end_ns']
        assert first<=last and (previous_end is None or first>=previous_end)
        previous_end=last
        if s['state'].startswith('R'):
            result['runnable_ns']+=overlap(a,b,first,last)
        elif s['state'] in ('S','D') and s['wakeup_ns'] is not None:
            wake=s['wakeup_ns'];assert first<=wake<=last
            result['blocked_ns']+=overlap(a,b,first,wake)
            result['runnable_ns']+=overlap(a,b,wake,last)
        else:result['unknown_ns']+=overlap(a,b,first,last)
    assert sum(result.values())<=b-a
    return result

def analyze(directory,repo):
    trace=load('render_trace',repo/'tools/landscape-hdmi-stall-trace.py')
    budget=load('render_budget',repo/'tools/card-shell-benchmark.py')
    old=repo/'docs/evidence/omarchy-themes/background-video-board-2026-10-21'
    elapsed=load('render_elapsed',old/'tracking-elapsed/analyze.py')
    runs={}
    for role in ('untraced','traced','untraced-return'):
        raw=(directory/role/'3-cards/telemetry.log').read_bytes()
        runs[role]=elapsed.analyze(raw,budget)
    events,meta=trace.checked_events(directory/'traced')
    target=meta['pid'];frames=runs['traced']['frames']
    boundaries={}
    for line in (directory/'traced/3-cards/telemetry.log').read_text().splitlines():
        if line.startswith('K230_CARD_SHELL repaint-timing '):
            r={k:int(v) for k,v in (p.split('=') for p in line.split()[2:])}
            boundaries[r['frame_id']]=r['commit_start_ns']
    first=min(f['start_ns'] for f in frames);last=max(f['end_ns'] for f in frames)
    calls,switches,partial=trace.intervals(events,target,first,last)
    cleanup=json.loads((directory/'traced/trace-cleanup.json').read_text())
    assert cleanup['instance_removed'] and cleanup['global_controls_unchanged'] and cleanup['cleanup_timer_active'] is False
    labels=json.loads((directory/'traced/peer-labels.json').read_text())['labels']
    result=[];by_call=collections.defaultdict(lambda:{'overlap_ns':0,'count':0})
    by_peer=collections.Counter()
    for f in frames:
        if not f['has_correlated_input']:continue
        start,end=f['start_ns'],f['end_ns']
        state=off_cpu((start,end),switches)
        row={'frame_id':f['frame_id'],'start_ns':start,'end_ns':end,
             'render_wall_ms':f['render_wall_ms'],'render_cpu_ms':f.get('render_cpu_ms'),
             **{k.removesuffix('_ns')+'_ms':v/1e6 for k,v in state.items()},'syscalls':[]}
        for c in calls:
            ns=overlap(start,end,c['start_ns'],c['end_ns'])
            if not ns:continue
            call={'nr':c['nr'],'overlap_ms':ns/1e6,'fd':c.get('fd'),'command':c.get('command')}
            row['syscalls'].append(call)
            key=(c['nr'],c.get('fd'),c.get('command'))
            by_call[key]['overlap_ns']+=ns;by_call[key]['count']+=1
        for s in switches:
            ns=overlap(start,end,s['start_ns'],s['end_ns'])
            if ns:by_peer[labels.get(str(s['descheduled_to_pid']),'unknown')]+=ns
        row['off_cpu_ms']=sum(state.values())/1e6
        row['non_descheduled_wall_ms']=row['render_wall_ms']-row['off_cpu_ms']
        commit=boundaries[f['frame_id']]
        for phase,window in [('precommit',(start,commit)),('commit',(commit,end))]:
            split=off_cpu(window,switches)
            row[phase+'_off_cpu_ms']=sum(split.values())/1e6
        assert abs(row['precommit_off_cpu_ms']+row['commit_off_cpu_ms']-row['off_cpu_ms'])<1e-9
        result.append(row)
    def summary(values):
        return {'count':len(values),**({'p50':budget.percentile(values,.5),'p95':budget.percentile(values,.95),'max':max(values)} if values else {})}
    out={'target_pid':target,'trace_event_count':meta['event_count'],'trace_stats':meta['stats'],
         'clock_and_loss_checked':True,'partial_trace_edges':partial,'runs':runs,
         'correlated_frames':result,
         'off_cpu_summary':{k:summary([r[k] for r in result]) for k in ['render_wall_ms','runnable_ms','blocked_ms','unknown_ms','off_cpu_ms','non_descheduled_wall_ms','precommit_off_cpu_ms','commit_off_cpu_ms']},
         'render_allowance_diagnostic':{'allowance_ms':8,'exceeded_count':sum(r['render_wall_ms']>8 for r in result),'non_descheduled_exceeded_count':sum(r['non_descheduled_wall_ms']>8 for r in result),'limits':'Subtracting observed off-CPU time is descriptive, not a prediction under a different scheduling policy. Remaining wall time includes interrupts and kernel execution, and is not a CPU charge.'},
         'syscall_render_overlap':[{'nr':k[0],'fd':k[1],'command':k[2],**v} for k,v in sorted(by_call.items(),key=lambda x:x[1]['overlap_ns'],reverse=True)],
         'first_switched_to_peer_render_overlap_ns':dict(by_peer),
         'limits':['Trace samples main thread only; process CPU may include other compositor threads.',
                   'Off-CPU phase boundaries use microsecond trace timestamps against nanosecond render clocks; small edge error remains.',
                   'Syscall wall intervals and off-CPU intervals overlap; never add them as exclusive costs.',
                   'A sleeping switch without a matching wake has unknown wait partition.',
                   'Peer labels identify only the task first switched to; intervening task execution is not captured.',
                   'An untraced/traced/untraced comparison measures observer/workload variation, not causality.',
                   'Native uinput/backend feedback is not real-finger or optical proof. Frozen budget gate is separate.']}
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--repo',type=Path,required=True);a=p.parse_args()
    v=analyze(a.directory,a.repo);(a.directory/'profile-analysis.json').write_text(json.dumps(v,indent=2)+'\n')
    print(json.dumps(v['off_cpu_summary'],indent=2))
