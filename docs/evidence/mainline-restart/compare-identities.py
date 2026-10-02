import json,subprocess
from pathlib import Path
root=Path.cwd()
body='''in {
 kernel = f.packages.x86_64-linux.kernel.drvPath;
 deviceTree = f.packages.x86_64-linux.deviceTree.drvPath;
 sdImage = f.packages.x86_64-linux.sdImage.drvPath;
 system = f.nixosConfigurations.k230.config.system.build.toplevel.drvPath;
 kernelMainline = f.packages.x86_64-linux.kernelMainline.drvPath;
 deviceTreeMainline = f.packages.x86_64-linux.deviceTreeMainline.drvPath;
 consoleImageBootFiles = f.packages.x86_64-linux.kernelMainlineBootFiles.drvPath;
 consoleBootFiles = f.packages.x86_64-linux.kernelMainlineConsoleBootFiles.drvPath;
 consoleSystem = f.nixosConfigurations.k230-mainline-console.config.system.build.toplevel.drvPath;
}'''
results={}
for name,suffix in [('base','?rev=c5254075e531487af82841b3ae76582e5535f0fb'),('candidate','')]:
 uri='git+file://'+str(root)+suffix
 expr='let f = builtins.getFlake '+json.dumps(uri)+'; '+body
 results[name]=json.loads(subprocess.check_output(['nix','eval','--json','--impure','--expr',expr],text=True))
print(json.dumps(results,indent=2))
assert results['base']==results['candidate']
print('All nine default/vendor/console-only derivation identities unchanged.')
