from datetime import datetime, timezone
from pathlib import Path
import hashlib, json, subprocess
root=Path.home()/'.local/state/tdisplay-k230/retained-builds/coherent-combined-2026-10-10'
previous=Path.home()/'.local/state/tdisplay-k230/retained-builds/coherent-help-2026-10-10'
graph=json.loads((Path.home()/'tmp/k230-combined-derivations.json').read_text())['derivations']
prior={entry['path'] for entry in json.loads((previous/'build-inputs.json').read_text())}
selected='/nix/store/jf9kl3f2yrj2yxh0s4m6yx0s5v9n7wb0-k230-coherent-shell-boot-files.drv'
assert (root/'candidate').exists(), 'complete the selected build first'
paths=set(prior); omitted=set()
paths.update(subprocess.check_output(['nix-store','--query','--requisites',selected],text=True).splitlines())
for name,drv in graph.items():
 paths.add('/nix/store/'+name)
 paths.update('/nix/store/'+source for source in drv['inputs'].get('srcs',[]))
 for label,output in drv['outputs'].items():
  value=output.get('path')
  if value and Path('/nix/store/'+value).exists(): paths.add('/nix/store/'+value)
  else: omitted.add((name,label,value))
subprocess.run(['nix-store','--check-validity',*sorted(paths)],check=True)
extras=paths-prior
links=[str((previous/'build-closure').resolve(strict=True)),*sorted(extras)]
(root/'build-inputs.json').write_text(json.dumps([{'name':f'path-{i:05d}','path':path} for i,path in enumerate(sorted(paths))],indent=2)+'\n')
(root/'extra-inputs.json').write_text(json.dumps(links,indent=2)+'\n')
(root/'retain.nix').write_text('''let
  paths = builtins.map builtins.storePath
    (builtins.fromJSON (builtins.readFile ./extra-inputs.json));
  manifest = builtins.toFile "k230-retained-combined-paths"
    (builtins.concatStringsSep "\\n" paths + "\\n");
  bash = builtins.storePath "/nix/store/svx59425zxp552p2b8gm11qj5r09b56i-bash-5.3p15";
  coreutils = builtins.storePath "/nix/store/xjl7p8dvyk2j53kqf7f43kdj4ypbxz7g-coreutils-9.11";
in builtins.derivation {
  name = "tdisplay-k230-retained-coherent-combined-build-inputs";
  system = "x86_64-linux";
  builder = "${bash}/bin/bash";
  args = [ "-e" "-c" ''
    ${coreutils}/bin/mkdir "$out"
    index=0
    while IFS= read -r path; do
      printf -v entry 'path-%05d' "$index"
      ${coreutils}/bin/ln -s "$path" "$out/$entry"
      index=$((index + 1))
    done < ${manifest}
  '' ];
}
''')
receipt={'observed_utc':datetime.now(timezone.utc).isoformat(),'selected_derivation':selected,
 'prior_retained_paths':len(prior),'retained_paths':len(paths),'newly_retained_paths':len(extras),
 'direct_links':len(links),'prior_farm':links[0],
 'manifest_sha256':hashlib.sha256((root/'build-inputs.json').read_bytes()).hexdigest(),
 'graph_derivations':len(graph),'unrealized_outputs_omitted':len(omitted),
 'enumeration':'Previous verified farm union recursive selected derivation sources and all currently realized declared outputs. Every retained path passed nix-store --check-validity. Nested prior farm and new links use builtins.storePath context.',
 'global_policy_changed':False,'root':str(root/'build-closure')}
(root/'retention.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(len(paths),'valid retained paths;',len(extras),'added;',len(links),'direct links')
