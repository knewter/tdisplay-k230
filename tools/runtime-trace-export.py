#!/usr/bin/env python3
"""Merge bounded shell/helper records into a Perfetto timeline and frame report.

Local CLOCK_MONOTONIC recordings only. No timestamp rebasing across machines.
This exports measured spans, NOT a sampled CPU flamegraph.
"""
import argparse
import json
import re
from pathlib import Path

KINDS = frozenset('''trace_start input_down input_motion input_up draw_begin draw_end
commit feedback_unavailable feedback_overflow frame_callback presented discarded
speculative_admission overlay_draw event_loop_work wayland_dispatch wayland_flush
appearance_prepare render_total scene_rebuild canvas_copy thumbnail_poll
thumbnail_hash thumbnail_read_cache thumbnail_resolve thumbnail_decode overlay_prerender
theme_request theme_request_begin theme_request_end theme_helper_rpc helper_request
 theme_activate_invoke theme_activate_checked_copy theme_activate_build_wallpaper_cache
 theme_activate_helper_digest theme_activate_theme_digest theme_activate_prepare
 theme_catalog_prepare_entry theme_catalog_handle theme_transaction_exchange
 theme_transaction_prepare_only theme_transaction_activate_generation'''.split())


def uint(value):
    return type(value) is int and 0 <= value < 2**64


def validate(report):
    if report.get('schema') != 1 or report.get('clock') != 'CLOCK_MONOTONIC':
        raise ValueError('unsupported schema or clock')
    if not re.fullmatch('[0-9a-f]{32}', str(report.get('trace_id', ''))):
        raise ValueError('invalid trace ID')
    for key in ('pid', 'capacity', 'dropped', 'deadline_us', 'finished_us'):
        if not uint(report.get(key)):
            raise ValueError('invalid numeric report field')
    if not report['pid'] or not 1 <= report['capacity'] <= 65536:
        raise ValueError('invalid process or capacity')
    events = report.get('events')
    if not isinstance(events, list) or len(events) > report['capacity']:
        raise ValueError('invalid bounded event buffer')
    seen = set()
    for event in events:
        if event.get('kind') not in KINDS:
            raise ValueError('unrecognized event name; review before export')
        for key in ('span_id', 'parent_span_id', 'start_us', 'end_us', 'cpu_us', 'tid'):
            if not uint(event.get(key)):
                raise ValueError('invalid numeric event field')
        if (event['end_us'] < event['start_us'] or event['end_us'] > report['finished_us']
                or not event['tid']):
            raise ValueError('invalid event time or thread')
        if (not isinstance(event.get('data'), list) or len(event['data']) != 6
                or not all(uint(n) for n in event['data'])):
            raise ValueError('invalid event data')
        if event['span_id']:
            if event['span_id'] in seen:
                raise ValueError('duplicate span ID')
            seen.add(event['span_id'])


def export(reports):
    if not reports:
        raise ValueError('no recordings')
    for report in reports:
        validate(report)
    if len({r['trace_id'] for r in reports}) != 1:
        raise ValueError('trace ID mismatch')
    if len({r['pid'] for r in reports}) != len(reports):
        raise ValueError('duplicate PID recording: merge separate capture windows separately')
    timeline, spans, records, warnings = [], {}, [], []
    for report in reports:
        pid = report['pid']
        if report['dropped']:
            warnings.append(f"pid {pid}: dropped {report['dropped']} events")
        timeline.append(dict(ph='M', name='process_name', pid=pid, tid=0,
                             args={'name': f'runtime pid {pid}'}))
        for event in report['events']:
            entry = dict(event, pid=pid)
            records.append(entry)
            args = dict(cpu_us=event['cpu_us'], data=event['data'],
                        span_id=f"{event['span_id']:016x}",
                        parent_span_id=f"{event['parent_span_id']:016x}")
            if event['span_id']:
                if event['span_id'] in spans:
                    raise ValueError('span ID collision across processes')
                spans[event['span_id']] = entry
                timeline.append(dict(ph='X', cat='runtime', name=event['kind'], pid=pid,
                                     tid=event['tid'], ts=event['start_us'],
                                     dur=event['end_us'] - event['start_us'], args=args))
            else:
                timeline.append(dict(ph='i', s='t', cat='runtime', name=event['kind'],
                                     pid=pid, tid=event['tid'], ts=event['start_us'], args=args))
    missing = 0
    for identity, event in spans.items():
        parent = spans.get(event['parent_span_id'])
        if event['parent_span_id'] and parent is None:
            missing += 1
        if parent and parent['tid'] != event['tid']:
            for phase, source, timestamp in [('s', parent, parent['start_us']), ('f', event, event['start_us'])]:
                timeline.append(dict(ph=phase, cat='rpc', name='parent span', id=f'{identity:016x}',
                                     pid=source['pid'], tid=source['tid'], ts=timestamp))
    if missing:
        warnings.append(f'{missing} spans have missing parents (partial capture or unrecorded component)')
    frames = frame_report(records)
    warnings.extend(frames.pop('warnings'))
    return dict(traceEvents=timeline, displayTimeUnit='ms'), dict(
        schema=1, trace_id=reports[0]['trace_id'], warnings=warnings,
        recording_intact=not warnings, observed_event_kinds=sorted({e['kind'] for e in records}),
        limits=['Spans are wall durations with thread CPU totals, not CPU stack samples.',
                'Overlapping work is correlation, not proof of causation.',
                'Compositor internal stages and kernel scheduling are not captured by these files.'],
        **frames)


