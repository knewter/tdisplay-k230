"""Actual existing MemoryPrintk nohz-off host qualifier; no build or UART."""
import argparse,ast,hashlib,importlib.util,json,os,shutil,subprocess,sys,types
from datetime import datetime,timezone
from pathlib import Path
from compression import zstd
os.umask(0o077)
d=Path(__file__).resolve().parent
assert d.stat().st_uid==os.getuid() and d.stat().st_mode&0o077==0
repo=Path('/home/jadams/tmp/k230-mainline-uart-progress-memory-printk-nohz-controller')
board=Path('/home/jadams/tmp/k230-mainline-uart-memory-printk-board')
p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True);p.add_argument('--dev',type=Path,required=True);p.add_argument('--normal-report',type=Path,required=True);a=p.parse_args()
assert str(a.bundle)=='/nix/store/p2kdar89q7dhwdajjy0mrhmxxzcgsalw-k230-mainline-drm-trial-boot-files'
assert str(a.dev)=='/nix/store/24hbalyljs6gn6fzkkl24znv8a0x6jdl-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-dev'
fullpath=board/'full-build-result.private.json';full=json.loads(fullpath.read_text())
assert full['returncode']==0 and full['revision']=='1c59f8565ce6baab1e97ffad23e55556961af308'
assert str(a.bundle)in full['output_paths'] and str(a.dev)in full['output_paths']
assert a.bundle.exists() and a.dev.exists() and a.normal_report.is_file() and not a.normal_report.is_symlink()
controller=repo/'tools/mainline-drm-initrd-shell-trial.py'
spec=importlib.util.spec_from_file_location('nohz_qualifier_trial',controller);t=importlib.util.module_from_spec(spec);sys.modules[spec.name]=t;spec.loader.exec_module(t)
frozen=subprocess.check_output(['git','show','fcd1020f:tools/mainline-drm-initrd-shell-trial.py'],cwd=repo,text=True)
# Only functions unchanged by this increment are required byte-equivalent in AST.
names={'prepare_trial','normal_expectation','prepare_uart_memory_printk','prepare_uart_progress','inspect_shell_initrd','inspect_uart_progress_kernel','inspect_uart_memory_kernel','observe_uart_progress','uart_memory_summary','uart_memory_printk_summary','linux_console_prefix','linux_console_backend','shell_pid1_bootargs'}
def defs(source):
 x={n.name:ast.dump(n,include_attributes=False)for n in ast.parse(source).body if isinstance(n,ast.FunctionDef)and n.name in names}
 assert set(x)==names
 return x
assert defs(controller.read_text())==defs(frozen)
old=types.ModuleType('frozen_nohz_default');old.__file__=str(controller);sys.modules[old.__name__]=old;exec(compile(frozen,str(controller),'exec'),old.__dict__)
normal=d/'normal-report.json';manifest=d/'candidate-manifest.json';prepared=d/'prepared.private.json';result=d/'result.json';transport=d/'transport.private.txt'
assert all(not x.exists()for x in (normal,manifest,prepared,result,transport))
shutil.copyfile(a.normal_report,normal);shutil.copyfile(board/'candidate-manifest.json',manifest)
started=datetime.now(timezone.utc).isoformat()
t.validate_uart_memory_printk_nohz_off_selector(True,True,True,True,True,True,'minimal')
base=t.prepare_uart_memory_printk(t.prepare_trial(manifest,a.bundle,normal));selected=t.prepare_uart_memory_printk_nohz_off(base)
assert Path(base['uart_progress_kernel']['config'])==a.dev/'lib/modules/7.3.0-rc5/build/.config'
assert selected['bootargs']==base['bootargs']+' nohz=off'
assert selected['transport']==base['transport'][:-1]+' nohz=off"'
assert len(base['transport'].encode())==416 and len(selected['transport'].encode())==425
for k,v in base.items():
 if k not in ('bootargs','transport'):assert selected[k]==v,k
