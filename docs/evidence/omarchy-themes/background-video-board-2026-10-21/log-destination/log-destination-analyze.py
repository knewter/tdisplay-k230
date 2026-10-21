"""Replay unchanged card gates and compare measured journal/file logging arms."""
from pathlib import Path
import argparse,importlib.util,json

def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def cpu_window(samples,first,last):
 assert first<last and len(samples)>=3
 previous=None;identity=samples[0]['cgroup_identity']
 for r in samples:
  assert r['cgroup_identity']==identity and r['cpu_ns']>=0
  if previous:assert r['t_ns']>previous['t_ns'] and r['cpu_ns']>=previous['cpu_ns']
  previous=r
 selected=[r for r in samples if first<=r['t_ns']<=last]
 assert len(selected)>=3,'insufficient measured samples inside active phase'
 a,z=selected[0],selected[-1];wall=z['t_ns']-a['t_ns'];cpu=z['cpu_ns']-a['cpu_ns']
 return {'sample_count':len(selected),'first_sample_ns':a['t_ns'],'last_sample_ns':z['t_ns'],'elapsed_seconds':wall/1e9,'cpu_seconds':cpu/1e9,'average_cores':cpu/wall,'requested_window_ns':[first,last],'limits':'Measured samples wholly inside the active phase; no interpolation or extrapolation. Journal cgroup CPU includes unrelated logs.'}

def replay(directory,repo):
 parent=repo/'docs/evidence/omarchy-themes/background-video-board-2026-10-21'
 costs=load('destination_costs',parent/'analyze-card-costs.py');elapsed=load('destination_elapsed',parent/'tracking-elapsed/analyze.py');cadence=load('destination_cadence',parent/'tracking-cadence/analyze.py');normalizer=load('destination_normalizer',repo/'tools/card-shell-board-session.py')
 manifest=json.loads((directory/'manifest.json').read_text());control=json.loads((directory/'result.json').read_text());budgets={};runs={}
 assert [r['label'] for r in control['runs']]==['journal','file','journal-return']
 assert all(r['exit']==0 for r in control['runs']) and control['restored_properties']==control['original_properties']
 assert not control['restore_timer_active'] and control['test_input_devices']==0 and all(control['normal_services'].values())
 for role,destination in [('journal','journal'),('file','file'),('journal-return','journal')]:
  folder=directory/role/'3-cards';raw=(folder/'telemetry.log').read_bytes();assert normalizer.normalized_journal(raw.decode())==raw.decode()
  meta=json.loads((folder/'metadata.json').read_text());assert meta['log_destination']==destination and len(meta['gestures'])==6
  budgets[role]=costs.replay(directory/role,manifest);frozen=budgets[role]['runs'][0]
  e=elapsed.analyze(raw,costs.benchmark);c=cadence.describe(raw)
  assert e['cards']=='3' or e['cards']==3
  assert all(f['attempts']==1 for f in e['frames'] if f['has_correlated_input'])
  a=frozen['metrics']['tracking_present_interval_ms'];assert (c['tracking_present_interval_ms']['count'],c['tracking_present_interval_ms']['p95'])==(a['count'],a['p95'])
  rows,_=costs.benchmark.parse_rows(raw);head=next(r for r in rows if r['event']=='session')
  j=json.loads((folder/'journal-resources.json').read_text());assert j['unit']=='systemd-journald.service'
  cpu=cpu_window(j['samples'],head['t_ns'],meta['back_requested_ns'])
  runs[role]={'elapsed':e,'cadence':c,'journal_cpu_active':cpu,'frozen_metrics':frozen['metrics'],'excluded_input_pauses':frozen['excluded_input_pauses'],'missing_evidence':frozen['missing_evidence'],'telemetry_lines':len(raw.splitlines())}
 result={'runs':runs,'limits':['Same reused0v1/2778 binary and six35-motion700ms native-uinput workload; still landscape8ms throughout.','Each arm restarts the session; one journal/file/journal sequence cannot isolate order effects or prove causality.','File logging redirects session stderr, including inherited child descriptors; it does not disable log formatting or writes.','File export normalizes the whole captured stderr suffix; journal export prefilters selected telemetry families. Additional fixed-grammar rows in file export do not replace or drop any frozen metric.','Journal CPU covers the global service; unrelated logging can contribute. Frozen session resources still contain only shell and shell-ui.','Native-injected/backend evidence is distinct from real-finger and optical acceptance. Frozen target is unchanged; reports retain portrait geometry and missing one-card companion warnings for these three-card-only diagnostics.']}
 (directory/'destination-analysis.json').write_text(json.dumps(result,indent=2)+'\n');(directory/'budget-analysis.json').write_text(json.dumps(budgets,indent=2)+'\n')
 return result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--repo',required=True,type=Path);a=p.parse_args();v=replay(a.directory,a.repo)
 for role,r in v['runs'].items():print(role,json.dumps({'elapsed_p95_ms':r['elapsed']['groups']['correlated']['render_wall_ms']['p95'],'tracking_p95_ms':r['frozen_metrics']['tracking_present_interval_ms']['p95'],'journal_active_average_cores':r['journal_cpu_active']['average_cores']}))
