"""Replay all original numeric gates for the complete still/video card matrix."""
from pathlib import Path
import argparse,importlib.util,json

def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def replay(directory,repo):
 parent=repo/'docs/evidence/omarchy-themes/background-video-board-2026-10-21'
 costs=load('pair_costs',parent/'analyze-card-costs.py');elapsed=load('pair_elapsed',parent/'tracking-elapsed/analyze.py');cadence=load('pair_cadence',parent/'tracking-cadence/analyze.py');logger=load('pair_logger',parent/'log-destination/log-destination-analyze.py');normalizer=load('pair_normalizer',repo/'tools/card-shell-board-session.py');video=load('pair_video',repo/'tools/theme_background_status.py')
 control=json.loads((directory/'result.json').read_text());manifest=json.loads((directory/'manifest.json').read_text());basic=json.loads((directory/'basic-result.json').read_text());expected=['static-1-cards','static-3-cards','video-1-cards','video-3-cards']
 assert [r['label'] for r in control['runs']]==expected and all(r['exit']==0 and r['allowance_ms']==8 and r['destination']=='file' for r in control['runs'])
 assert basic['trial']=='completed-needs-operator-review' and basic['restoration']=='passed' and [r['role'] for r in basic['arms']]==['static','video']
 assert not control['restore_timer_active'] and control['restored_properties']==control['original_properties'] and control['test_input_devices']==0 and all(control['normal_services'].values())
 assert control['theme_restoration']['fixture_removed'] and control['theme_restoration']['preferences_sha256']==control['theme_baseline']['preferences_sha256']
 report=costs.replay(directory,manifest);runs={}
 for row in control['runs']:
  role=row['role'];cards=row['cards'];folder=directory/row['label'];raw=(folder/'telemetry.log').read_bytes();assert normalizer.normalized_journal(raw.decode())==raw.decode();meta=json.loads((folder/'metadata.json').read_text());assert meta['log_destination']=='file' and meta['output']['max_render_time']==8 and len(meta['gestures'])==6
  rows,_=costs.benchmark.parse_rows(raw);head=next(r for r in rows if r['event']=='session');frozen=next(r for r in report['runs'] if r['run']==head['run']);assert head['cards']==cards
  e=elapsed.analyze(raw,costs.benchmark);c=cadence.describe(raw);a=frozen['metrics']['tracking_present_interval_ms'];assert (a['count'],a['p95'])==(c['tracking_present_interval_ms']['count'],c['tracking_present_interval_ms']['p95'])
  j=json.loads((folder/'journal-resources.json').read_text());cpu=logger.cpu_window(j['samples'],head['t_ns'],meta['back_requested_ns'])
  before=meta['wallpaper_before_gestures'];after=meta['wallpaper_after_gestures'];progress={'before':before,'after':after}
  assert before['generation']==after['generation']==next(r for r in control['roles'] if r['role']==role)['activation']['generation']
  if role=='video':
   if before['state']==after['state']=='playing' and before['decoder_pid']==after['decoder_pid']:
    progress['deltas']=video.progress(before,after)
   elif before['state']==after['state']=='paused-covered' and before['decoder_pid'] is None and after['decoder_pid'] is None:
    assert all(before[k]==after[k] for k in video.COUNTERS+video.TIMES)
    progress['paused_boundary_observation']={'both_paused_covered':True,'reported_counters_and_timestamps_unchanged':True,'limits':'Two boundary snapshots, not continuous state tracing; no decoder progress or active-decoding contention inferred during gestures.'}
   else:progress['limits']='Decoder identity/state changed or playback paused; no subtraction across lifetimes.'
  else:assert before['state']==after['state']=='still' and before['decoder_pid'] is None and after['decoder_pid'] is None
  runs[row['label']]={'role':role,'cards':cards,'elapsed':e,'cadence':c,'journal_cpu_active':cpu,'wallpaper_gesture_window':progress,'frozen_metrics':frozen['metrics'],'excluded_input_pauses':frozen['excluded_input_pauses'],'missing_evidence':frozen['missing_evidence']}
 cover=next(r for r in control['roles'] if r['role']=='video');assert cover['covered_counters_stopped'] and cover['covered_after']['decoder_pid'] is None
 assert all(cover['covered_before'][k]==cover['covered_after'][k] for k in video.COUNTERS)
 video.progress(cover['uncovered_before'],cover['uncovered_after'])
 result={'runs':runs,'numeric_metrics_all_pass':all(m['status']=='PASS' for r in runs.values() for m in r['frozen_metrics'].values()),'full_board_budget_gate':report['board_budget_gate'],'board_missing_evidence':report['missing_evidence'],'basic_workload':basic,'cover_resume':cover,'limits':['Four actual same-binary file-logged12ms native-uinput arms; no frozen threshold changed.','Landscape geometry warning remains; native captures/backend feedback do not prove real-finger or optical acceptance.','Raw observations with decoder state/identity changes remain incomparable; no cross-lifetime counter subtraction.','This is a candidate trial, not persistent12ms integration, image deployment, or a default-video enablement.','Existing reduced-motion startup proof uses the unchanged Rust bytes in candidate2/reduced-motion; not rerun in this trial.']}
 (directory/'paired-analysis.json').write_text(json.dumps(result,indent=2)+'\n');(directory/'budget-analysis.json').write_text(json.dumps(report,indent=2)+'\n');return result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--repo',required=True,type=Path);a=p.parse_args();v=replay(a.directory,a.repo)
 for role,r in v['runs'].items():print(role,json.dumps({'tracking':r['frozen_metrics']['tracking_present_interval_ms'],'metric_failures':{k:m['status'] for k,m in r['frozen_metrics'].items() if m['status']!='PASS'},'video_progress':r['wallpaper_gesture_window'].get('deltas',r['wallpaper_gesture_window'].get('limits'))}))
 print('all_numeric_metrics_pass',v['numeric_metrics_all_pass'])
