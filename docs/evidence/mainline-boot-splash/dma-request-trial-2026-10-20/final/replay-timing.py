from pathlib import Path
import json,numpy as np,re,bisect,hashlib,gzip
b=Path(__file__).parent;p=b;m=json.loads((p/'capture.json').read_text());host=[json.loads(l) for l in gzip.decompress((p/'host-clock.jsonl.gz').read_bytes()).decode().splitlines()];hs=[s for s in host if s['kind']=='sample'];assert host[-1]['driver_exit']==0 and len(hs)>5000
hmid=np.array([(s['before_monotonic_ns']+s['after_monotonic_ns'])/2 for s in hs]);offlo=np.array([s['raw_ns']-s['after_monotonic_ns'] for s in hs]);offhi=np.array([s['raw_ns']-s['before_monotonic_ns'] for s in hs]);slew=0.002
assert np.all(np.diff(hmid)>0)
for i in range(1,len(hs)):
 dt=hmid[i]-hmid[i-1];assert offlo[i]<=offhi[i-1]+slew*dt and offlo[i-1]<=offhi[i]+slew*dt,'Host clock offsets violate conversion envelope'
def to_raw(t):
 i=bisect.bisect_left(hmid,t);i=min(max(i,1),len(hs)-1);candidates=[i-1,i];lo=[];hi=[]
 for j in candidates:
  radius=abs(t-hmid[j])*slew;lo.append(t+offlo[j]-radius);hi.append(t+offhi[j]+radius)
 low=max(lo);high=min(hi);assert low<=high;return low,high
samples=m['clock_samples'];href=sum(to_raw((samples[0]['host_before_ns']+samples[0]['host_after_ns'])/2))/2;rref=samples[0]['board_raw_ns'];A=[];B=[]
for s in samples:
 lo=(to_raw(s['host_before_ns'])[0]-href)/1e9;hi=(to_raw(s['host_after_ns'])[1]-href)/1e9;r=(s['board_raw_ns']-rref)/1e9;A.extend([[lo,1],[-hi,-1]]);B.extend([r-lo,-r+hi])
A=np.array(A);B=np.array(B);vertices=[]
for i in range(len(A)):
 for j in range(i):
  pair=A[[i,j]]
  if abs(np.linalg.det(pair))<1e-12:continue
  v=np.linalg.solve(pair,B[[i,j]])
  if v[0]>-1 and np.all(A@v<=B+2e-9):vertices.append(v)
assert vertices,'No affine raw-clock map satisfies every SSH bracket; no relaxation or sample removal allowed'
vtx=np.array(vertices)
def raw_board(t):
 lo,hi=to_raw(t);low=rref/1e9+(lo-href)/1e9*(1+vtx[:,0])+vtx[:,1];high=rref/1e9+(hi-href)/1e9*(1+vtx[:,0])+vtx[:,1];return float(low.min()),float(high.max())
marks=json.loads((p/'kernel-clock-check.json').read_text());assert marks['boot_id']==m['postboot_identity']['boot_id'];intervals=[]
for s,line in zip(marks['samples'],marks['dmesg_markers']):
 k=float(re.match(r'\[\s*([0-9.]+)\]',line)[1]);r=s['board_raw_ns']/1e9;span=(s['board_mono_after_ns']-s['python_mono_ns'])/1e9*1.01;intervals.append([k-r-span-1e-6,k-r+1e-6])
counter=json.loads((p/'counter-analysis.json').read_text());dlo=max(max(x[0] for x in intervals),counter['printk_minus_raw_seconds'][0]);dhi=min(min(x[1] for x in intervals),counter['printk_minus_raw_seconds'][1]);assert dlo<=dhi
rows=[json.loads(l) for l in gzip.decompress((p/'frames.jsonl.gz').read_bytes()).decode().splitlines()];frames=[f for f in rows if f['kind']=='frame'];assert rows[-1]['capture_complete'] and len(frames)==8993
assert not any(f[k] for f in frames for k in ['sequence_gap','timestamp_regression','clock_flags_changed','timestamp_invalid','buffer_error'])
assert all(f['camera_clock']=='monotonic' and f['timestamp_source']=='start_of_exposure' for f in frames)
t=np.array([f['camera_timestamp_ns']/1e9 for f in frames]);samples_opt=m['optical_calibration_samples'];assert len(samples_opt)==8 and m['optical_calibration_started_camera_elapsed_s']>170
y=np.full(len(frames),np.nan);mask=(t>samples_opt[0]['host_before_ns']/1e9-.6)&(t<samples_opt[-1]['host_after_ns']/1e9+.7)
roi=json.loads((p/'calibration-roi-luma.json').read_text());assert roi['source_raw_sha256']==m['recording_sha256']['frames.mjpeg']
for value in roi['measurements']:y[value['frame']]=value['mean_luma']

