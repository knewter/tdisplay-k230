from datetime import datetime, timezone
from pathlib import Path
import hashlib, json, subprocess
root=Path('/home/jadams/.local/state/tdisplay-k230/retained-builds/coherent-help-2026-10-10')
previous=Path('/home/jadams/.local/state/tdisplay-k230/retained-builds/theme-foot-2026-10-10/build-inputs.json')
graph=json.loads(Path('/home/jadams/tmp/k230-help-derivations.json').read_text())['derivations']
prior={entry['path'] for entry in json.loads(previous.read_text())}
paths=set(prior); omitted=set()
selected=['/nix/store/fk3w6gym9vd1fnybdp3ppmiqqpsjf03m-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0.drv']
for drv in selected:
 paths.update(subprocess.check_output(['nix-store','--query','--requisites',drv],text=True).splitlines())
for name,drv in graph.items():
 paths.add('/nix/store/'+name)
 paths.update('/nix/store/'+source for source in drv['inputs'].get('srcs',[]))
 for label,output in drv['outputs'].items():
  value=output.get('path')
  if value and Path('/nix/store/'+value).exists(): paths.add('/nix/store/'+value)
  else: omitted.add((name,label,value))
for drv in selected:
 out='/nix/store/'+graph[Path(drv).name]['outputs']['out']['path']
 subprocess.run(['nix-store','--check-validity',out],check=True)
subprocess.run(['nix-store','--check-validity',*sorted(paths)],check=True)
(root/'build-inputs.json').write_text(json.dumps([{'name':f'path-{i:05d}','path':path} for i,path in enumerate(sorted(paths))],indent=2)+'\n')
(root/'retain.nix').write_text('''let f = builtins.getFlake "/home/jadams/tmp/k230-coherent-closeout-2026-10-10";
    p = f.inputs.nixpkgs.legacyPackages.x86_64-linux;
    paths = builtins.fromJSON (builtins.readFile ./build-inputs.json);
in p.linkFarm "tdisplay-k230-retained-coherent-help-build-inputs"
  (builtins.map (entry: { inherit (entry) name; path = builtins.storePath entry.path; }) paths)
''')
receipt={'observed_utc':datetime.now(timezone.utc).isoformat(),'selected_derivations':selected,
 'prior_retained_paths':len(prior),'retained_paths':len(paths),'newly_retained_paths':len(paths-prior),
 'manifest_sha256':hashlib.sha256((root/'build-inputs.json').read_bytes()).hexdigest(),
 'graph_derivations':len(graph),'unrealized_outputs_omitted':len(omitted),
 'enumeration':'Previous verified farm union recursive selected derivation sources and all currently realized declared outputs; nix-store --check-validity passed for every retained path.',
 'global_policy_changed':False,'root':str(root/'build-closure')}
(root/'retention.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(len(paths),'valid retained paths;',len(paths-prior),'added')
