import ast
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import subprocess
import zlib
os.umask(0o077)
d=Path(__file__).resolve().parent
repo=Path('/home/jadams/tmp/k230-mainline-uart-progress-breadcrumbs-controller')
root=Path('/home/jadams/tmp/k230-mainline-probe-integration')
board=Path('/home/jadams/tmp/k230-mainline-uart-breadcrumbs-board')
build=json.loads((board/'full-build-result.private.json').read_text())
assert build['returncode']==0, 'matching full build failed'
assert len(build['output_paths'])==2, 'unknown matching build outputs'
outputs=[Path(p) for p in build['output_paths']]
bundles=[p for p in outputs if p.name.endswith('-k230-mainline-drm-trial-boot-files')]
assert len(bundles)==1
bundle=bundles[0]
assert all(p.exists() for p in outputs)
source=repo/'tools/mainline-drm-initrd-shell-trial.py'
root_source=root/'tools/mainline-drm-initrd-shell-trial.py'
names=['prepare_trial','normal_expectation','prepare_uart_progress','prepare_shell_comparison','inspect_shell_initrd','inspect_uart_progress_kernel','inspect_uart_breadcrumb_kernel','shell_pid1_bootargs','shell_pid1_transport']
def functions(p):
 return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in names}
assert functions(source)==functions(root_source), 'preparation functions differ from frozen root source'
spec=importlib.util.spec_from_file_location('breadcrumb_host_controller',source)
t=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=t
spec.loader.exec_module(t)
normal=d/'normal-report.json'
shutil.copyfile(board/'normal-report.json',normal)
report=json.loads(normal.read_text())
manifest={'system':str((bundle/'system').resolve(strict=True)),'files':{}}
for name,*_ in t.LOADS:
 if name=='fw_jump_add_uboot_head.bin':
  manifest['files'][name]={**report['boot_files'][name],'crc32':t.NORMAL_WRAPPER_CRC32}
 else:
  raw=(bundle/name).read_bytes()
  manifest['files'][name]={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'crc32':f'{zlib.crc32(raw):08x}'}
manifest_path=d/'candidate-manifest.json'
manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
started=dt.datetime.now(dt.timezone.utc).isoformat()
p=t.prepare_uart_progress(t.prepare_trial(manifest_path,bundle,normal),uart_progress_breadcrumbs=True)
assert any(str(c.parent.parent.parent.parent.parent)==str(o) for o in outputs for c in [Path(p['uart_progress_kernel']['config'])]), 'built dev output does not contain qualified config'
params=p['bootargs'].removeprefix('bootargs=').split()
assert all(params.count(v)==1 for v in (*t.SHELL_CONTROLS,'rdinit=/bin/sh',t.UART_PROGRESS_FLAG,t.UART_PROGRESS_BREADCRUMBS_FLAG,'init='+p['system']+'/init'))
assert not any(v in params for v in t.SHELL_TRACE_FLAGS)
(d/'transport.private.txt').write_text(p['transport']+'\n')
private={**p,'bundle':str(p['bundle'])}
(d/'prepared.private.json').write_text(json.dumps(private,indent=2)+'\n')
public={'schema':'k230-uart-progress-breadcrumbs-positive-host-v1','evidence_class':'host-artifact-preparation-only','started_utc':started,'completed_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'controller_revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),'frozen_root_revision':build['revision'],'matching_build_returncode':build['returncode'],'bundle':str(bundle),'system':p['system'],'files':manifest['files'],'kernel_proof':p['uart_progress_kernel'],'breadcrumb_proof':p['uart_progress_breadcrumb_kernel'],'archive_proof':p['shell_comparison'],'bootargs':p['bootargs'],'literal_transport_bytes':len(p['transport'].encode()),'same_preparation_functions_as_frozen_root':True,'matching_dev_output_realized':True,'protected_normal_report_accepted':True,'protected_wrapper_anchored_to_prior_normal_report':True,'load_ranges_validated':True,'actual_payload_and_wrapper_checks':True,'registration_absence_assertion_in_prepost_helper':"assert not Path('/nix-path-registration').exists() and not Path('/nix-path-registration').is_symlink()" in p['helper_text'],'manifest_sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest(),'uart_opened':False,'board_commands_sent':False,'implicit_build_performed':False,'physical_result':'UNVERIFIED'}
(d/'positive-host-receipt.json').write_text(json.dumps(public,indent=2)+'\n')
print('Positive host preparation passed; receipt written privately.')
print('Bundle:',bundle)
print('Literal transport bytes:',public['literal_transport_bytes'])
