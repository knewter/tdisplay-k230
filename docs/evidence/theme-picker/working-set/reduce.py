#!/usr/bin/env python3
"""Reduce private picker capture to allowlisted numeric evidence; no board I/O."""
import argparse, collections, hashlib, json, re, statistics
from pathlib import Path

UNITS=('shell-ui.service','shell.service','theme-helper.service')
def digest(value):return hashlib.sha256(value.encode()).hexdigest()
def store(value):
    if not isinstance(value,str) or not re.fullmatch(r'/nix/store/[a-z0-9]{32}-[A-Za-z0-9+._?=-]+(?:/[A-Za-z0-9+._?=/~-]+)?',value):
        raise ValueError('unexpected store identity')
    return value

def reduce(r, theme_count):
    parsed=[];commands=[];pre=[];held=False;held_pre=0
    for e in r.get('events',[]):
        m=re.fullmatch(r'rust-shell (\d+)ms (.*)',e['message'])
        if not m:continue
        t=int(m[1]);text=m[2];kind=None
        if text in ('commit','frame-done','wallpaper-commit'):kind=text
        elif re.fullmatch(r'touch-(down|move) -?\d+ -?\d+(?:\.\d+)? -?\d+(?:\.\d+)?',text):kind=text.split()[0]
        elif re.fullmatch(r'touch-up -?\d+',text):kind='touch-up'
        elif re.fullmatch(r'optimistic-apply prerendered generation=[a-f0-9]+',text):kind='prerender-completed'
        cmd=re.fullmatch(r'theme-command (list|preview|activate) (?:[a-f0-9]+|-) path=(socket|fallback) ms=(\d+)',text)
        if cmd:commands.append({'action':cmd[1],'transport':cmd[2],'duration_ms':int(cmd[3])})
        if kind and e.get('monotonic_us'):
            parsed.append({'rust_ms':t,'monotonic_s':int(e['monotonic_us'])/1e6,'kind':kind})
    for e in sorted(parsed,key=lambda e:e['rust_ms']):
        if e['kind']=='touch-down':held=True
        elif e['kind']=='touch-up':held=False
        elif e['kind']=='prerender-completed':pre.append(e);held_pre+=held
    phases=[]
    for p in r['phases']:
        name=p['name']
        if not re.fullmatch(r'(settings-baseline|first-open|warm-open|back|idle-first|idle-warm|(?:warm-)?theme-swipe-\d+|background-swipe-\d+)',name):
            raise ValueError('unexpected phase')
        if 'end_monotonic_s' not in p:continue
        a,b=p['start_monotonic_s'],p['end_monotonic_s']
        rows=[s for s in r['samples'] if a<=s['monotonic_s']<=b]
        out={'name':'first-observed-open' if name=='first-open' else name,'duration_s':round(b-a,4),
             'sample_count':len(rows)}
        if 'injection_end_monotonic_s' in p:
            out['injection_duration_ms']=round(1000*(p['injection_end_monotonic_s']-a),3)
        if len(rows)>1:
            first,last=rows[0],rows[-1];dt=last['monotonic_s']-first['monotonic_s']
            out['sampled_s']=round(dt,4);out['units']={}
            for unit in UNITS:
                x,y=first['units'][unit],last['units'][unit]
                out['units'][unit]={'process_cpu_percent':round(100*(y['ticks']-x['ticks'])/r['clock_ticks_per_second']/dt,3),
                    'cgroup_cpu_percent':round(100*(y['cgroup_cpu']['usage_usec']-x['cgroup_cpu']['usage_usec'])/1e6/dt,3),
                    'rss_first_bytes':x['rss_bytes'],'rss_last_bytes':y['rss_bytes'],
                    'rss_peak_bytes':max(s['units'][unit]['rss_bytes'] for s in rows)}
        events=[e for e in parsed if a<=e['monotonic_s']<=b]
        out['events']=dict(collections.Counter(e['kind'] for e in events))
        commits=sorted(e['rust_ms'] for e in events if e['kind']=='commit')
        if 'swipe' in name:
            gaps=[y-x for x,y in zip(commits,commits[1:])]
            out['commit_intervals_ms']=gaps
            out['commit_gap_median_ms']=statistics.median(gaps) if gaps else None
            out['commit_gap_max_ms']=max(gaps) if gaps else None
        phases.append(out)
    before=r['generation_before'];after=r['generation_after']
    return {'schema':'k230-picker-browsing-observation-v1','label':r['label'] if r['label'] in ('old','new') else 'trial',
        'capture_completed':r['status']=='CAPTURED_REQUIRES_REVIEW','capture_error_count':len(r.get('errors',[])),
        'provenance':'injected verified virtual touchscreen; no physical-finger or presentation-FPS claim',
        'opening_condition':'first observed opening in this capture; not proven process-cold or disk-cold',
        'theme_count_operator_observed':theme_count,'active_background_count':r['active_background_count'],
        'duration_s':round(r['end_monotonic_s']-r['start_monotonic_s'],4),
        'kernel_release':r['kernel_release'],
        'booted_system':store(r['booted_system']),'current_system':store(r['current_system']),
        'runtime':{unit:{'pid':int(r['identities'][unit]['pid']),'exe':store(r['identities'][unit]['exe']),
                  'start_ticks':int(r['identities'][unit]['start_ticks'])} for unit in UNITS},
        'generation_before_sha256':digest(before),'generation_after_sha256':digest(after),
        'generation_unchanged':r['generation_unchanged'],
        'generation_samples':len(r['samples']),
        'generation_change_samples':sum(s['generation']!=before for s in r['samples']),
        'event_counts':dict(collections.Counter(e['kind'] for e in parsed)),
        'speculative_prerender_completions':len(pre),'speculative_completions_while_touch_held':held_pre,
        'theme_commands':commands,'phases':phases,
        'limits':['Single sequential old/new run; prior process/cache histories are not matched.',
                  'Swipe windows include 1.2 seconds of settling after injection.',
                  'Commit gaps use Rust elapsed timestamps; phase assignment uses journal monotonic time.',
                  'CPU samples are roughly 0.5 seconds apart; short phases have partial sample coverage.',
                  'No thumbnail request/cache-hit counters are emitted by the installed program.',
                  'No native media was recorded during this CPU/timing pass.']}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--theme-count',type=int,required=True);a=p.parse_args()
    result=reduce(json.loads(a.input.read_text()),a.theme_count)
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print('Wrote allowlisted evidence:',a.output)
