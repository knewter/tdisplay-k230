"""Confirm the paired trial against the installed 12 ms allowance with real-finger 8.14 ms drag steps.
Starts from the committed paired12 staged files (hash-checked); only owned
names and the drag step count change."""
from pathlib import Path
import ast,base64,datetime,hashlib,json,subprocess
b=Path(__file__).parent
r=Path('/mnt/MediaVolume/home/jadams/src/gitlab.daringbit.com/josh/tdisplay-k230/.claude/worktrees/bg31')
P=r/'docs/evidence/omarchy-themes/background-video-board-2026-10-21/paired12'
H=Path('/home/jadams/tmp/codex-claude-handoff-20261019/3')
staged=json.loads((P/'paired12-staged-sha256.json').read_text())
src={'run.py':'run-board.py','collect.py':'collect-board.py','theme.py':'theme.py','copy-private.py':'copy-private.py','restore-owned.py':'restore-owned.py','cadence_audit.py':'cadence_audit.py','descriptor.json':'descriptor.json'}
files={}
for k,v in src.items():
 data=(P/v).read_bytes();assert hashlib.sha256(data).hexdigest()==staged[k],k;files[k]=data.decode()
REPL=[('/run/k230-source3-paired12-code-20261021-attempt4','/run/k230-touchrateinst-code-20261021'),
 ('/run/k230-source3-paired12-20261021-attempt4','/run/k230-touchrateinst-20261021'),
 ('source3-paired12-attempt4-','touchrateinst-'),
 ('source3-background-paired12','source3-background-touchrateinst'),
 ("'96-source3-quiet-cadence.conf']","'96-source3-quiet-cadence.conf','97-source3-paired12.conf','98-touchrate.conf','99-touchrate8.conf']"),
 ('97-source3-paired12.conf\');assert not override.exists()','99-touchrateinst.conf\');assert not override.exists()'),
 ("unit='k230-source3-paired12-20261021-attempt4'","unit='k230-touchrateinst-20261021'"),
 ('"""Guarded complete still/video one/three-card diagnostic at quiet12ms."""','"""Guarded paired still/video one/three-card trial against the installed 12 ms allowance; 8.14 ms real-finger drag steps."""'),
 ("before['system']==before['profile']==m['system']","before['system']==m['system'] and before['profile']=='/nix/store/2igpibpw4nn0clbda7p35dp5bhg28n35-nixos-system-nixos-26.11.20260919.20b1ddd'"),
 ("before['outputs'][0]['max_render_time']==8","before['outputs'][0]['max_render_time']==12"),
 ('steps=35 if count>1 else 16','steps=86 if count>1 else 39')]
hits={}
for old,new in REPL:
 n=0
 for k in files:
  c=files[k].count(old);n+=c;files[k]=files[k].replace(old,new)
 assert n>0,'replacement missed: '+old;hits[old]=n
for k in files:
 for bad in ['attempt4','paired12-2026','source3-paired12-code']:assert bad not in files[k] or k=='descriptor.json',(k,bad)
m=json.loads(files['descriptor.json'])
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip()
assert subprocess.run(['git','diff','--quiet',m['reused_build_source'],'HEAD','--','nix','flake.nix','flake.lock'],cwd=r).returncode==0
m.update(source_revision=head,prepared_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),system='/nix/store/8xkkpma4fvgw4fi6pl8qaz7d9d75kcdi-nixos-system-nixos-26.11.20260919.20b1ddd',normal_sha256=m['candidate_sha256'],installed_allowance_ms=12,drag_step_ms=round(700/86,3),drag_steps=86,drag_duration_ms=700,touch_rate_basis='touch-rate/README.md')
files['descriptor.json']=json.dumps(m,indent=2)
files={k:v.encode() for k,v in files.items()}
names=sorted(n for n in staged if n.startswith('tools/'))
files['card-shell-board-session.py']=(r/'tools/card-shell-board-session.py').read_bytes()
files['workload.json']=(r/'docs/evidence/omarchy-themes/trial-workload-v1.json').read_bytes()
files.update({n:(r/n).read_bytes() for n in names})
files.update({'assets/'+p.name:p.read_bytes() for p in (H/'background-fixture').iterdir()})
for n in ['card-shell-board-session.py','workload.json','assets/01-still.png','assets/02-motion.mp4',*names]:
 if hashlib.sha256(files[n]).hexdigest()!=staged[n]:print('changed since paired12:',n)
for n,v in files.items():
 if n.endswith('.py'):ast.parse(v)
R='/var/lib/k230/touchrateinst-20261021'
code='from pathlib import Path\nimport base64,json,os,pwd,hashlib,shutil\nr=Path("'+R+'");r.mkdir(mode=0o711)\n(r/"tools").mkdir(mode=0o755)\nr.chmod(0o711);(r/"tools").chmod(0o755)\n(r/"assets").mkdir(mode=0o700)\n'
for n,v in files.items():code+='p=r/'+repr(n)+';p.write_bytes(base64.b64decode('+repr(base64.b64encode(v).decode())+'));p.chmod('+('0o600' if n=='descriptor.json' or n.startswith('assets/') else '0o644')+')\n'
code+="""public=Path('/run/k230-touchrateinst-code-20261021');public.mkdir(mode=0o711);public.chmod(0o711)
shutil.copytree(r/'tools',public/'tools');(public/'tools').chmod(0o755)
for p in (public/'tools').iterdir():p.chmod(0o644)
shutil.copyfile(r/'workload.json',public/'workload.json');(public/'workload.json').chmod(0o644)
u=pwd.getpwnam('shell')
source=Path('/nix/store/7nz37ga0jxad5x48gggjbxn15p0lkwdh-handheld-theme-default-28ceaae7/share/omarchy/themes/catppuccin-latte')
dest=Path('/home/shell/.config/omarchy/themes/source3-background-touchrateinst');assert not dest.exists();dest.mkdir(mode=0o700)
for f in source.iterdir():
 if f.is_file() and not f.is_symlink():shutil.copyfile(f,dest/f.name)
shutil.copytree(r/'assets',dest/'backgrounds')
for p in [dest,*dest.rglob('*')]:os.chown(p,u.pw_uid,u.pw_gid)
receipt={'identity':[dest.stat().st_dev,dest.stat().st_ino],'files':{str(p.relative_to(dest)):hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.rglob('*') if p.is_file()}}
p=r/'fixture.private.json';p.write_text(json.dumps(receipt));p.chmod(0o600)
print(json.dumps({'stage':str(r),'fixture':'source3-background-touchrateinst','files':len(list(r.rglob('*'))),'asset_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (r/'assets').iterdir()}}))
"""
(b/'stage.py').write_text(code)
(b/'staged-sha256.json').write_text(json.dumps({n:hashlib.sha256(v).hexdigest() for n,v in files.items()},indent=2)+'\n')
(b/'execute.py').write_text("import runpy\nrunpy.run_path('"+R+"/run.py',run_name='__main__')\n")
for k in ['run.py','collect.py','theme.py','copy-private.py','restore-owned.py','descriptor.json']:(b/('staged-'+k)).write_bytes(files[k])
print(json.dumps({'files':len(files),'bytes':sum(map(len,files.values())),'replacements':hits,'source_revision':head}))
