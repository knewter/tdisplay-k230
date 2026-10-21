from pathlib import Path
import hashlib,json,shutil,subprocess,sys
r=Path(__file__).parent
p=subprocess.run([sys.executable,str(r/'theme.py'),'restore'],capture_output=True,text=True,timeout=115)
(r/'recovery/theme-restore-private.log').write_text(p.stdout+p.stderr)
assert p.returncode==0,'theme restore failed; private error retained'
v=json.loads(p.stdout);receipt=json.loads((r/'fixture.private.json').read_text());f=Path('/home/shell/.config/omarchy/themes/source3-background-touchrate')
if f.exists():
 st=f.stat();assert [st.st_dev,st.st_ino]==receipt['identity']
 assert not any(p.is_symlink() for p in f.rglob('*'))
 assert {str(p.relative_to(f)):hashlib.sha256(p.read_bytes()).hexdigest() for p in f.rglob('*') if p.is_file()}==receipt['files']
 shutil.rmtree(f)
v['fixture_removed']=not f.exists();print(json.dumps(v))
