#!/usr/bin/env python3
"""Correlate per-input CPU stages with accepted input and frame costs."""
import argparse
import importlib.util
import json
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('repaint_profile',HERE.parent/'repaint-stages/analyze.py')
repaint=importlib.util.module_from_spec(spec);spec.loader.exec_module(repaint)
FIELDS={'run','input_id','cpu_ns','policy_cpu_ns','scene_cpu_ns','chrome_cpu_ns'}
STAGES=('policy','scene','chrome')


def analyze(raw):
    frame_profile=repaint.analyze(raw)
    events,_=repaint.profile.benchmark.parse_rows(raw)
    inputs={(int(e['run']),e['input_id']):e for e in events if e['event']=='input'}
    submitted={}
    for e in events:
        if e['event']=='submit':
            key=(int(e['run']),e['input_id'])
            if key in submitted:raise ValueError('input submitted more than once')
            submitted[key]=e['frame_id']
    costs={};frames={}
    for line in raw.decode().splitlines():
        if 'K230_CARD_SHELL input-cost ' in line:
            fields=[part.split('=') for part in line.split('K230_CARD_SHELL input-cost ',1)[1].split()]
            if len(fields)!=len(FIELDS) or {f[0] for f in fields}!=FIELDS or any(len(f)!=2 or not re.fullmatch(r'[0-9]+',f[1]) for f in fields):
                raise ValueError('malformed input-cost row')
            row={key:int(value) for key,value in fields};key=(row['run'],row['input_id'])
            if key in costs:raise ValueError('duplicate input-cost row')
            if sum(row[stage+'_cpu_ns'] for stage in STAGES)>row['cpu_ns']:
                raise ValueError('input stages exceed input CPU')
            costs[key]=row
        elif 'K230_CARD_SHELL frame-cost ' in line:
            row={k:int(v) for k,v in (part.split('=') for part in line.split('K230_CARD_SHELL frame-cost ',1)[1].split())}
            frames[(row['run'],row['frame_id'])]=row
    if not inputs or costs.keys()!=inputs.keys() or submitted.keys()!=inputs.keys():
        raise ValueError('incomplete input-cost coverage')
    per_frame={}
    for key,row in costs.items():
        frame_key=(key[0],submitted[key])
        per_frame[frame_key]=per_frame.get(frame_key,0)+row['cpu_ns']
    for key,total in per_frame.items():
        if key not in frames or total>frames[key]['input_cpu_ns']:
            raise ValueError('per-input CPU exceeds charged frame input CPU')
    runs=[]
    for run,session in sorted(((int(e['run']),e) for e in events if e['event']=='session'),key=lambda item:item[1]['cards']):
        rows=[row for key,row in costs.items() if key[0]==run]
        if not rows:continue
        stages={}
        for stage in (*STAGES,'cpu'):
            field='cpu_ns' if stage=='cpu' else stage+'_cpu_ns'
            values=[row[field]/1e6 for row in rows]
            stages[stage]={'mean_ms':sum(values)/len(values),'p95_ms':repaint.profile.benchmark.percentile(values,.95),'max_ms':max(values)}
        hottest=sorted(rows,key=lambda row:row['cpu_ns'],reverse=True)[:8]
        runs.append({'run':run,'cards':session['cards'],'inputs':len(rows),'stages':stages,
                     'hottest_inputs':[{**row,'kind':inputs[(run,row['input_id'])]['kind'],
                                        'frame_id':submitted[(run,row['input_id'])]} for row in hottest]})
    return {'schema':'card-input-cpu-stages-v1','frame_profile':frame_profile,'runs':runs,
            'limits':['Diagnostic CPU subdivision only; existing charged frame and input totals remain the acceptance values.',
                      'Stage clocks and other handler work remain inside the charged input interval.',
                      'A submitted frame may include multiple accepted input events and other charged work.',
                      'Host timing cannot establish board CPU cost or physical touch latency.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.write_text(json.dumps(analyze(args.input.read_bytes()),indent=2)+'\n')


if __name__=='__main__':main()
