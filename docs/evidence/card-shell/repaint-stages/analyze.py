#!/usr/bin/env python3
"""Correlate repaint stages with actual submitted-frame CPU; no acceptance claim."""
import argparse
import importlib.util
import json
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('frame_profile',HERE.parent/'render-cost/analyze.py')
profile=importlib.util.module_from_spec(spec);spec.loader.exec_module(profile)
STAGES=('prepare','build','commit')
FIELDS={'run','frame_id','render_cpu_ns','prepare_cpu_ns','build_cpu_ns','commit_cpu_ns','attempts','failed_attempts'}


def analyze(raw):
    frame_profile=profile.analyze(raw) # Validates complete frame/input/render coverage.
    events,_=profile.benchmark.parse_rows(raw)
    sessions={int(e['run']):e for e in events if e['event']=='session'}
    inputs={(int(e['run']),e['input_id']):e['kind'] for e in events if e['event']=='input'}
    kinds={}
    for event in events:
        if event['event']=='submit':
            key=(int(event['run']),event['frame_id'])
            kinds.setdefault(key,set()).add(inputs[(int(event['run']),event['input_id'])])
    original={};repaint={}
    for line in raw.decode().splitlines():
        if 'K230_CARD_SHELL frame-cost ' in line:
            row={k:int(v) for k,v in (f.split('=') for f in line.split('K230_CARD_SHELL frame-cost ',1)[1].split())}
            original[(row['run'],row['frame_id'])]=row
        elif 'K230_CARD_SHELL repaint-cost ' in line:
            fields=[f.split('=') for f in line.split('K230_CARD_SHELL repaint-cost ',1)[1].split()]
            if len(fields)!=len(FIELDS) or any(len(f)!=2 or not re.fullmatch('[0-9]+',f[1]) for f in fields) or {f[0] for f in fields}!=FIELDS:
                raise ValueError('malformed repaint fields')
            row={k:int(v) for k,v in fields};key=(row['run'],row['frame_id'])
            if key in repaint:raise ValueError('duplicate repaint frame')
            if row['attempts']!=row['failed_attempts']+1:raise ValueError('inconsistent repaint attempts')
            if sum(row[stage+'_cpu_ns'] for stage in STAGES)!=row['render_cpu_ns']:
                raise ValueError('stage sum differs from render CPU')
            repaint[key]=row
    if not original or repaint.keys()!=original.keys():raise ValueError('incomplete repaint frame coverage')
    for key,row in repaint.items():
        if row['render_cpu_ns']!=original[key]['render_cpu_ns']:raise ValueError('repaint CPU differs from original producer')
    runs=[]
    for run,session in sorted(sessions.items(),key=lambda item:item[1]['cards']):
        rows=[r for key,r in repaint.items() if key[0]==run]
        if not rows:continue
        render=sum(r['render_cpu_ns'] for r in rows)
        if render<=0:raise ValueError('empty render CPU')
        stages={}
        for stage in STAGES:
            samples=[r[stage+'_cpu_ns']/1e6 for r in rows]
            stages[stage]={'mean_ms':sum(samples)/len(samples),'p95_ms':profile.benchmark.percentile(samples,.95),
                           'max_ms':max(samples),'percent_of_render_cpu':100*sum(r[stage+'_cpu_ns'] for r in rows)/render}
        hottest=sorted(rows,key=lambda r:r['render_cpu_ns'],reverse=True)[:5]
        runs.append({'run':run,'cards':session['cards'],'frames':len(rows),'stages':stages,
                     'attempts':sum(r['attempts'] for r in rows),'uncommitted_attempts':sum(r['failed_attempts'] for r in rows),
                     'hottest_frames':[{**r,'input_kinds':sorted(kinds[(run,r['frame_id'])]),
                                        'total_cpu_ns':original[(run,r['frame_id'])]['total_cpu_ns']} for r in hottest]})
    return {'schema':'card-repaint-cpu-stages-v1','frame_profile':frame_profile,'runs':runs,
            'limits':['Diagnostic CPU breakdown; no acceptance decision or optical timing.',
                      'Prepare includes output scene configuration and card preparation.',
                      'Build includes wlroots output-state construction, painting and any tearing test; it is not pure Pixman time.',
                      'Commit measures output commit CPU, not time until light output.',
                      'Uncommitted attempts include no-frame early returns as well as failures.',
                      'Extra clocks/logging have overhead; per-stage p95 values are not additive.']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();args.output.write_text(json.dumps(analyze(args.input.read_bytes()),indent=2)+'\n')


if __name__=='__main__':main()
