from pathlib import Path
import json,re,gzip,numpy as np
b=Path(__file__).parent;p=b;m=json.loads((p/'capture.json').read_text());samples=m['clock_samples'];marks=json.loads((b/'kernel-clock-check.json').read_text());h0=(samples[0]['host_before_ns']+samples[0]['host_after_ns'])//2;r0=samples[0]['board_raw_ns'];A=[];B=[]
for s in samples:
 lo=(s['host_before_ns']-h0)/1e9;hi=(s['host_after_ns']-h0)/1e9;r=(s['board_raw_ns']-r0)/1e9
 A.extend([[lo,1],[-hi,-1]]);B.extend([r-lo,-r+hi])
A=np.array(A);B=np.array(B);vertices=[]
for i in range(len(A)):
 for j in range(i):
  pair=A[[i,j]];det=np.linalg.det(pair)
  if abs(det)<1e-12:continue
  v=np.linalg.solve(pair,B[[i,j]])
  if v[0]>-1 and np.all(A@v<=B+2e-9):vertices.append(v)
assert vertices,'No affine map satisfies all SSH brackets; do not silently relax evidence.'
vertices=np.array(vertices);intervals=[]
for s,line in zip(marks['samples'],marks['dmesg_markers']):
 k=float(re.match(r'\[\s*([0-9.]+)\]',line)[1]);raw=s['board_raw_ns']/1e9;upper_delta=(s['board_mono_after_ns']-s['python_mono_ns'])/1e9*1.01
 intervals.append([k-raw-upper_delta-1e-6,k-raw+1e-6])
dlo=max(x[0] for x in intervals);dhi=min(x[1] for x in intervals);assert dlo<=dhi
records=[json.loads(s) for s in gzip.decompress((p/'frames.jsonl.gz').read_bytes()).decode().splitlines() if '"kind":"frame"' in s];indices=[510,511,512,516,523,588,1360,1430,1431,1432,1453,1461,1502,1794,1815,1983,3151];results=[]
for i in indices:
 f=records[i];x=(f['camera_timestamp_ns']-h0)/1e9;ts=r0/1e9+x*(1+vertices[:,0])+vertices[:,1];results.append({'frame':i,'camera_elapsed_s':(f['camera_timestamp_ns']-records[0]['camera_timestamp_ns'])/1e9,'conditional_kernel_time_low_s':float(ts.min()+dlo),'conditional_kernel_time_high_s':float(ts.max()+dhi)})
v={'method':'All120 persistent-SSH intervals constrain an affine map from hostCLOCK_MONOTONIC to boardCLOCK_MONOTONIC_RAW; separate bracketed kmsg writes constrain printk-minus-raw offset. No network-symmetry assumption, no outlier removal or relaxed constraints.','source_grounding':'Configured kernel timer-riscv.c reads get_cycles64() for both clocksource and sched_clock, registered with same riscv_timebase. Clocksource active riscv_clocksource. Kernel/syscall/Python monotonic samples agree within sampling intervals. The display enable-phase log does not establish the first visible presentation.','affine_vertices':vertices.tolist(),'reference_host_ns':h0,'reference_board_raw_ns':r0,'slope_ppm_bounds':[float(vertices[:,0].min()*1e6),float(vertices[:,0].max()*1e6)],'printk_minus_raw_s_bounds':[dlo,dhi],'sample_count':len(samples),'sample_span_s':(samples[-1]['host_after_ns']-samples[0]['host_before_ns'])/1e9,'minimum_ssh_roundtrip_ms':min((s['host_after_ns']-s['host_before_ns'])/1e6 for s in samples),'conditional_frame_times':results,'kernel_video_alignment_qualified':False,'limits':['This is a conditional software-clock map, not optical validation of the UVC SOE flag/exposure timing.','Affine extrapolation before firstSSH and early-kernel clock origin have not been physically qualified to±0.1s. Negative times are retained, not clipped or used to assign a bootloader/kernel cause.','Preserving VO to first plane update is an enable-phase message, not first presentation; its timestamp must not anchor film visible takeover.','Current defect reproduced; removal and final filmed default-image proof remain open.']};(p/'conditional-clock-map.replayed.json').write_text(json.dumps(v,indent=2)+'\n');print(json.dumps({'vertices':len(vertices),'slope_ppm_bounds':v['slope_ppm_bounds'],'kernel_offset_ms_bounds':[dlo*1000,dhi*1000],'selected_frame_times':results[:5],'qualified':False},indent=2))
