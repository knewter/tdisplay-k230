from pathlib import Path
import subprocess,time,json,datetime,hashlib,shlex,select,os
b=Path(__file__).parent;out=b/'splash-dma-final-proof-20261020';out.mkdir(mode=0o700);now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat();ssh=['ssh','-F','/home/jadams/tmp/k230-coordination/ssh_config.private','-o','ConnectTimeout=3','k230'];py='/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3';old=json.loads((b/'splash-dma-trial-postboot-controls.json').read_text());status=out/'manifest.json';v={'started_at':now(),'status':'STARTING_CAMERA','scope':'Trial of one-field stage1 splash DMA request 0x40 to0x4f. Accepted p501 system and landscape retained; final timing/fix proof not assumed.','operator_ready':True,'preboot_id':old['boot_id'],'system':old['systems']['/run/current-system'],'camera_controls':json.loads((b/'splash-dma-final-camera-active-controls.json').read_text()),'board_lease_tool_session':'see current ack.json','kernel_video_alignment_qualified':False,'hardware_task_4_1_complete':False};save=lambda:status.write_text(json.dumps(v,indent=2)+'\n')
camera=None;clock=None;camera_log=(out/'camera.log').open('w')
try:
 deployment=json.loads((b/'splash-dma-board/deployment.json').read_text());assert deployment['status']=='CANDIDATE_WRITTEN_AND_READBACK_VERIFIED';v['deployment']=deployment
 save();camera=subprocess.Popen([str(b/'capture-boot-camera'),'/dev/video0',str(out/'camera'),'300','1024','9600'],stdin=subprocess.DEVNULL,stdout=camera_log,stderr=subprocess.STDOUT);v['camera_pid']=camera.pid;v['camera_pg_id']=os.getpgid(camera.pid);v['camera_started_host_ns']=time.monotonic_ns();save();deadline=time.monotonic()+15
 while time.monotonic()<deadline:
  if camera.poll() is not None:raise RuntimeError('camera exited before readiness')
  metadata=out/'camera/frames.jsonl'
  if metadata.exists() and metadata.read_text().count('"kind":"frame"')>=45:break
  time.sleep(.1)
 else:raise RuntimeError('camera readiness deadline')
 v.update(status='REBOOT_REQUESTED',reboot_requested_at=now(),reboot_host_before_ns=time.monotonic_ns());save();request=subprocess.run(ssh+['systemctl --no-block reboot'],capture_output=True,timeout=10);v.update(reboot_command_exit=request.returncode,reboot_host_after_ns=time.monotonic_ns());(out/'reboot-request.private.stderr').write_bytes(request.stderr);save()
 # An early SSH disconnect is observed, never followed by a duplicate reboot.
 identity_code="from pathlib import Path;import json,os,time,hashlib;print(json.dumps(dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),system=os.path.realpath('/run/current-system'),booted_system=os.path.realpath('/run/booted-system'),persistent_system=os.path.realpath('/nix/var/nix/profiles/system'),kernel_notes_sha256=hashlib.file_digest(Path('/sys/kernel/notes').open('rb'),'sha256').hexdigest(),board_monotonic_ns=time.monotonic_ns())))"
 attempts=[];deadline=time.monotonic()+180
 while time.monotonic()<deadline:
  a={'host_before_ns':time.monotonic_ns(),'utc':now()}
  try:
   p=subprocess.run(ssh+[py+' -c '+shlex.quote(identity_code)],capture_output=True,text=True,timeout=6);a.update(host_after_ns=time.monotonic_ns(),exit_code=p.returncode)
   if p.returncode==0:
    found=json.loads(p.stdout);a['identity']=found
    if found['boot_id']!=old['boot_id']:
     assert all(found[k]==v['system'] for k in ['system','booted_system','persistent_system']) and found['kernel_notes_sha256']==old['kernel_notes_sha256'];v.update(status='NEW_ORDINARY_BOOT_VERIFIED',postboot_identity=found,first_ssh_at=now());attempts.append(a);v['ssh_attempts']=attempts;save();break
  except (subprocess.SubprocessError,OSError,ValueError) as e:a.update(host_after_ns=time.monotonic_ns(),error_class=type(e).__name__)
  attempts.append(a);v['ssh_attempts']=attempts;save();time.sleep(2)
 else:raise RuntimeError('new ordinary boot not verified')
 clock_code="import sys,time,json,pathlib\nboot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip();brightness=pathlib.Path('/sys/class/backlight/canaan-dsi-backlight/brightness');original=brightness.read_text().strip();print(json.dumps(dict(ready=True,boot_id=boot,original_brightness=original)),flush=True)\ntry:\n for line in sys.stdin:\n  value=int(line.split()[1]) if line.startswith('bl ') else -1\n  m=time.monotonic_ns();r=time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW);bt=time.clock_gettime_ns(time.CLOCK_BOOTTIME)\n  if value>=0:brightness.write_text(str(value))\n  r1=time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW);m1=time.monotonic_ns()\n  print(json.dumps(dict(board_monotonic_ns=m,board_raw_ns=r,board_boottime_ns=bt,after_raw_ns=r1,after_monotonic_ns=m1,boot_id=boot,value=value,brightness_readback=brightness.read_text().strip())),flush=True)\nfinally:\n brightness.write_text(original);print(json.dumps(dict(restored_brightness=brightness.read_text().strip())),flush=True)\n"
 clock=subprocess.Popen(ssh+[py+' -u -c '+shlex.quote(clock_code)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=(out/'clock.private.stderr').open('w'),text=True)
 def read_clock():
  if not select.select([clock.stdout],[],[],8)[0]:raise RuntimeError('clock read deadline')
  line=clock.stdout.readline()
  if not line:raise RuntimeError('clock pipe closed')
  return json.loads(line)
 ready=read_clock();assert ready['boot_id']==v['postboot_identity']['boot_id'];v['clock_ready']=ready;v['clock_method']='Persistent SSH brackets include all overhead; affine/exposure/boot extrapolation not yet qualified.';v['clock_samples']=[];save()
 for i in range(120):
  h0=time.monotonic_ns();clock.stdin.write('sample\n');clock.stdin.flush();sample=read_clock();h1=time.monotonic_ns();assert sample['boot_id']==ready['boot_id'];sample.update(host_before_ns=h0,host_after_ns=h1,offset_lower_ns=h0-sample['board_monotonic_ns'],offset_upper_ns=h1-sample['board_monotonic_ns']);v['clock_samples'].append(sample);save();time.sleep(1)
 assert ready['original_brightness']=='255'
 v['optical_calibration_samples']=[];v['optical_calibration_started_camera_elapsed_s']=(time.monotonic_ns()-v['camera_started_host_ns'])/1e9;assert v['optical_calibration_started_camera_elapsed_s']>170
 for value in [32,255,32,255,32,255,32,255]:
  h0=time.monotonic_ns();clock.stdin.write('bl '+str(value)+'\n');clock.stdin.flush();sample=read_clock();h1=time.monotonic_ns();assert sample['value']==value and sample['brightness_readback']==str(value);sample.update(host_before_ns=h0,host_after_ns=h1);v['optical_calibration_samples'].append(sample);save();time.sleep(1)
 clock.stdin.close();v['brightness_restoration']=read_clock();assert v['brightness_restoration']['restored_brightness']=='255';assert clock.wait(timeout=10)==0;clock=None
 for name,command in [('postboot-dmesg.private.log','dmesg --time-format=raw'),('postboot-kernel-journal.private.log','journalctl -b -k -o short-monotonic --no-pager')]:
  p=subprocess.run(ssh+[command],capture_output=True,timeout=30);assert p.returncode==0;(out/name).write_bytes(p.stdout)
 remaining=max(1,320-(time.monotonic_ns()-v['camera_started_host_ns'])/1e9);v['camera_exit']=camera.wait(timeout=remaining);camera=None;camera_log.close();rows=[json.loads(line) for line in (out/'camera/frames.jsonl').read_text().splitlines()];assert rows[-1]['kind']=='summary';v['camera_summary']=rows[-1];v['recording_sha256']={n:hashlib.file_digest((out/'camera'/n).open('rb'),'sha256').hexdigest() for n in ['frames.mjpeg','frames.jsonl']};v.update(status='CANDIDATE_TIMED_CAPTURED',finished_at=now());save();print(json.dumps({'status':v['status'],'boot_id':v['postboot_identity']['boot_id'],'camera_exit':v['camera_exit'],'camera_summary':v['camera_summary'],'clock_samples':len(v['clock_samples']),'kernel_video_alignment_qualified':False,'output':str(out)},indent=2),flush=True)
 if v['camera_exit']!=0 or not v['camera_summary']['capture_complete']:raise SystemExit(2)
except BaseException as e:
 if isinstance(e,SystemExit):raise
 v.update(status='ERROR_PARTIAL_EVIDENCE_RETAINED',error_class=type(e).__name__,error=str(e),finished_at=now());save();raise
finally:
 if clock is not None and clock.poll() is None:clock.terminate();clock.wait(timeout=10)
 if camera is not None and camera.poll() is None:camera.terminate();camera.wait(timeout=10)
 camera_log.close()
