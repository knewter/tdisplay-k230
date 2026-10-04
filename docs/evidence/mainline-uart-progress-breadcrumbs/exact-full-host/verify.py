#!/usr/bin/env python3
"""Read-only exact-header and complete bundle proof; never opens hardware."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile

EXPECTED_SOURCE_SHA = '7207dcae9462694a07bd4f7d37d1d9ea43a536496f1b96dd94fed3dfa78c6a22'
EXPECTED_ROOT_REV = '2a54813575deecce790d4f0df048e5d3746e3d0e'
OBJECT_REV = '071086bc64418c04f7affd67ef56cddac960c896'
BASE_BUNDLE = Path('/nix/store/gmsmqkjcb8vmh6h44xvq7y59dd9xihsh-k230-mainline-drm-trial-boot-files')
BASE_DEV = Path('/nix/store/a3r0fwxh2s594xgz4amb4ydbp22l3w65-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-dev')
RECORDS = {
 'k230_uart_progress_entry': b'\nK230_UPB1 point=worker-entry\n\0',
 'k230_uart_progress_first_post_sleep': b'\nK230_UPB1 point=first-post-sleep\n\0',
}

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def run(*args): return subprocess.check_output(args, text=True)
def elf(p):
 b=p.read_bytes(); h=struct.unpack_from('<16sHHIQQQIHHHHHH',b)
 assert h[0][:6] == b'\x7fELF\x02\x01' and h[1] == 1 and h[2] == 243
 sec=[struct.unpack_from('<IIQQQQIIQQ',b,h[6]+i*h[11]) for i in range(h[12])]
 names=sec[h[13]]; names=b[names[4]:names[4]+names[5]]
 def string(data,n): return data[n:data.index(0,n)].decode()
 out={}
 for s in sec:
  if s[1] != 2: continue
  strings=sec[s[6]]; strings=b[strings[4]:strings[4]+strings[5]]
  for off in range(s[4],s[4]+s[5],s[9]):
   name,info,other,idx,value,size=struct.unpack_from('<IBBHQQ',b,off)
   if not name or idx==0 or idx>=len(sec): continue
   name=string(strings,name)
   if not name.startswith('k230_uart_progress'): continue
   t=sec[idx]
   out[name]={'section':string(names,t[0]),'section_alignment':t[8], 'value':value,'size':size}
   if name in RECORDS:
    assert b[t[4]+value:t[4]+value+size] == RECORDS[name]
    assert size<=64 and value%64==0 and t[8]>=64
    assert value%4096+size<=4096
    assert not out[name]['section'].startswith('.init')
 return out

def config(p):
 return dict(line.split('=',1) for line in p.read_text().splitlines() if line.startswith('CONFIG_') and '=' in line)

ap=argparse.ArgumentParser(); ap.add_argument('objects',type=Path); ap.add_argument('receipt',type=Path); ap.add_argument('output',type=Path); a=ap.parse_args()
a.output.mkdir(parents=True,exist_ok=True)
build=json.loads(a.receipt.read_text())
assert build['returncode']==0 and build['revision']==EXPECTED_ROOT_REV
paths=[Path(p) for p in build['output_paths']]
bundle=next(p for p in paths if (p/'bootargs.txt').is_file())
dev=next(p for p in paths if (p/'lib/modules/7.3.0-rc5/build/.config').is_file())
assert Path((a.objects/'dev-path.txt').read_text().strip())==dev
source=Path((a.objects/'source-path.txt').read_text().strip())
assert source==Path('/nix/store/k5a5zrhqy9ypr3mja1r50mdlcgi74i1f-linux-mainline-k230-uart-progress-breadcrumbs-src')
assert sha(source/'drivers/soc/canaan/k230-uart-progress.c')==EXPECTED_SOURCE_SHA
base_source=Path('/nix/store/4av3w0kigacwah6w04zfpnky4gsh0k59-linux-mainline-k230-uart-progress-src')
source_comparison={}
for relative in ('drivers/tty/serial/8250/8250_core.c','drivers/tty/serial/8250/8250.h','drivers/clocksource/timer-riscv.c','include/linux/serial_8250.h','include/linux/clocksource.h','drivers/soc/canaan/Kconfig'):
 assert (source/relative).read_bytes()==(base_source/relative).read_bytes()
 source_comparison[relative]=sha(source/relative)
cpath=dev/'lib/modules/7.3.0-rc5/build/.config'; hpath=dev/'lib/modules/7.3.0-rc5/build/include/generated/autoconf.h'
assert cpath.read_bytes()==(a.objects/'installed-kernel.config').read_bytes()
assert hpath.read_bytes()==(a.objects/'installed-autoconf.h').read_bytes()
cfg=config(cpath)
for key in ('K230_UART_PROGRESS','SERIAL_8250','SERIAL_8250_DW','OF','RISCV_SBI','RISCV_TIMER','VMAP_STACK','PAGE_SIZE_4KB'):
 assert cfg.get('CONFIG_'+key)=='y'
assert cfg['CONFIG_PAGE_SHIFT']=='12' and cfg.get('CONFIG_KUNIT') is None
assert '#define CONFIG_K230_UART_PROGRESS 1' in hpath.read_text().splitlines()
objects={}
for name in ('8250_core.o','timer-riscv.o','k230-uart-progress.o'):
 p=a.objects/name; syms=elf(p); objects[name]={'sha256':sha(p),'symbols':syms,'compiler_comment':run('readelf','-p','.comment',str(p)).strip()}
 report=run('readelf','-hWSs',str(p))
 header,separator,symbols=report.partition('Symbol table')
 assert separator
 excerpt=header+separator+'\n'.join(symbols.splitlines()[:3])+'\n'
 excerpt+='\n'.join(line for line in symbols.splitlines()[3:] if 'k230_uart_progress' in line)+'\n'
 excerpt='\n'.join(line.rstrip() for line in excerpt.splitlines())+'\n'
 (a.output/(name+'.readelf.txt')).write_text(excerpt+'\nSymbol rows above are the K230 progress excerpt; header/section tables are complete.\n')
worker=objects['k230-uart-progress.o']['symbols']
for key in (*RECORDS,'k230_uart_progress_worker','k230_uart_progress_enabled','k230_uart_progress_breadcrumbs_enabled','k230_uart_progress_record'):
 assert key in worker and not worker[key]['section'].startswith('.init')
helpers=[v for k,v in worker.items() if k.startswith('k230_uart_progress_breadcrumb') and not k.endswith(('enabled','setup'))]
assert all(v['section']=='.text' for v in helpers)
assert worker['k230_uart_progress_record']['size']==256 and worker['k230_uart_progress_record']['section_alignment']>=256
for name,sym in (('8250_core.o','k230_uart_progress_snapshot'),('timer-riscv.o','k230_uart_progress_timer_irq')):
 assert objects[name]['symbols'][sym]['section']=='.text'
subprocess.run(['sha256sum','-c','SHA256SUMS'],cwd=a.objects,check=True,stdout=subprocess.DEVNULL)
for name in ('compile.log','SHA256SUMS'): shutil.copyfile(a.objects/name,a.output/('exact-object-'+name))
log=(a.objects/'compile.log').read_text()
assert not any('warning:' in line and 'pahole' not in line for line in log.splitlines())
subprocess.run(['python3','tools/mainline-drm-trial-inspect.py',str(bundle)],stdout=open(a.output/'inspector-output.txt','w'),check=True)
s=(a.output/'inspector-output.txt').read_text(); inspection=json.loads(s[s.index('{'):])
args=inspection['bootargs'].split(); system=Path(inspection['system']); kernel=Path(inspection['kernel'])
kernel_drv=run('nix-store','-q','--deriver',str(kernel)).strip()
assert kernel_drv==run('nix-store','-q','--deriver',str(dev)).strip()
assert kernel_drv=='/nix/store/4hc3qsi5f2rnzav6q02y04ybsyqhcnav-linux-riscv64-unknown-linux-gnu-7.3.0-rc5.drv'
assert run('nix-store','-q','--deriver',str(bundle)).strip()=='/nix/store/c4zr3pa3x7gfhq1g6fyb3ini4nkgbn21-k230-mainline-drm-trial-boot-files.drv'
expected_params=json.loads(Path('docs/evidence/mainline-uart-progress-breadcrumbs/source-host/identities.json').read_text())['params']
assert args==expected_params+[f'init={system}/init']
assert [s for s in args if s.startswith('init=')]==[f'init={system}/init'] and (system/'init').is_file() and os.access(system/'init',os.X_OK)
assert [s for s in args if s.startswith('console=')]==['console=ttyS0,115200n8']
for token in ('k230.boot_trace=1','k230.boot_trace_sbi_only=1'): assert args.count(token)==1
assert not any(s.startswith(('rdinit=','initramfs_async=','k230.uart_progress','earlycon','keep_bootcon')) for s in args)
image=(bundle/'Image-mainline-drm').read_bytes()
for record in RECORDS.values(): assert image.count(record)==1
assert image.count(b'k230.uart_progress_breadcrumbs=\0')==1
assert image.count(b'k230.uart_progress=\0')==1
assert b'\nK230_UP1 n=%u s=%u ' in image and b'k230-uart-progress\0' in image
with tempfile.TemporaryDirectory() as folder:
 decoded=[]
 for i,dt in enumerate((BASE_BUNDLE/'k230-tdisplay-mainline-drm.dtb',bundle/'k230-tdisplay-mainline-drm.dtb')):
  copy=Path(folder)/f'{i}.dtb';shutil.copyfile(dt,copy)
  subprocess.run(['fdtput','-d',str(copy),'/chosen','bootargs'],check=True)
  decoded.append(run('dtc','-I','dtb','-O','dts','-s',str(copy)))
 assert decoded[0]==decoded[1]
 canonical_sha=hashlib.sha256(decoded[0].encode()).hexdigest()
basecfg=config(BASE_DEV/'lib/modules/7.3.0-rc5/build/.config')
diff={k:{'old':basecfg.get(k),'new':cfg.get(k)} for k in sorted(basecfg.keys()|cfg.keys()) if basecfg.get(k)!=cfg.get(k)}
proof={'evidence_class':'host exact configured RISC-V objects and full matching artifacts; no hardware',
 'selected_kernel_and_dev_same_derivation':kernel_drv,'object_revision':OBJECT_REV,'object_output':str(a.objects),'object_dev':str(dev),'source':str(source),'source_worker_sha256':EXPECTED_SOURCE_SHA,'unchanged_cached_getter_dependencies_vs_original_reporter':source_comparison,
 'installed_config_sha256':sha(cpath),'installed_autoconf_sha256':sha(hpath),'config_autoconf_exact_selected_dev':True,'no_forced_CONFIG_overlay':True,
 'actual_effective_config_difference_vs_original_reporter':diff,'objects':objects,'breadcrumb_records_exact_aligned_regular_lifetime':True,
 'full_build':{k:build[k] for k in ('command','revision','started_utc','completed_utc','returncode','output_paths') if k in build},
 'inspection':inspection,'artifact_sha256':{p.name:sha(p) for p in bundle.iterdir() if p.is_file()},
 'hardware_DT_base_bundle':str(BASE_BUNDLE),'hardware_DT_equal_after_only_chosen_bootargs_removed':True,'canonical_DTS_sha256':canonical_sha,
 'Image_exact_unique_breadcrumb_records_and_setup_key':True,'artifact_original_policy_preserved':True,'selected_init_executable':True,'installed_config':{k:cfg.get('CONFIG_'+k) for k in ('K230_UART_PROGRESS','SERIAL_8250','SERIAL_8250_DW','OF','RISCV_SBI','RISCV_TIMER','VMAP_STACK','PAGE_SIZE_4KB','PAGE_SHIFT','KUNIT')}}
(a.output/'proof.json').write_text(json.dumps(proof,indent=2,sort_keys=True)+'\n')
print(json.dumps({k:proof[k] for k in ('object_output','source','installed_config_sha256','actual_effective_config_difference_vs_original_reporter','canonical_DTS_sha256')},indent=2))
