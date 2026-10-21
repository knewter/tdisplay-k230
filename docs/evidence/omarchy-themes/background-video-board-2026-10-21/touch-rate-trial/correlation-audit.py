"""Audit existing input/frame association without replacing any frozen metric."""
from bisect import bisect_left
from collections import defaultdict
import argparse,importlib.util,json
from pathlib import Path

def audit(directory,repo):
 s=importlib.util.spec_from_file_location('association_budget',repo/'tools/card-shell-benchmark.py');b=importlib.util.module_from_spec(s);s.loader.exec_module(b);result={}
 for label in ['static-1-cards','static-3-cards','video-1-cards','video-3-cards']:
  raw=(directory/label/'telemetry.log').read_text();rows,_=b.parse_rows(raw.encode());assert sum(r['event']=='session' for r in rows)==1;inputs={r['input_id']:r for r in rows if r['event']=='input'};submits={r['input_id']:r for r in rows if r['event']=='submit'};present={r['frame_id']:r['t_ns'] for r in rows if r['event']=='present' and r['presented']};timing=[];input_lines={};origins={}
  for n,line in enumerate(raw.splitlines()):
   if line.startswith('K230_CARD_SHELL repaint-timing '):
    r={k:int(v) for k,v in (s.split('=') for s in line.split()[2:])};r['line']=n;timing.append(r)
   if line.startswith('K230_CARD_SHELL input-origin '):
    r={k:int(v) for k,v in (s.split('=') for s in line.split()[2:])};origins[r['input_id']]=r['source_ns']
   if line.startswith('K230_CARD_BENCH ') and 'event=input ' in line:
    r=dict(s.split('=',1) for s in line.split()[1:]);input_lines[int(r['input_id'])]=n
  starts=[r['start_ns'] for r in timing];assert starts==sorted(starts);by_frame={r['frame_id']:r for r in timing};motion=[r for r in inputs.values() if r['kind']=='motion'];disagreement=[];nested=[];gestures=defaultdict(list)
  for r in motion:
   i=r['input_id'];first=timing[bisect_left(starts,r['t_ns'])];mapped=submits[i]['frame_id']
   if first['frame_id']!=mapped:disagreement.append(i)
   if first['line']<input_lines[i]:nested.append(i)
   gestures[r['gesture_id']].append(r)
  late=[];intervals=[]
  for g,entries in gestures.items():
   entries.sort(key=lambda r:r['t_ns']);assert all(z['t_ns']-a['t_ns']<=50_000_000 for a,z in zip(entries,entries[1:])),'audit requires no excluded input pauses'
   # Frozen parser deduplicates coalesced motion inputs per presented frame.
   represented={}
   for r in entries:
    f=submits[r['input_id']]['frame_id']
    if f in present and (f not in represented or represented[f]['t_ns']<r['t_ns']):represented[f]=r
   ordered=sorted(represented,key=lambda f:submits[represented[f]['input_id']]['t_ns'])
   for a,z in zip(ordered,ordered[1:]):
    before,after=represented[a],represented[z];gap=(present[z]-present[a])/1e6;intervals.append(gap)
    if gap<=b.BUDGETS['tracking_present_interval_ms']['p95']:continue
    intermediate=[f for f,t in present.items() if present[a]<t<present[z]]
    late.append({'gesture_id':g,'previous_frame':a,'next_frame':z,'previous_input':before['input_id'],'next_input':after['input_id'],'present_gap_ms':gap,'dispatch_gap_ms':(after['t_ns']-before['t_ns'])/1e6,'origin_gap_ms':(origins[after['input_id']]-origins[before['input_id']])/1e6 if before['input_id'] in origins and after['input_id'] in origins else None,'intermediate_frames':intermediate,'intermediate_render_starts_before_next_input':all(by_frame[f]['start_ns']<after['t_ns'] for f in intermediate),'next_input_to_render_start_ms':(by_frame[z]['start_ns']-after['t_ns'])/1e6})
  result[label]={'motion_inputs':len(motion),'first_subsequent_render_mapping_disagreements':disagreement,'render_timing_logged_before_input_end_row':nested,'tracking_intervals':len(intervals),'tracking_p95_ms':b.percentile(intervals,.95),'above_target_intervals':late}
 frozen=json.loads((directory/'paired-analysis.json').read_text())['runs']
 for label,r in result.items():
  original=frozen[label]['frozen_metrics']['tracking_present_interval_ms'];assert (r['tracking_intervals'],r['tracking_p95_ms'])==(original['count'],original['p95'])
 return {'runs':result,'limits':['Host audit of committed board timestamps and stream order; no new hardware measurement.','First subsequent actual render-start agreement supports the recorded mapping; it does not prove optical visibility or identify every input-dispatch delay.','Intermediate presentations whose render started before the next input cannot simply be credited to that later input.','No frozen parser, input workload, threshold, or failed result is changed. Input/refresh phase sensitivity needs separate investigation.']}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--repo',type=Path,required=True);a=p.parse_args();v=audit(a.directory,a.repo);(a.directory/'correlation-audit.json').write_text(json.dumps(v,indent=2)+'\n')
 for name,r in v['runs'].items():print(name,json.dumps({'motions':r['motion_inputs'],'mapping_disagreements':len(r['first_subsequent_render_mapping_disagreements']),'nested_render_rows':len(r['render_timing_logged_before_input_end_row']),'late':len(r['above_target_intervals']),'p95':r['tracking_p95_ms']}))
