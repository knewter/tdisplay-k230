from pathlib import Path
import subprocess,shlex,json,hashlib,datetime
b=Path(__file__).parent;ssh=['ssh','-F','/home/jadams/tmp/k230-coordination/ssh_config.private','k230'];py='/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3';blob=(b/'read-riscv-time.so').read_bytes();sha=hashlib.sha256(blob).hexdigest();code='''from pathlib import Path
import sys,ctypes,hashlib,time,os,json,subprocess
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='fbfdd9d3-7f95-4aec-978f-1a19b2a220f9'
root=Path('/var/lib/k230/splash-dma-request-20261020');p=root/'read-riscv-time.so';blob=sys.stdin.buffer.read();assert hashlib.sha256(blob).hexdigest()==EXPECTED_SHA
with p.open('xb') as f:f.write(blob);f.flush();os.fsync(f.fileno())
lib=ctypes.CDLL(str(p));read=lib.k230_read_time;read.restype=ctypes.c_ulonglong;read.argtypes=[];freq=int.from_bytes(Path('/proc/device-tree/cpus/timebase-frequency').read_bytes(),'big');assert freq==27000000;samples=[];fd=os.open('/dev/kmsg',os.O_WRONLY)
try:
 for i in range(32):
  c0=read();r=time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW);c1=read();w0=read();os.write(fd,('<6>K230_FINAL_COUNTER_PANE23 index='+str(i)+'\\n').encode());w1=read();samples.append(dict(index=i,counter_before_raw=c0,board_raw_ns=r,counter_after_raw=c1,counter_before_kmsg=w0,counter_after_kmsg=w1));time.sleep(.1)
finally:os.close(fd)
markers=[x for x in subprocess.check_output(['dmesg','--time-format=raw'],text=True).splitlines() if 'K230_FINAL_COUNTER_PANE23 ' in x];assert len(markers)==32
print(json.dumps(dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),frequency_hz=freq,clocksource=Path('/sys/devices/system/clocksource/clocksource0/current_clocksource').read_text().strip(),samples=samples,dmesg_markers=markers,library_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),mutation='One protected diagnostic library file and32 numeric kmsg records only; no firmware, config, tracing, MMIO or display changes.'),indent=2))
'''.replace('EXPECTED_SHA',repr(sha));p=subprocess.run(ssh+[py+' -c '+shlex.quote(code)],input=blob,capture_output=True,timeout=40);(b/'splash-dma-final-counter.private.stderr').write_bytes(p.stderr);assert p.returncode==0,p.stderr.decode();v=json.loads(p.stdout);v['checked_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();(b/'splash-dma-final-proof-20261020/counter-audit.json').write_text(json.dumps(v,indent=2)+'\n');print('Hardware rdtime/RAW/printk audit captured',len(v['samples']),'samples')
