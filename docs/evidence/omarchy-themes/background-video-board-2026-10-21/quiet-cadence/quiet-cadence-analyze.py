"""Replay unchanged card gates for file-logged 8/12/8ms scheduling arms."""
from pathlib import Path
import argparse,importlib.util,json

def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def replay(directory,repo):
 parent=repo/'docs/evidence/omarchy-themes/background-video-board-2026-10-21'
 logger=load('quiet_logger',parent/'log-destination/log-destination-analyze.py')
 costs=load('destination_costs',parent/'analyze-card-costs.py');elapsed=load('destination_elapsed',parent/'tracking-elapsed/analyze.py');cadence=load('destination_cadence',parent/'tracking-cadence/analyze.py');normalizer=load('destination_normalizer',repo/'tools/card-shell-board-session.py')
 manifest=json.loads((directory/'manifest.json').read_text());control=json.loads((directory/'result.json').read_text());budgets={};runs={}
 assert [r['label'] for r in control['runs']]==['8ms-before','12ms','8ms-return']
 assert [r['allowance_ms'] for r in control['runs']]==[8,12,8]
 assert all(r['destination']=='file' and r['fd2_kind']=='regular-file' for r in control['runs'])
 assert all(r['exit']==0 for r in control['runs']) and control['restored_properties']==control['original_properties']
 assert not control['restore_timer_active'] and control['test_input_devices']==0 and all(control['normal_services'].values())
 for role,allowance in [('8ms-before',8),('12ms',12),('8ms-return',8)]:
  destination='file'
  observed=next(r for r in control['runs'] if r['label']==role)
  assert observed['identity']['outputs'][0]['max_render_time']==allowance
  folder=directory/role/'3-cards';raw=(folder/'telemetry.log').read_bytes();assert normalizer.normalized_journal(raw.decode())==raw.decode()
  meta=json.loads((folder/'metadata.json').read_text());assert meta['log_destination']==destination and len(meta['gestures'])==6
  assert meta['output']['max_render_time']==allowance
  budgets[role]=costs.replay(directory/role,manifest);frozen=budgets[role]['runs'][0]
  e=elapsed.analyze(raw,costs.benchmark);c=cadence.describe(raw)
  assert e['cards']=='3' or e['cards']==3
  assert all(f['attempts']==1 for f in e['frames'] if f['has_correlated_input'])
  a=frozen['metrics']['tracking_present_interval_ms'];assert (c['tracking_present_interval_ms']['count'],c['tracking_present_interval_ms']['p95'])==(a['count'],a['p95'])
  rows,_=costs.benchmark.parse_rows(raw);head=next(r for r in rows if r['event']=='session')
  j=json.loads((folder/'journal-resources.json').read_text());assert j['unit']=='systemd-journald.service'
  cpu=logger.cpu_window(j['samples'],head['t_ns'],meta['back_requested_ns'])
  runs[role]={'allowance_ms':allowance,'elapsed':e,'cadence':c,'journal_cpu_active':cpu,'frozen_metrics':frozen['metrics'],'excluded_input_pauses':frozen['excluded_input_pauses'],'missing_evidence':frozen['missing_evidence'],'telemetry_lines':len(raw.splitlines())}
 result={'runs':runs,'limits':['Same reused0v1/2778binary, file logging and six35motion700ms native-uinput workload in all arms; still landscape throughout.', 'Each arm restarts the session; one8/12/8sequence does not isolate order/cache/observer effects or establish causality.', 'Only output max_render_time varies8/12/8ms at runtime;normal8ms,journalrouting and original compositor restored; no default changed.', 'Journal CPU is global and can include unrelated logs; frozen session resources remain shell and shell-ui only.', 'All-present intervals remain diagnostic; frozen input-correlated tracking target is unchanged.', 'Three-card still-only native-injected/backend evidence does not supply full paired still/video, one/multiple-card, portrait, real-finger or optical acceptance.']}
 (directory/'quiet-analysis.json').write_text(json.dumps(result,indent=2)+'\n');(directory/'budget-analysis.json').write_text(json.dumps(budgets,indent=2)+'\n')
 return result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--repo',required=True,type=Path);a=p.parse_args();v=replay(a.directory,a.repo)
 for role,r in v['runs'].items():print(role,json.dumps({'elapsed_p95_ms':r['elapsed']['groups']['correlated']['render_wall_ms']['p95'],'tracking_p95_ms':r['frozen_metrics']['tracking_present_interval_ms']['p95'],'journal_active_average_cores':r['journal_cpu_active']['average_cores']}))
