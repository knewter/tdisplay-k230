from pathlib import Path
import json,re,importlib.util
out=Path(__file__).resolve().parent
repo=out.parents[3]
spec=importlib.util.spec_from_file_location('presentation',repo/'tools/analyze-video-presentation.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
data=json.loads((out/'steady-results.json').read_text());summary=[]
for row in data['trials']:
 mode=row['mode'];a,z=row['samples'][0],row['samples'][-1];lo,hi=a['time-pos'],z['time-pos']
 raw=out/(mode+'-window.log')
 lines=(out/('steady-'+mode+'-presentation.log')).read_text().splitlines();selected=[]
 for line in lines:
  if 'K230_PRESENT_CLOCK' in line:selected.append(line)
  elif match:=re.search(r'\bpts=([-\d.]+)',line):
   if lo<=float(match[1])<=hi:selected.append(line)
 raw.write_text('\n'.join(selected)+'\n')
 result=m.analyze(raw.read_text());assert result['presentation_span_s']>=30 and result['all_hardware_completion']
 (out/(mode+'-window-analysis.json')).write_text(json.dumps(result,indent=2)+'\n')
 wall=z['elapsed']-a['elapsed'];cpu=100*((z['player']['utime']+z['player']['stime'])-(a['player']['utime']+a['player']['stime']))/data['clock_ticks']/wall
 summary.append({'mode':mode,'window_media_start':lo,'window_media_end':hi,'wall_seconds':wall,'player_cpu_percent':cpu,'rss_bytes_first':a['player']['rss_pages']*data['page_size'],'rss_bytes_last':z['player']['rss_pages']*data['page_size'],'decoder_drop_delta':z['decoder-frame-drop-count']-a['decoder-frame-drop-count'],'output_drop_delta':z['frame-drop-count']-a['frame-drop-count'],'min_cache_seconds':min(q['demuxer-cache-duration'] for q in row['samples']),'paused_cache_seen':any(q['paused-for-cache'] for q in row['samples']),'presentation':result})
(out/'summary.json').write_text(json.dumps({'clock_ticks':data['clock_ticks'],'page_size':data['page_size'],'trials':summary},indent=2)+'\n')
for r in summary:print(r['mode'],r['presentation']['presentation_events_per_s'],r['presentation']['interval_ms'])