oldproof=json.loads((repo/'docs/evidence/mainline-uart-progress-memory-printk/positive-controller-host/result.json').read_text())
for key,previous in (('uart_progress_kernel','kernel_proof'),('uart_progress_memory_printk_kernel','memory_printk_proof'),('shell_comparison','archive_proof')):assert base[key]==oldproof[previous]
assert hashlib.sha256(manifest.read_bytes()).hexdigest()==oldproof['manifest_sha256']
assert hashlib.sha256((a.bundle/'Image-mainline-drm').read_bytes()).hexdigest()==oldproof['memory_printk_proof']['image_sha256']
assert base['uart_progress_memory_kernel']['worker_sha256']=='30e8eb1ee365d62665c9d3ffd674e973736f3d04405d53f0f5dc12c3ee23f5f2'
assert selected['uart_progress_memory_printk_nohz_off_kernel']['linked_nohz_setup_offset']==19425910
system=base['system'];original=(a.bundle/'bootargs.txt').read_text();plain=t.shell_pid1_bootargs(original,system)
policies=[(plain,{}),(plain+' '+t.UART_PROGRESS_FLAG,{'uart_progress':True}),
 (plain+' '+t.UART_PROGRESS_FLAG+' '+t.UART_PROGRESS_MEMORY_FLAG,{'uart_progress':True,'uart_progress_memory':True}),
 (plain+' '+t.UART_PROGRESS_FLAG+' '+t.UART_PROGRESS_MEMORY_FLAG+' nohlt',{'uart_progress':True,'uart_progress_memory':True,'uart_progress_memory_poll_idle':True}),
 (base['bootargs'],{'uart_progress':True,'uart_progress_memory':True,'uart_progress_memory_printk':True})]
for args,kw in policies:assert t.shell_pid1_transport(args,system,**kw)==old.shell_pid1_transport(args,system,**kw)
subprocess.run(['sha256sum','--check','SHA256SUMS'],cwd=a.bundle,capture_output=True,check=True,timeout=30)
assert subprocess.check_output(['fdtget','-t','s',str(a.bundle/'k230-tdisplay-mainline-drm.dtb'),'/chosen','bootargs'],text=True,timeout=20).strip()==original.strip().removeprefix('bootargs=')
transport.write_text(selected['transport']+'\n');prepared.write_text(json.dumps(selected,indent=2,default=str)+'\n')
safe={'schema':'k230-memory-printk-nohz-off-positive-host-v1','evidence_class':'actual-existing-artifact-host-preparation-only',
 'started_utc':started,'completed_utc':datetime.now(timezone.utc).isoformat(),
 'controller_revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
 'controller_source_sha256':hashlib.sha256(controller.read_bytes()).hexdigest(),
 'frozen_original_artifact_revision':full['revision'],'original_full_build_returncode':0,
 'bundle':str(a.bundle),'system':system,'dev':str(a.dev),
 'kernel_proof':base['uart_progress_kernel'],'memory_printk_proof':base['uart_progress_memory_printk_kernel'],
 'nohz_off_proof':selected['uart_progress_memory_printk_nohz_off_kernel'],'archive_proof':base['shell_comparison'],
 'files':oldproof['files'],'base_bootargs':base['bootargs'],'selected_bootargs':selected['bootargs'],
 'base_literal_transport_bytes':416,'selected_literal_transport_bytes':425,'sole_added_kernel_argument':'nohz=off',
 'same_source_config_Image_initrd_DTB_archive_manifest_loads':True,'unchanged_observation_and_backend_AST':True,
 'five_existing_transport_values_unchanged':True,'bundle_SHA256SUMS_passed':True,
 'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),
 'original_full_build_receipt_sha256':hashlib.sha256(fullpath.read_bytes()).hexdigest(),
 'qualification_command_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
 'normal_report_class':'protected historical host-only anchor; no fresh recovery/preflight',
 'registration_absence_assertion_in_prepost_helper':"assert not Path('/nix-path-registration').exists() and not Path('/nix-path-registration').is_symlink()"in selected['helper_text'],
 'candidate_input_policy':'zero writes','receipt_status_planned':'NOT_REQUESTED','rx_status_planned':'NOT_TESTED',
 'performed_board_preflight':False,'uart_opened':False,'implicit_build_performed':False,
 'runtime_tick_policy':'UNVERIFIED','physical_result':'UNVERIFIED'}
assert safe['registration_absence_assertion_in_prepost_helper']
result.write_text(json.dumps(safe,indent=2)+'\n')
print('Actual existing MemoryPrintk nohz-off host qualification PASS;416->425 bytes;no UART/build.')
