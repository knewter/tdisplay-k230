#!/usr/bin/env python3
"""Reject echoed commands, failed/short loads and malformed trial parameters."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('trial',Path(__file__).resolve().parents[1]/'tools/rvv-board-boot.py')
trial=importlib.util.module_from_spec(spec);spec.loader.exec_module(trial)

class BootProtocol(unittest.TestCase):
    def test_linux_ready_terminal_prefix(self):
        token='a'*32
        line=b'K230_RVV_READY '+token.encode()
        self.assertTrue(trial.has_ready(b'command\r\n\x1b[?2004l\r'+line+b'\r\n',token))
        for raw in (line,b'echo '+line+b'\r\n',line+b'b\r\n',b'other '+line+b'\r\n'):
            self.assertFalse(trial.has_ready(raw,token))

    def test_load_requires_actual_exact_report(self):
        trial.verify_load(b'ext4load mmc 1:2 0x200000 /Image\r\n60427776 bytes read in 8500 ms (6.8 MiB/s)\r\nK230# ',60427776)
        for text in (None,b'60427776 bytes read',b'echo 60427776 bytes read\r\nK230# ',b'0 bytes read in 4 ms\r\n',b'** File not found **\r\nK230# ',b'60427776 bytes read\r\n60427776 bytes read\r\n'):
            # A complete, newline-terminated report is required; stale duplicates fail.
            with self.subTest(text=text):
                with self.assertRaises(RuntimeError):trial.verify_load(text,60427776)

    def test_crc_requires_one_actual_matching_result(self):
        trial.verify_crc(b'crc32 0x200000 0x39a0780\r\nCRC32 for 00200000 ... 03ba077f ==> abcdef12\r\nK230# ','abcdef12')
        for text in (None,b'echo CRC32 for 0..1 ==> abcdef12\r\n',b'CRC32 for 0..1 ==> abcdef13\r\n',b'CRC32 for 0..1 ==> abcdef12\r\nCRC32 for 0..1 ==> abcdef12\r\n'):
            with self.subTest(text=text):
                with self.assertRaises(RuntimeError):trial.verify_crc(text,'abcdef12')

    def test_vendor_lowercase_crc(self):
        trial.verify_crc(b'crc32 for 07000000 ... 070000d2 ==> 8f1867b4\r\nK230# ','8f1867b4')

    def test_manifest_bounds_and_command_injection(self):
        m={'kernel':'/nix/store/'+'a'*32+'-linux-riscv64-6.6.36/Image',
           'system':'/nix/store/'+'b'*32+'-nixos-system-26.11',
           'initrd_payload_matches_system':True,'uimage_crc_valid':True,'bootargs_select_matching_system':True,
           'boot_files':{n:{'bytes':211,'sha256':'1'*64,'crc32':'2'*8} for n in
             ('Image','initrd.uimg','bootargs.txt','k230-tdisplay.dtb','fw_jump_add_uboot_head.bin')}}
        trial.validate_manifest(m)
        for key,value in [('kernel',m['kernel']+'; reset'),('system',m['system']+'\nreset'),('uimage_crc_valid',False)]:
            bad=copy.deepcopy(m);bad[key]=value
            with self.assertRaises(ValueError):trial.validate_manifest(bad)
        for key,value in [('bytes',0),('bytes',64*1024**2),('bytes',True),('crc32','123'),('sha256','x'*64)]:
            bad=copy.deepcopy(m);bad['boot_files']['Image'][key]=value
            with self.assertRaises(ValueError):trial.validate_manifest(bad)

if __name__=='__main__':unittest.main()