def frame_report(records):
    draws, commits, inputs, presented, discarded = {}, {}, {}, [], set()
    unavailable = 0
    gestures = {}
    for e in sorted(records, key=lambda e: e['start_us']):
        key = (e['pid'], e['data'][0])
        if e['kind'] == 'draw_begin':
            draws[key] = e
        elif e['kind'] == 'commit':
            commits[key] = e
        elif e['kind'] in ('input_down', 'input_motion', 'input_up'):
            if e['kind'] == 'input_down':
                gestures[e['pid']] = e['data'][0]
            inputs[key] = dict(e, gesture=gestures.get(e['pid']))
        elif e['kind'] == 'presented':
            presented.append(e)
        elif e['kind'] == 'discarded':
            discarded.add(key)
        elif e['kind'] in ('feedback_unavailable', 'feedback_overflow'):
            unavailable += 1
    frames, warnings = [], []
    for e in presented:
        frame, timestamp_ns, refresh_ns, sequence, flags, clock_id = e['data']
        key = (e['pid'], frame)
        draw, commit = draws.get(key), commits.get(key)
        if clock_id != 1:  # Linux CLOCK_MONOTONIC; never subtract unlike clocks.
            warnings.append(f'frame {frame}: unsupported presentation clock {clock_id}')
            continue
        timestamp = timestamp_ns // 1000
        if draw is None or commit is None:
            warnings.append(f'frame {frame}: missing draw or commit')
            continue
        if not draw['start_us'] <= commit['start_us'] <= timestamp <= e['start_us'] + 1:
            warnings.append(f'frame {frame}: inconsistent presentation timestamp')
            continue
        input_event = inputs.get((e['pid'], draw['data'][1]))
        active = bool(draw['data'][5]) or bool(input_event and input_event['kind'] in ('input_down', 'input_motion'))
        phase = ('contact' if input_event['kind'] in ('input_down', 'input_motion') else 'released') if input_event else 'animation'
        frames.append(dict(pid=e['pid'], frame=frame, presentation_us=timestamp,
                           input_sequence=draw['data'][1], gesture=input_event['gesture'] if input_event else None, phase=phase,
                           active=active, motion_mask=draw['data'][5],
                           draw_to_present_us=timestamp-draw['start_us'],
                           commit_to_present_us=timestamp-commit['start_us'],
                           feedback_delivery_us=e['start_us']-timestamp,
                           refresh_ns=refresh_ns, flags=flags, sequence=sequence,
                           input_to_present_us=(timestamp-input_event['start_us'] if input_event else None)))
    frames.sort(key=lambda f: (f['pid'], f['presentation_us']))
    gaps = []
    for previous, current in zip(frames, frames[1:]):
        same_phase = (previous['pid'] == current['pid'] and previous['gesture'] == current['gesture']
                      and previous['phase'] == current['phase'])
        moving = ((current['input_sequence'] != previous['input_sequence']) if current['phase'] == 'contact'
                  else bool(previous['motion_mask']))
        # Holding a finger still needs no new frames. Never count the pause
        # between the last contact frame and a release/next gesture as jank.
        if same_phase and moving:
            gap = current['presentation_us']-previous['presentation_us']
            current['active_gap_us'] = gap
            gaps.append(gap)
    feedback_keys = {(e['pid'], e['data'][0]) for e in presented} | discarded
    missing = len(set(commits)-feedback_keys)
    if missing:
        warnings.append(f'{missing} commits lack presentation/discard feedback before capture ended')
    if unavailable:
        warnings.append(f'{unavailable} unavailable or overflowed feedback requests')
    if not frames:
        warnings.append('no validated presentation frames')
    ordered = sorted(gaps)
    def percentile(p):
        return ordered[min(len(ordered)-1, max(0, (len(ordered)*p+99)//100-1))] if ordered else None
    return dict(presented_frames=len(frames), discarded_frames=len(discarded),
                active_gap_count=len(gaps), active_gap_us={f'p{p}': percentile(p) for p in (50, 95, 99)},
                worst_frames=sorted(frames, key=lambda f: f.get('active_gap_us', 0), reverse=True)[:20],
                warnings=warnings)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recordings', type=Path, nargs='+')
    parser.add_argument('--timeline', type=Path, required=True)
    parser.add_argument('--summary', type=Path, required=True)
    args = parser.parse_args()
    reports = [json.loads(path.read_text()) for path in args.recordings]
    timeline, summary = export(reports)
    # Never replace a prior run accidentally.
    for path, value in [(args.timeline, timeline), (args.summary, summary)]:
        with path.open('x') as output:
            json.dump(value, output, separators=(',', ':'))
            output.write('\n')


if __name__ == '__main__':
    main()
