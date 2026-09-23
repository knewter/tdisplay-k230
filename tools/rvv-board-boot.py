#!/usr/bin/env python3
"""Load a staged RVV kernel from root without changing the persistent boot path.

Default: validate all load sizes/CRCs, then reset into the normal system.
--boot: boot the verified in-memory trial once. A successful serial login is
only a boot observation, never vector/context or shell acceptance.
"""
import argparse
import hashlib
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time
import uuid

PROMPT = b'K230# '
NORMAL = '/nix/store/gnr36q39hmy4pq7ipwac1r1rpfbyqxd4-nixos-system-nixos-26.11.20260919.20b1ddd'
TRIAL_DIR = '/var/lib/k230/rvv-trial'
PYTHON = '/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3'


def validate_manifest(m):
    if not re.fullmatch(r'/nix/store/[a-z0-9]{32}-linux-[A-Za-z0-9._+-]+/Image', m['kernel']):
        raise ValueError('invalid immutable trial kernel path')
    if not re.fullmatch(r'/nix/store/[a-z0-9]{32}-nixos-system-[A-Za-z0-9._+-]+', m['system']):
        raise ValueError('invalid system path')
    files = m['boot_files']
    limits = {'Image':64*1024**2, 'initrd.uimg':64*1024**2,
              'bootargs.txt':4096, 'k230-tdisplay.dtb':1024**2,
              'fw_jump_add_uboot_head.bin':4*1024**2}
    for name, limit in limits.items():
        item = files[name]
        if type(item['bytes']) is not int or not 0 < item['bytes'] < limit:
            raise ValueError('invalid size for '+name)
        if not re.fullmatch('[a-f0-9]{8}', item['crc32']):
            raise ValueError('invalid CRC for '+name)
        if not re.fullmatch('[a-f0-9]{64}', item['sha256']):
            raise ValueError('invalid SHA256 for '+name)
    if not all(m.get(k) is True for k in ('initrd_payload_matches_system',
                                         'uimage_crc_valid', 'bootargs_select_matching_system')):
        raise ValueError('unverified image manifest')


def uart_text(output):
    # Linux's interactive shell attaches its bracketed-paste reset to the
    # first output line. Strip only that known leading terminal artifact.
    return re.sub(rb'(?m)^(?:\r|\x1b\[\?2004[lh])*', b'', output).replace(b'\r', b'')


def has_ready(output, token):
    return re.search(rb'^K230_RVV_READY '+token.encode()+rb'\n', uart_text(output), re.M) is not None


def verify_load(output, size):
    if output is None:
        raise RuntimeError('load did not return to the U-Boot prompt')
    counts = re.findall(rb'^([0-9]+) bytes read(?: in [^\r\n]*)?\r?\n', uart_text(output), re.M)
    if counts != [str(size).encode()]:
        raise RuntimeError('load did not report the exact expected byte count')


def verify_crc(output, expected):
    if output is None:
        raise RuntimeError('CRC did not return to the U-Boot prompt')
    values = re.findall(rb'^[Cc][Rr][Cc]32 for [^\r\n]+ ==> ([0-9a-fA-F]{8})\r?\n', uart_text(output), re.M)
    if [v.decode().lower() for v in values] != [expected]:
        raise RuntimeError('loaded memory CRC mismatch or missing report')


def wait_linux(session, timeout=180):
    return session.wait_for(b'nixos login:', timeout)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--private-log', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--boot', action='store_true')
    args = p.parse_args()
    m = json.loads(args.manifest.read_text()); validate_manifest(m)
    if args.output.exists() or args.private_log.exists():
        p.error('preserve prior trial logs; use new output paths')
    os.umask(0o077)
    spec = importlib.util.spec_from_file_location('ums', Path(__file__).with_name('ums-session.py'))
    ums = importlib.util.module_from_spec(spec);spec.loader.exec_module(ums)
    report = {'status':'FAIL', 'mode':'one-time-boot' if args.boot else 'load-and-return',
              'trial_system':m['system'], 'normal_system':NORMAL, 'loads':[],
              'persistent_boot_selection_changed':False, 'vector_execution_verified':False,
              'controller_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    in_uboot = False
    with open('/tmp/k230-board.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        class TrialSession(ums.Session):
            def send_line(self, text, kill=True):
                if kill:
                    self.port.write(ums.KILL_LINE);self.port.flush();time.sleep(.05)
                self.note('sending: '+text)
                self.buf=b''
                # U-Boot treats LF after CR as a second empty command and
                # repeats the previous command. Send exactly one terminator.
                self.port.write(text.encode()+b'\r');self.port.flush()
        session = TrialSession('/dev/ttyACM0',115200,str(args.private_log))
        try:
            # The staged preflight checks current system, full staged-file SHA256,
            # protected normal boot hashes, selected profile and physical layout.
            token = uuid.uuid4().hex
            session.port.write(b'\r');session.port.flush();time.sleep(.4);session.pump()
            session.send_line(PYTHON+' -I '+TRIAL_DIR+'/preflight.py '+token)
            end=time.monotonic()+30
            while time.monotonic()<end:
                session.pump()
                if has_ready(session.buf,token):break
            else:raise RuntimeError('staged trial preflight did not pass')
            session.send_line('reboot')
            end=time.monotonic()+25
            while time.monotonic()<end:
                session.port.write(b' \x08');session.port.flush();session.pump();time.sleep(.1)
            session.buf=b'';session.port.write(b'\r');session.port.flush()
            if not session.wait_for(PROMPT,30):
                raise RuntimeError('could not catch U-Boot; no trial load attempted')
            in_uboot=True
            plan = [
                ('bootargs.txt','1:2','0x7000000',TRIAL_DIR+'/bootargs.txt'),
                ('fw_jump_add_uboot_head.bin','1:1','0x8000000','/fw_jump_add_uboot_head.bin'),
                ('Image','1:2','0x200000',m['kernel']),
                ('k230-tdisplay.dtb','1:2','0x8400000',TRIAL_DIR+'/k230-tdisplay.dtb'),
                ('initrd.uimg','1:2','0x9000000',TRIAL_DIR+'/initrd.uimg'),
            ]
            for name,partition,address,path in plan:
                info=m['boot_files'][name]
                verify_load(session.cmd_output('ext4load mmc '+partition+' '+address+' '+path,90),info['bytes'])
                verify_crc(session.cmd_output('crc32 '+address+' '+hex(info['bytes']),30),info['crc32'])
                report['loads'].append({'file':name,'partition':partition,'bytes':info['bytes'],'crc32':info['crc32']})
            if args.boot:
                # The count is from the verified bootargs artifact, not whatever
                # the last ext4load happened to leave in ${filesize}.
                reply=session.cmd_output('env import -t 0x7000000 '+hex(m['boot_files']['bootargs.txt']['bytes'])+' && echo K230_RVV_ARGS_IMPORTED')
                if reply is None or not re.search(rb'^K230_RVV_ARGS_IMPORTED\r?$',reply,re.M):
                    raise RuntimeError('volatile trial arguments were not imported')
                session.send_line('bootm 0x8000000 0x9000000 0x8400000')
                in_uboot=False
            else:
                session.send_line('reset');in_uboot=False
            if not wait_linux(session):
                raise RuntimeError('Linux login deadline exceeded; physical recovery may be required')
            report.update(status='PASS',linux_login_observed=True)
        except Exception as error:
            report['error']=str(error)
            if in_uboot or PROMPT in session.buf[-1024:]:
                session.send_line('reset');in_uboot=False
                report['normal_recovery_login_observed']=wait_linux(session)
            raise
        finally:
            session.port.close();session.log.close()
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    main()
