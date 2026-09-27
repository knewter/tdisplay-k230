set -e
export PATH=/run/current-system/sw/bin:/run/wrappers/bin
test "$(readlink -e /run/current-system)" = '/nix/store/cmhsqwvzwp3bad15wv5znk4w35wx65d5-nixos-system-nixos-26.11.20260919.20b1ddd'
test "$(readlink -e /run/booted-system)" = '/nix/store/cmhsqwvzwp3bad15wv5znk4w35wx65d5-nixos-system-nixos-26.11.20260919.20b1ddd'
test "$(readlink -e /nix/var/nix/profiles/system)" = '/nix/store/cmhsqwvzwp3bad15wv5znk4w35wx65d5-nixos-system-nixos-26.11.20260919.20b1ddd'
systemctl is-active --quiet shell.service shell-ui.service shell-keyboard.service theme-helper.service
echo K230_TRACE_BOOT_IDENTITIES_MATCH
echo K230_TRACE_BOOT_SERVICES_HEALTHY
/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3 - <<'PYBOOT'
import json,subprocess,time,os
def ipc(c,kind=None):
 a=['swaymsg','-s','/run/shell/sway-ipc.sock','-r']
 if kind:a+=['-t',kind]
 return json.loads(subprocess.check_output(a+[c]))
def nodes(n):
 yield n
 for c in n.get('nodes',[])+n.get('floating_nodes',[]):yield from nodes(c)
assert subprocess.check_output(['runuser','-u','shell','--','env','XDG_DATA_DIRS=/run/current-system/sw/share','xdg-mime','query','default','text/markdown'],text=True).strip()=='k230-editor.desktop'
ipc('exec /nix/store/nvnmlbqxh4m5kgw1qa4aj20r6vw1w4xm-omawrite-riscv64-unknown-linux-gnu-0-unstable-2026-08-07/bin/omawrite')
for _ in range(60):
 a=[n for n in nodes(ipc('','get_tree')) if n.get('app_id')=='omawrite']
 if a:
  assert os.readlink('/proc/'+str(a[0]['pid'])+'/exe')=='/nix/store/nvnmlbqxh4m5kgw1qa4aj20r6vw1w4xm-omawrite-riscv64-unknown-linux-gnu-0-unstable-2026-08-07/bin/.omawrite-wrapped'
  print('K230_TRACE_BOOT_EDITOR_RUNNING',flush=True)
  break
 time.sleep(.5)
else:raise AssertionError('editor did not launch after normal boot')
PYBOOT
