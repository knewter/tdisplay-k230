from pathlib import Path
import shutil
out=Path('/run/k230-touchrate8-20261021')
for role in ['basic-private','basic-result']:
 s=Path('/run/shell/touchrate8-'+role);d=out/role
 if s.exists() and not d.exists():
  assert s.is_dir() and not s.is_symlink() and not any(p.is_symlink() for p in s.rglob('*'))
  shutil.copytree(s,d);d.chmod(0o700)