events=[]
for s in samples_opt:
 lo=s['host_before_ns']/1e9;hi=s['host_after_ns']/1e9;pre=float(np.median(y[(t>lo-.4)&(t<lo-.12)]));post=float(np.median(y[(t>hi+.2)&(t<hi+.5)]));assert abs(post-pre)>5
 threshold=(pre+post)/2;indices=np.where((t>lo-.15)&(t<hi+.3))[0];cross=[int(i) for i in indices if (y[i]>=threshold)==(post>pre)];assert cross;i=cross[0];camera_range=raw_board(frames[i]['camera_timestamp_ns']);upper=camera_range[1]-s['board_raw_ns']/1e9;events.append(dict(value=s['value'],frame=i,pre_luma=pre,post_luma=post,command_board_before_raw_ns=s['board_raw_ns'],command_board_after_raw_ns=s['after_raw_ns'],camera_board_raw_interval_s=list(camera_range),timestamp_minus_changed_photon_upper_s=upper,host_ssh_roundtrip_ms=(s['host_after_ns']-s['host_before_ns'])/1e6))
assert all(e['timestamp_minus_changed_photon_upper_s']>0 for e in events)
optical_upper=max(e['timestamp_minus_changed_photon_upper_s'] for e in events)
controls=m['camera_controls']['mode_and_controls'];exposure_units=int(re.search(r'exposure_time_absolute[^\n]*value=(\d+)',controls)[1]);exposure_s=exposure_units*.0001;period=float(np.max(np.diff(t)));sensor_allowance=period+exposure_s
results=[]
for f in frames[:3600]:
 tslo,tshi=raw_board(f['camera_timestamp_ns']);dqlo,dqhi=raw_board(f['host_dq_after_ns']);lower=tslo-optical_upper-sensor_allowance+dlo;upper=dqhi+dhi;assert lower<=upper;results.append(dict(frame=f['frame'],camera_elapsed_s=(f['camera_timestamp_ns']-frames[0]['camera_timestamp_ns'])/1e9,kernel_time_lower_s=lower,kernel_time_upper_s=upper,kernel_time_mid_s=(lower+upper)/2,uncertainty_half_width_s=(upper-lower)/2))
maxerr=max(x['uncertainty_half_width_s'] for x in results);board_source=json.loads((p/'board-clock-source.json').read_text());assert board_source['timebase_frequency']==27000000 and board_source['clocksource']=='riscv_clocksource'
output=dict(method='Same-stream posthandoff optical calibration and causal dequeue bounds; contemporaneous host mono/raw brackets; all120 SSH intervals constrain an affine host-RAW to board-RAW map; separately bracketed printk/raw offset. No network-symmetry assumption, sample removal or relaxed feasibility constraints.',boot_id=m['postboot_identity']['boot_id'],host_clocksource=host[0],host_clock_samples=len(hs),host_pair_max_width_ns=max(s['after_monotonic_ns']-s['before_monotonic_ns'] for s in hs),host_monotonic_raw_conversion_slew_envelope_ppm=slew*1e6,host_observed_offset_span_ms=float((offhi.max()-offlo.min())/1e6),affine_vertices=vtx.tolist(),reference_host_raw_ns=href,reference_board_raw_ns=rref,raw_clock_slope_ppm_bounds=[float(vtx[:,0].min()*1e6),float(vtx[:,0].max()*1e6)],all_ssh_samples_used=len(samples),minimum_ssh_roundtrip_ms=min((s['host_after_ns']-s['host_before_ns'])/1e6 for s in samples),printk_minus_raw_bounds_s=[dlo,dhi],direct_hardware_counter_origin=counter,optical_events=events,maximum_observed_timestamp_minus_changed_photon_upper_s=optical_upper,maximum_camera_period_s=period,exposure_units_100us=exposure_units,rolling_sensor_plus_exposure_allowance_s=sensor_allowance,frame_time_records=results,maximum_uncertainty_half_width_s=maxerr,numeric_100ms_bound_passed=maxerr<=.1,kernel_video_alignment_qualified=False,conditions=['The empirical same-stream upper latency envelope measured from eight posthandoff transitions applies to the preceding normal-boot frames; mode/controls/clock-source flags remain fixed, no gaps/errors/resets occurred. This is an empirical qualification, not a universal worst-case promise for unobserved camera behavior.','Host invariant TSC and board fixed27MHz riscv_clocksource are treated as affine over this single warmboot; source audit plus complete clock logs and all120 feasible SSH brackets ground the clock choice. A changed oscillator frequency outside the observed fit would invalidate extrapolation.','Whole-image rolling acquisition allowance uses the largest recorded frame interval plus exposure; per-frame dequeue causality supplies the opposite bound. This is conservative for the observed operating mode, not a sensor datasheet guarantee.','Negative new-kernel-relative times are retained for pre-kernel film frames. Source continuity/epoch audit must be reviewed before declaring the early-boot origin qualified.'],conclusion='Numeric timing interval computed; final qualification requires explicit review of the source epoch/continuity grounding and empirical camera conditions. Recorder flags alone do not prove it.')
(p/'timing-analysis.replayed.json').write_text(json.dumps(output,indent=2)+'\n');print(json.dumps({k:output[k] for k in ['host_clock_samples','host_pair_max_width_ns','host_observed_offset_span_ms','raw_clock_slope_ppm_bounds','printk_minus_raw_bounds_s','maximum_observed_timestamp_minus_changed_photon_upper_s','maximum_camera_period_s','rolling_sensor_plus_exposure_allowance_s','maximum_uncertainty_half_width_s','numeric_100ms_bound_passed','kernel_video_alignment_qualified']},indent=2))
