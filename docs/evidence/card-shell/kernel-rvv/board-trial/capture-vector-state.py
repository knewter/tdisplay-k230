#!/usr/bin/env python3
"""Run on the physical board; publish only public identity and diagnostic data."""
import ctypes
import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

SYSTEM = '/nix/store/fm8136gg0mfqywdz0hqnxlr8kq2wqflr-nixos-system-nixos-26.11.20260919.20b1ddd'
PROBE = '/nix/store/4gn2z5fi5szrnflhzjsr1kq3f1b39wqx-k230-rvv-context-probe-riscv64-unknown-linux-gnu-0.1/bin/k230-rvv-context-probe'
NORMAL = '/nix/store/gnr36q39hmy4pq7ipwac1r1rpfbyqxd4-nixos-system-nixos-26.11.20260919.20b1ddd'
assert len(sys.argv) == 2 and re.fullmatch('[a-f0-9]{32}', sys.argv[1])
assert os.geteuid() == 0
model = Path('/sys/firmware/devicetree/base/model').read_bytes().rstrip(b'\0').decode()
assert model == 'LILYGO T-Display-K230'
current = os.path.realpath('/run/current-system')
assert current == SYSTEM
assert 'init='+SYSTEM+'/init' in Path('/proc/cmdline').read_text().split()
config = gzip.decompress(Path('/proc/config.gz').read_bytes()).decode()
keys = ['CONFIG_TOOLCHAIN_HAS_V', 'CONFIG_RISCV_ISA_V', 'CONFIG_RISCV_ISA_V_DEFAULT_ENABLE', 'CONFIG_DYNAMIC_SIGFRAME', 'CONFIG_ERRATA_THEAD_VECTOR']
settings = {key: next((line.split('=',1)[1] for line in config.splitlines() if line.startswith(key+'=')), None) for key in keys}
assert all(settings[k] == 'y' for k in keys)
class Pair(ctypes.Structure):
    _fields_ = [('key',ctypes.c_int64),('value',ctypes.c_uint64)]
pair = Pair(4,0)
lib = ctypes.CDLL(None,use_errno=True)
lib.syscall.restype = ctypes.c_long
result = lib.syscall(ctypes.c_long(258),ctypes.byref(pair),ctypes.c_size_t(1),ctypes.c_size_t(0),ctypes.c_void_p(),ctypes.c_uint(0))
probe_errno = ctypes.get_errno()
command = ['timeout','--kill-after=3s','15s',PROBE]
# The compiled probe repeats the scalar gate and never forces vector dispatch.
r = subprocess.run(command,capture_output=True,text=True,timeout=22)
try:
    context = json.loads(r.stdout)
except ValueError:
    context = {'status':'INVALID_REPORT','stdout_bytes':len(r.stdout),'stderr_bytes':len(r.stderr)}
def active(unit):
    return subprocess.run(['systemctl','is-active','--quiet',unit]).returncode == 0
wifi = subprocess.run(['wpa_cli','-s','/run/k230-wifi/wpa_supplicant/client','-p','/run/k230-wifi/wpa_supplicant','-i','wlan0','status'],capture_output=True,text=True,timeout=10)
net = subprocess.run(['curl','--interface','wlan0','-fsS','--connect-timeout','10','--max-time','20','-o','/dev/null','-w','%{http_code}','https://example.com/'],capture_output=True,text=True,timeout=25)
report = {
 'token':sys.argv[1], 'evidence_class':'physical-board-vector-context',
 'observed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'model':model, 'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
 'current_system':current, 'kernel_release':os.uname().release,
 'config':settings, 'config_sha256':hashlib.sha256(config.encode()).hexdigest(),
 'persistent_profile_is_normal':os.path.realpath('/nix/var/nix/profiles/system')==NORMAL,
 'persistent_bootargs_select_normal':'init='+NORMAL+'/init' in Path('/boot/bootargs.txt').read_text().split(),
 'hwprobe':{'syscall':258,'result':result,'errno':probe_errno,'key':pair.key,'value':pair.value,'rvv_advertised':result==0 and pair.key==4 and bool(pair.value&4)},
 'context_command':command,'context_exit_code':r.returncode,'context':context,
 'probe_sha256':hashlib.sha256(Path(PROBE).read_bytes()).hexdigest(),
 'shell_active':active('shell'),'seatd_active':active('seatd'),
 'wifi_associated':wifi.returncode==0 and 'wpa_state=COMPLETED' in wifi.stdout.splitlines(),
 'wifi_https_200':net.returncode==0 and net.stdout=='200',
 'limits':['Representative vector state; not exhaustive ISA/register coverage.','No pixel correctness, renderer performance or real-finger acceptance.'],
}
print('K230_RVV_STATE '+json.dumps(report,sort_keys=True),flush=True)
