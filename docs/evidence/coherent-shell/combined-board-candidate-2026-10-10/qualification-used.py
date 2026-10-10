import fcntl,hashlib,importlib.util,json,os,re,shlex,time,uuid
from pathlib import Path
from datetime import datetime,timezone
import serial
os.umask(0o077)
wt=Path('/home/jadams/tmp/k230-coherent-closeout-2026-10-10');d=Path('/home/jadams/tmp/k230-coherent-combined-board-2026-10-10');e=wt/'docs/evidence/coherent-shell/combined-board-candidate-2026-10-10'
state=json.loads((d/'state.json').read_text());runtime=json.loads((e/'runtime.json').read_text());c=state['candidate']
q={k:c[k] for k in ['system','kernel','bundle']}
q.update(evidence_class='operator-real-finger-report',shell_executable=runtime['shell_executable'],boot_id=runtime['boot_id'],checks={'home_to_all_apps':True,'bottom_handle_to_overview':True,'terminal_open_and_return':True},help_navigation_buttons_accepted=True,operator_reply='it all worked land it',requested_checks='Home → All Apps; Terminal → Home; Overview; All Apps → Help → Navigation buttons → Home/Settings',recorded_utc=datetime.now(timezone.utc).isoformat(),source_revision='093a82a0c31007f775ad260492e30d3088739548',candidate_evidence_revision='cff9ec8f53ad7343fd8d219e30d10801239a5c10',provenance='Contextual operator affirmation of the requested checks on the running temporary candidate. No individual gesture trace or camera recording.',limits='No independently recorded cable cycle, timing, notification/long-press/conflict matrix, or dark/light appearance trial is inferred.')
body=json.dumps(q,indent=2)+'\n';(e/'operator-navigation.json').write_text(body)
spec=importlib.util.spec_from_file_location('rd',wt/'tools/mainline-drm-initrd-shell-trial.py');rd=importlib.util.module_from_spec(spec);spec.loader.exec_module(rd)
token=uuid.uuid4().hex;uploaded='/run/k230-mainline-coherent-qualification.json'
code="""from pathlib import Path
import hashlib,importlib.util,json,os
stage=Path(STAGE);q=json.loads(Path(UPLOADED).read_text());state=json.loads((stage/'state.json').read_text())
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==q['boot_id'],'accepted boot changed'
assert str(Path('/run/current-system').resolve())==q['system']
assert str(Path('/nix/var/nix/profiles/system').resolve())==state['normal_profile']
assert not (stage/'install-state.json').exists(),'inspect existing install journal'
spec=importlib.util.spec_from_file_location('installer',stage/'install.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.validate_qualification(q,state['candidate'])
b=Path(UPLOADED).read_bytes();assert hashlib.sha256(b).hexdigest()==SHA
assert not (stage/'qualified.json').exists()
m.save(stage/'qualified.json',q)
print(MARK,flush=True)
"""
code='STAGE='+repr(state['stage'])+'\nUPLOADED='+repr(uploaded)+'\nSHA='+repr(hashlib.sha256(body.encode()).hexdigest())+'\nMARK='+repr('K230_QUALIFIED_'+token)+'\n'+code
with open('/tmp/k230-board.lock','a') as lock,(d/'qualify-uart.private.log').open('xb',buffering=0) as log:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);s=rd.PrivateSession(serial,log)
 try:
  s.write(b'\r');assert s.wait_for(b'root@nixos',20)
  s.upload_text(uploaded,body,token)
  marker='K230_QUALIFY_RC_'+token
  s.line(shlex.join([rd.BOARD_PYTHON,'-I','-c',code])+"; printf '\\n"+marker+"=%s\\n' $?",interrupt=False)
  end=time.monotonic()+90;m=None
  while time.monotonic()<end and not m:
   s.pump();m=re.search(rb'\n'+marker.encode()+rb'=([0-9]+)\r?\n',s.buffer)
  assert m and int(m[1])==0,'qualification guard failed; private UART log retained'
  assert ('K230_QUALIFIED_'+token).encode() in s.buffer
  print('PASS: qualification guarded against exact accepted boot and staged candidate',flush=True)
 finally:s.close()
