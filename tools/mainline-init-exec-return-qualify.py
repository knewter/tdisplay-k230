#!/usr/bin/env python3
"""Read-only actual optional-artifact qualification; never builds or opens UART.

Zstandard archive inspection requires host Python 3.14. Protected normal input
is an historical host anchor, not a fresh board preflight or recovery proof.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zlib

BASE_BUNDLE=Path('/nix/store/p2kdar89q7dhwdajjy0mrhmxxzcgsalw-k230-mainline-drm-trial-boot-files')
BASE_DEV=Path('/nix/store/24hbalyljs6gn6fzkkl24znv8a0x6jdl-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-dev')
REPO=Path(__file__).resolve().parents[1]


def sha(body):return hashlib.sha256(body).hexdigest()


def hardware_dt(bundle):
    """Normalize only the system-specific chosen bootargs; no hardware edits."""
    raw=subprocess.check_output(['dtc','-I','dtb','-O','dts',str(bundle/'k230-tdisplay-mainline-drm.dtb')],stderr=subprocess.PIPE,timeout=30)
    lines=raw.decode().splitlines(True)
    matches=[line for line in lines if line.lstrip().startswith('bootargs = ')]
    if len(matches)!=1:raise ValueError('DT must have exactly one bootargs property')
    return ''.join(line for line in lines if line not in matches).encode()


def archived(bundle, archive):
    entries=archive.archive_entries((bundle/'initrd.uimg').read_bytes()[64:])
    return entries


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--dev',type=Path,required=True)
    parser.add_argument('--normal-report',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--build-receipt',type=Path)
    args=parser.parse_args();os.umask(0o077)
    if args.bundle==BASE_BUNDLE:raise ValueError('ordinary p2 is not the new optional variant')
    if not args.normal_report.is_file()or args.normal_report.is_symlink():raise ValueError('protected report must be a real file')
    if args.normal_report.stat().st_uid!=os.getuid()or args.normal_report.stat().st_mode&0o077:raise ValueError('normal report must be private and owned')
    if args.output_dir is None:
        directory=Path(tempfile.mkdtemp(prefix='k230-init-exec-return-qualification-',dir=Path.home()/'tmp'))
    else:
        directory=args.output_dir.expanduser().absolute()
        if directory.exists():raise ValueError('qualification directory must be fresh')
        directory.mkdir(mode=0o700,parents=False)
    started=datetime.now(timezone.utc).isoformat()
    spec=importlib.util.spec_from_file_location('init_exec_trial',REPO/'tools/mainline-drm-system-trial.py')
    trial=importlib.util.module_from_spec(spec);sys.modules[spec.name]=trial;spec.loader.exec_module(trial)
    normal=directory/'normal-report.json';normal.write_bytes(args.normal_report.read_bytes())
    report=json.loads(normal.read_text())
    manifest={'system':str((args.bundle/'system').resolve(strict=True)),'files':{}}
    for name,*_ in trial.rd.LOADS:
        if name=='fw_jump_add_uboot_head.bin':
            manifest['files'][name]={**report['boot_files'][name],'crc32':trial.rd.NORMAL_WRAPPER_CRC32}
        else:
            body=(args.bundle/name).read_bytes()
            manifest['files'][name]={'bytes':len(body),'sha256':sha(body),'crc32':f'{zlib.crc32(body):08x}'}
    manifest_path=directory/'candidate-manifest.json';manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    prepared=trial.prepare(args.bundle,manifest_path,normal,wait_initramfs_in_initcall=True,without_boot_markers=True,init_exec_return=True)
    proof=prepared['init_exec_return_proof']
    if Path(proof['config'])!=args.dev/'lib/modules/7.3.0-rc5/build/.config':raise ValueError('dev is not the selected same-derivation config')
    if (args.dev/'lib/modules/7.3.0-rc5/build/.config').read_bytes()!=(BASE_DEV/'lib/modules/7.3.0-rc5/build/.config').read_bytes():raise ValueError('config differs from p2')
    if (Path(prepared['system'])/'init').read_bytes()!=(Path((BASE_BUNDLE/'system').resolve())/'init').read_bytes():raise ValueError('selected system/init bytes changed')
    if hardware_dt(args.bundle)!=hardware_dt(BASE_BUNDLE):raise ValueError('DT hardware differs')
    subprocess.run(['sha256sum','--check','SHA256SUMS'],cwd=args.bundle,check=True,capture_output=True,timeout=30)
    dtargs=subprocess.check_output(['fdtget','-t','s',str(args.bundle/'k230-tdisplay-mainline-drm.dtb'),'/chosen','bootargs'],text=True,timeout=20).strip()
    original=(args.bundle/'bootargs.txt').read_text()
    if dtargs!=original.strip().removeprefix('bootargs='):raise ValueError('DT and bundle argument identities differ')
    base_args=trial.ordinary_bootargs(original,prepared['system'],wait_initramfs_in_initcall=True,without_boot_markers=True)
    if prepared['bootargs']!=base_args+' '+trial.INIT_EXEC_RETURN_FLAG:raise ValueError('not a sole added gate')
    archive_spec=importlib.util.spec_from_file_location('init_exec_archive',REPO/'tools/mainline-drm-uart-observer-trial.py')
    archive=importlib.util.module_from_spec(archive_spec);archive_spec.loader.exec_module(archive)
    old,new=archived(BASE_BUNDLE,archive),archived(args.bundle,archive)
    removed=sorted(old.keys()-new.keys());added=sorted(new.keys()-old.keys())
    changed=sorted(name for name in old.keys()&new.keys()if old[name]!=new[name])
    # Unit/script and dependencies must stay byte-identical, except kernel-specific
    # release information and module tree/store symlinks. No silent userspace delta.
    for name in changed:
        if name!='etc/os-release'and not name.startswith(('lib/modules/','usr/lib/modules/')):
            raise ValueError('unexpected changed archived userspace entry: '+name)
    for name in removed+added:
        if 'linux-riscv64-unknown-linux-gnu-7.3.0-rc5'not in name and not name.startswith(('lib/modules/','usr/lib/modules/')):
            raise ValueError('unexpected added/removed archive dependency: '+name)
    build=None
    if args.build_receipt:
        build=json.loads(args.build_receipt.read_text())
        if build['returncode']!=0 or str(args.bundle)not in build['output_paths']or str(args.dev)not in build['output_paths']:
            raise ValueError('matching successful full build receipt absent')
    (directory/'prepared.private.json').write_text(json.dumps(prepared,indent=2,default=str)+'\n')
    transport=trial.volatile_bootargs_command(prepared)
    (directory/'transport.private.txt').write_text(transport+'\n')
    safe={'schema':'k230-init-exec-return-positive-host-v1','evidence_class':'actual-new-artifact-host-preparation-only',
          'started_utc':started,'completed_utc':datetime.now(timezone.utc).isoformat(),
          'controller_source_sha256':sha((REPO/'tools/mainline-drm-system-trial.py').read_bytes()),
          'qualifier_sha256':sha(Path(__file__).read_bytes()),'bundle':str(args.bundle),'system':prepared['system'],
          'dev':str(args.dev),'kernel_proof':proof,'archive_proof':prepared['init_exec_return_archive'],
          'files':{k:v for k,v in manifest['files'].items()if k!='fw_jump_add_uboot_head.bin'},
          'manifest_sha256':sha(manifest_path.read_bytes()),'base_bundle':str(BASE_BUNDLE),
          'archive_delta':{'old_entries':len(old),'new_entries':len(new),'added':added,'removed':removed,'changed':changed},
          'same_kernel_config':True,'same_DT_hardware':True,'same_original_system_init_bytes':True,
          'SHA256SUMS_and_DTB_bootargs_passed':True,'sole_added_argument':trial.INIT_EXEC_RETURN_FLAG,
          'base_argument_bytes':len(base_args.removeprefix('bootargs=').encode()),'argument_bytes':len(prepared['bootargs'].removeprefix('bootargs=').encode()),
          'literal_command_bytes':len(transport.encode()),'five_load_files_and_CRC_host_qualified':True,
          'build_receipt_sha256':sha(args.build_receipt.read_bytes())if build else None,
          'build_revision':build.get('revision')if build else None,
          'normal_report_class':'protected historical host anchor; no fresh preflight or recovery',
          'UART_opened':False,'implicit_build':False,'physical_result':'UNVERIFIED'}
    (directory/'result.json').write_text(json.dumps(safe,indent=2)+'\n')
    print('Actual optional init exec-return host qualification PASS; private directory: '+str(directory))
    return 0


if __name__=='__main__':raise SystemExit(main())
