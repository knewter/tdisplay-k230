"""Executed fixed autonomous Bash PID1 artifact qualifier; no UART or build.

Copy this exact file to a fresh mode-0700 ~/tmp directory before executing.
Requires host Python 3.14 native zstd support for the unchanged archived initrd.
"""
import argparse,ast,hashlib,importlib.util,json,os,shutil,subprocess,sys,uuid
from datetime import datetime,timezone
from pathlib import Path
from compression import zstd
os.umask(0o077)
d=Path(__file__).resolve().parent
assert d.stat().st_uid==os.getuid() and d.stat().st_mode&0o077==0
repo=Path('/home/jadams/tmp/k230-mainline-autonomous-pid1-controller')
native_repo=Path('/home/jadams/tmp/k230-mainline-probe-integration')
board=Path('/home/jadams/tmp/k230-mainline-uart-memory-printk-nohz-board')
fullpath=Path('/home/jadams/tmp/k230-mainline-uart-memory-printk-board/full-build-result.private.json')
p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True);p.add_argument('--dev',type=Path,required=True);p.add_argument('--normal-report',type=Path,required=True);a=p.parse_args()
assert str(a.bundle)=='/nix/store/p2kdar89q7dhwdajjy0mrhmxxzcgsalw-k230-mainline-drm-trial-boot-files'
assert str(a.dev)=='/nix/store/24hbalyljs6gn6fzkkl24znv8a0x6jdl-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-dev'
full=json.loads(fullpath.read_text());assert full['returncode']==0 and full['revision']=='1c59f8565ce6baab1e97ffad23e55556961af308'
assert str(a.bundle)in full['output_paths'] and str(a.dev)in full['output_paths']
assert a.bundle.is_dir() and a.dev.is_dir() and a.normal_report.is_file() and not a.normal_report.is_symlink()
controller=native_repo/'tools/mainline-drm-initrd-shell-trial.py'
spec=importlib.util.spec_from_file_location('autonomous_qualification_trial',controller);t=importlib.util.module_from_spec(spec);sys.modules[spec.name]=t;spec.loader.exec_module(t)
# Exact checkpoint implementation; default shared preparation is unchanged.
frozen=subprocess.check_output(['git','show','d988bb08:tools/mainline-drm-initrd-shell-trial.py'],cwd=repo,text=True)
assert controller.read_text()==frozen
old=subprocess.check_output(['git','show','703e9105:tools/mainline-drm-initrd-shell-trial.py'],cwd=repo,text=True)
names={'prepare_trial','normal_expectation','prepare_uart_memory_printk','prepare_uart_progress','inspect_shell_initrd','inspect_uart_progress_kernel','inspect_uart_memory_kernel','observe_uart_progress','uart_memory_summary','uart_memory_printk_summary','linux_console_prefix','linux_console_backend','shell_pid1_bootargs','shell_pid1_transport'}
def defs(text):
 result={n.name:ast.dump(n,include_attributes=False)for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)and n.name in names}
 assert set(result)==names
 return result
assert defs(controller.read_text())==defs(old)
normal=d/'normal-report.json';manifest=d/'candidate-manifest.json';prepared_file=d/'prepared.private.json';result=d/'result.json';transport=d/'transport.private.txt'
assert all(not x.exists()for x in (normal,manifest,prepared_file,result,transport))
shutil.copyfile(a.normal_report,normal);shutil.copyfile(board/'candidate-manifest.json',manifest)
started=datetime.now(timezone.utc).isoformat()
t.validate_autonomous_selector(True,True,'minimal')
base=t.prepare_uart_memory_printk(t.prepare_trial(manifest,a.bundle,normal))
selected=t.prepare_autonomous_bash(t.prepare_trial(manifest,a.bundle,normal),uuid.uuid4().hex)
selected['autonomous_native_proof']=t.qualify_autonomous_native(selected,proof_repo=native_repo)
assert Path(selected['uart_progress_kernel']['config'])==a.dev/'lib/modules/7.3.0-rc5/build/.config'
oldproof=json.loads((repo/'docs/evidence/mainline-uart-progress-memory-printk/positive-controller-host/result.json').read_text())
for key,previous in (('uart_progress_kernel','kernel_proof'),('uart_progress_memory_printk_kernel','memory_printk_proof'),('shell_comparison','archive_proof')):
 assert base[key]==oldproof[previous] and selected[key]==base[key]
