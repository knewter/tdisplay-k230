"""Host-only replay; never opens serial or changes the original physical result."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--log',type=Path,required=True)
parser.add_argument('--original-result',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
a=parser.parse_args()
assert not a.output.exists()
repo=Path(__file__).resolve().parents[4]
spec=importlib.util.spec_from_file_location('printk_replay_fixtures',repo/'tests/test_mainline_uart_progress_memory_printk_controller.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
raw=a.log.read_bytes();original_bytes=a.original_result.read_bytes()
original=json.loads(original_bytes)
wire=f.passive.PassiveWire([raw[i:i+8192] for i in range(0,len(raw),8192)])
r=f.trial.observe_uart_progress(wire,f.old.TOKEN,original['expected_bootargs'],
    timeout=180,readiness_timeout=90,clock=f.old.Clock(),uart_progress_memory=True,
    uart_progress_memory_no_stimulus=True,uart_progress_memory_printk=True)
assert wire.writes==[] and r['stimulus_attempts']==0
fields=('candidate_banner','kernel_args_status','init_entry','primary_prompt_observed',
        'readiness_observed','stimulus_attempts','receipt_status','rx_status',
        'memory_summary','memory_summary_valid','protocol_errors','normal_prompt_observed')
old={key:original['probe'][key] for key in fields}
new={key:r[key] for key in fields}
assert not old['primary_prompt_observed'] and not old['readiness_observed']
assert new['primary_prompt_observed'] and new['readiness_observed']
assert all(old[key]==new[key] for key in fields if key not in ('primary_prompt_observed','readiness_observed'))
assert r['linux_console_backend']==original['probe']['linux_console_backend']
assert not r['normal_prompt_observed'] and r['memory_summary'] is None
assert raw.count(b'\x1b[?2004hsh-5.3# ')==1
receipt={'schema':'k230-memory-printk-readiness-host-replay-v1',
    'evidence_class':'host-only reinterpretation of saved physical capture',
    'completed_utc':datetime.now(timezone.utc).isoformat(),
    'controller_source_sha256':hashlib.sha256((repo/'tools/mainline-drm-initrd-shell-trial.py').read_bytes()).hexdigest(),
    'replay_command_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'raw_log_bytes':len(raw),'raw_log_sha256':hashlib.sha256(raw).hexdigest(),
    'original_result_sha256':hashlib.sha256(original_bytes).hexdigest(),
    'original_physical_source':'877bec0e',
    'original_physical_controller_sha256':'5c227ac0e0cd20c25447d895bb1151751f8ff1ca34efc7d37fc34aedb06d3656',
    'original_observation':old,'host_replay_observation':new,
    'linux_console_backend_unchanged':True,'raw_record_parsers_unchanged':True,
    'exact_bracketed_paste_primary_prompt_count':1,
    'original_physical_result_modified':False,'new_physical_trial':False,
    'uart_opened':False,'candidate_bytes_sent':0,
    'replay_timing':'accelerated fake clock; original arrival times and physical duration not reproduced',
    'physical_worker_output_and_return':'UNVERIFIED',
    'normal_recovery':'not performed by this host replay'}
a.output.write_text(json.dumps(receipt,indent=2)+'\n')
print('Host-only readiness replay passed; original physical result unchanged.')
