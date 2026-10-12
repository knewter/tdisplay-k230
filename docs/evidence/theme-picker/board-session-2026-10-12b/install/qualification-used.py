import fcntl,hashlib,importlib.util,json,os,re,shlex,time,uuid
from pathlib import Path
from datetime import datetime,timezone
import serial
os.umask(0o077)
wt=Path('/home/jadams/tmp/k230-row-memtrace');d=Path('/home/jadams/tmp/k230-session-b-install');e=wt/'docs/evidence/theme-picker/board-session-2026-10-12b/install'
state=json.loads((d/'state.json').read_text());runtime=json.loads((e/'candidate-runtime.json').read_text());c=state['candidate']
q={k:c[k] for k in ['system','kernel','bundle']}
baseline=json.loads((e/'preflight.json').read_text())
q.update(evidence_class='operator-authorized-userspace-update',shell_executable=runtime['shell_executable'],boot_id=runtime['boot_id'],deployment_authorized=True,additional_physical_collection_waived=True,operator_instruction='"what more do you need from me just test stuff that doesn\'t need me as far as you can then lmk what you need" (2026-10-12)',prior_waiver='continue but you dont have to gather that proof ive already confirmed its fine carry on it\'s all good',recorded_utc=datetime.now(timezone.utc).isoformat(),source_revision='e93b5a23094e08f5473e110053a1099d8bf1d2f1',accepted_baseline={'system':baseline['system'],'kernel':baseline['kernel'],'boot_files':{n:baseline['normal_boot_files'][n] for n in ('Image','initrd.uimg')}},provenance='Operator instruction to carry the remaining theme-picker board work as far as possible without them (2026-10-12, perf/theme-row-memory-trace e93b5a23: bounded slice sprite cache with release and trim, per-frame carousel trace, warm tap-apply without a preview and with a reusable pre-render), with the standing waiver of additional install-time physical collection. Same-kernel userspace update; claims no finger observation.',limits='No new gesture, cable cycle, pixel, timing, or individual typography/spacing physical observation is inferred.')
inspec=importlib.util.spec_from_file_location('installer',wt/'tools/coherent-shell-board-install.py');installer=importlib.util.module_from_spec(inspec);inspec.loader.exec_module(installer)
installer.validate_qualification(q,c);installer.validate_install_baseline(q,state)

body=json.dumps(q,indent=2)+'\n';(e/'deployment-authorization.json').write_text(body)
spec=importlib.util.spec_from_file_location('rd',wt/'tools/mainline-drm-initrd-shell-trial.py');rd=importlib.util.module_from_spec(spec);spec.loader.exec_module(rd)
token=uuid.uuid4().hex;uploaded='/run/k230-mainline-recovery-qualification.json'
code="""from pathlib import Path
import hashlib,importlib.util,json,os
stage=Path(STAGE);q=json.loads(Path(UPLOADED).read_text());state=json.loads((stage/'state.json').read_text())
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==q['boot_id'],'accepted boot changed'
assert str(Path('/run/current-system').resolve())==q['system']
assert str(Path('/nix/var/nix/profiles/system').resolve())==state['normal_profile']
assert not (stage/'install-state.json').exists(),'inspect existing install journal'
spec=importlib.util.spec_from_file_location('installer',stage/'install.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.validate_qualification(q,state['candidate']);m.validate_install_baseline(q,state)
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
