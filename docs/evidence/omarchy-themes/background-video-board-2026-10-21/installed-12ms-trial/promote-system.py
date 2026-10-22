from pathlib import Path
import os,json,hashlib,subprocess,shutil,signal,datetime
root=Path('/var/lib/k230/render12-20261021');stage=root/'promotion';boot=Path('/boot');profile=Path('/nix/var/nix/profiles/system');new='/nix/store/8xkkpma4fvgw4fi6pl8qaz7d9d75kcdi-nixos-system-nixos-26.11.20260919.20b1ddd';old='/nix/store/2igpibpw4nn0clbda7p35dp5bhg28n35-nixos-system-nixos-26.11.20260919.20b1ddd'
sha=lambda p:hashlib.file_digest(Path(p).open('rb'),'sha256').hexdigest()
expected={'k230-tdisplay.dtb':('ad16d217f59d8ead079f6395535071fb56b33b9d480773491f7fca638a2b8823','8d302c9412a2dc42897896098d66e7d0cddeb7aee403edae734b5804e59dcda4'),'bootargs.txt':('ee635a63e41b750fba52b56900a0f04a8fab66ebd4966a57534c53bab2689c7b','9b70ee98fc04ddfb96633f0aca34d09b0b71496692beca9bf94bc3029ee82850')}
assert str(Path('/run/current-system').resolve())==new and str(Path('/run/booted-system').resolve())==old and str(profile.resolve())==old
assert sha('/sys/kernel/notes')=='1a98ea1e0a6e75f923c0fd53cfcf472f576ddb36de86b89361bfc224a305d9b6'
assert not any(Path('/run/systemd/system/shell.service.d').glob('*')) if Path('/run/systemd/system/shell.service.d').exists() else True
for name,(previous,current) in expected.items():
 assert sha(boot/name)==previous and sha(stage/name)==current
 assert (boot/name).read_bytes().count(old.encode())==1 and (boot/name).read_bytes().replace(old.encode(),new.encode())==(stage/name).read_bytes()
assert shutil.disk_usage(boot).free>1048576 and shutil.disk_usage('/').free>16*1048576
backup=stage/'rollback';backup.mkdir(mode=0o700)
for name in expected:
 with (boot/name).open('rb') as src,(backup/name).open('xb') as dst:shutil.copyfileobj(src,dst);dst.flush();os.fsync(dst.fileno())
for name,system in [('accepted-system-root',new),('rollback-system-root',old)]:
 p=root/name;assert not p.exists();subprocess.run(['nix-store','--add-root',str(p),'--indirect','--realise',system],capture_output=True,check=True,timeout=30)
def protected():
 result={}
 for p in boot.iterdir():
  if p.name in expected:continue
  if p.is_symlink():result[p.name]={'symlink':os.readlink(p)}
  elif p.is_file():result[p.name]={'sha256':sha(p),'bytes':p.stat().st_size}
  else:result[p.name]={'directory':True}
 return result
before=protected();state={'phase':'ROLLBACK_PROTECTED','started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'previous_system':old,'candidate_system':new,'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'expected':expected,'protected_before':before,'source_revision':'154225653e80df13868f11fc5651a44d60cb5a7f','ordinary_boot_verified':False}
def save():
 tmp=stage/'receipt.new';tmp.write_text(json.dumps(state,indent=2)+'\n');tmp.replace(stage/'receipt.json')
def replace(src,dest,expected_hash):
 assert sha(src)==expected_hash and not dest.is_symlink()
 tmp=dest.with_name(dest.name+'.render12-new');assert not tmp.exists()
 with src.open('rb') as inp,tmp.open('xb') as out:shutil.copyfileobj(inp,out);out.flush();os.fsync(out.fileno())
 assert sha(tmp)==expected_hash;tmp.chmod(0o644);os.replace(tmp,dest);os.sync();assert sha(dest)==expected_hash
def interrupt(signum,frame):raise InterruptedError('promotion interrupted')
for sig in [signal.SIGHUP,signal.SIGTERM,signal.SIGINT]:signal.signal(sig,interrupt)
save()
try:
 for name in ['k230-tdisplay.dtb','bootargs.txt']:
  state['phase']='replacing-'+name;save();replace(stage/name,boot/name,expected[name][1])
 assert protected()==before
 subprocess.run(['nix-env','--profile',str(profile),'--set',new],capture_output=True,check=True,timeout=60)
 assert str(profile.resolve())==new and all(sha(boot/n)==h[1] for n,h in expected.items())
 state.update(phase='PERSISTENT_SELECTED',finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),profile_after=str(profile.resolve()),protected_after=protected());save()
except BaseException as e:
 state.update(phase='ROLLING_BACK',error_class=type(e).__name__);save()
 for name in expected:
  (boot/(name+'.render12-new')).unlink(missing_ok=True);replace(backup/name,boot/name,expected[name][0])
 subprocess.run(['nix-env','--profile',str(profile),'--set',old],capture_output=True,check=True,timeout=60)
 state['phase']='ROLLED_BACK';save();raise
print(json.dumps(state))