assert selected['helper_text']==base['helper_text'] and selected['normal']==base['normal'] and selected['manifest']==base['manifest']
assert hashlib.sha256(manifest.read_bytes()).hexdigest()==oldproof['manifest_sha256']
assert selected['uart_progress_memory_printk_kernel']['worker_sha256']=='30e8eb1ee365d62665c9d3ffd674e973736f3d04405d53f0f5dc12c3ee23f5f2'
assert len(t.autonomous_bash_script(selected['autonomous_nonce']).encode())==154
assert len(selected['bootargs'].removeprefix('bootargs=').encode())==477
assert len(selected['transport'].encode())==503
assert all(x not in selected['bootargs'] for x in ('k230.uart_progress','k230.boot_trace','nohz=','nohlt','initcall_debug'))
assert selected['bootargs']==t.shell_pid1_bootargs((a.bundle/'bootargs.txt').read_text(),selected['system'])+' -- -c "'+t.autonomous_bash_script(selected['autonomous_nonce'])+'"'
assert selected['transport']==t.autonomous_bash_transport(selected['bootargs'],selected['system'],selected['autonomous_nonce'])
subprocess.run(['sha256sum','--check','SHA256SUMS'],cwd=a.bundle,capture_output=True,check=True,timeout=30)
original=(a.bundle/'bootargs.txt').read_text()
assert subprocess.check_output(['fdtget','-t','s',str(a.bundle/'k230-tdisplay-mainline-drm.dtb'),'/chosen','bootargs'],text=True,timeout=20).strip()==original.strip().removeprefix('bootargs=')
assert all(selected['manifest']['files'][name]==base['manifest']['files'][name] for name,*_ in t.LOADS)
transport.write_text(selected['transport']+'\n');prepared_file.write_text(json.dumps(selected,indent=2,default=str)+'\n')
safe={'schema':'k230-autonomous-bash-pid1-positive-host-v1','evidence_class':'actual-existing-artifact-host-preparation-only',
 'started_utc':started,'completed_utc':datetime.now(timezone.utc).isoformat(),
 'controller_revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=native_repo,text=True).strip(),
 'author_controller_revision':'d988bb08',
 'controller_source_sha256':hashlib.sha256(controller.read_bytes()).hexdigest(),
 'original_full_build_revision':full['revision'],'original_full_build_returncode':0,
 'bundle':str(a.bundle),'system':selected['system'],'dev':str(a.dev),'files':oldproof['files'],
 'kernel_proof':selected['uart_progress_kernel'],'memory_printk_artifact_proof':selected['uart_progress_memory_printk_kernel'],
 'archive_proof':selected['shell_comparison'],'autonomous_archive_proof':selected['autonomous_archive'],
 'native_proof':selected['autonomous_native_proof'],
 'fixed_script_bytes':154,'selected_raw_kernel_arguments_bytes':477,'selected_single_Hush_command_bytes':503,'with_CR_bytes':504,
 'old_shared_preparation_and_observer_AST_unchanged':True,'same_artifacts_manifest_loads_normal_helper':True,
 'bundle_SHA256SUMS_passed':True,'DT_original_bootargs_match':True,'no_reporter_trace_or_tick_gates_selected':True,
 'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),
 'original_full_build_receipt_sha256':hashlib.sha256(fullpath.read_bytes()).hexdigest(),
 'qualification_command_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
 'normal_report_class':'protected historical host-only anchor; no fresh recovery/preflight',
 'registration_absence_assertion_in_prepost_helper':"assert not Path('/nix-path-registration').exists() and not Path('/nix-path-registration').is_symlink()"in selected['helper_text'],
 'candidate_input_policy':'zero writes after bootm','capture_seconds_planned':60,'receipt_status_planned':'NOT_REQUESTED','rx_status_planned':'NOT_TESTED',
 'performed_board_preflight':False,'uart_opened':False,'implicit_build_performed':False,
 'installed_Hush_firmware_ABI_verified':False,'Bash_sleep_or_builtin_execution_verified':False,
 'physical_result':'UNVERIFIED','usable_root':'UNVERIFIED','touch':'UNVERIFIED'}
assert safe['registration_absence_assertion_in_prepost_helper']
result.write_text(json.dumps(safe,indent=2)+'\n')
print('Actual autonomous Bash PID1 host qualification PASS;154/477/503 bytes;no UART/build.')
