#!/usr/bin/env python3
"""Exercise the actual producer's entry ordering with small backend stubs."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class EntryTiming(unittest.TestCase):
    def test_native_ipc_and_stale_input_entry_parse_with_valid_baseline(self):
        with tempfile.TemporaryDirectory(prefix='card-telemetry-') as directory:
            root=Path(directory)
            def put(name,text):
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
            shutil.copyfile(ROOT/'nix/card-shell/telemetry.h',root/'telemetry.h')
            put('sway/card_shell_telemetry.h','#include "telemetry.h"\n')
            put('log.h','''#include <stdio.h>
#define SWAY_INFO 0
#define SWAY_ERROR 1
#define sway_log(level,...) do { printf(__VA_ARGS__); putchar('\\n'); } while (0)
''')
            put('drm_fourcc.h','#define DRM_FORMAT_RGB565 1\n#define DRM_FORMAT_XRGB8888 2\n')
            put('sway/output.h','''#include <stdbool.h>
#include <stdint.h>
#include <time.h>
struct wlr_output { void *backend; uint32_t render_format,commit_seq; };
struct sway_output { struct wlr_output *wlr_output; struct wlr_scene_output *scene_output; int width,height; };
struct wlr_output_event_present { struct timespec when; unsigned commit_seq; bool presented; };
''')
            put('wlr/backend/drm.h','static inline int wlr_backend_is_drm(void *p) { return p != 0; }\n')
            put('wlr/backend/headless.h','static inline int wlr_backend_is_headless(void *p) { return p == 0; }\n')
            put('entry.c','''#include "sway/output.h"
#include "telemetry.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
int main(int argc, char **argv) {
    struct wlr_output w = {.backend=(void*)1,.render_format=1};
    struct sway_output o = {.wlr_output=&w,.width=568,.height=1232};
    assert(card_bench_arm(&o,"injected",1));
    bool native = argc > 1 && !strcmp(argv[1],"native");
    bool stale = argc > 1 && !strcmp(argv[1],"stale");
    if (native || stale) card_bench_input_begin(1,"motion",true);
    if (stale) card_bench_input_end(false,false);
    struct timespec delay={.tv_nsec=1000000}; nanosleep(&delay,0);
    struct timespec before; clock_gettime(CLOCK_MONOTONIC,&before);
    printf("BEFORE_IPC=%llu\\n",(unsigned long long)before.tv_sec*1000000000+before.tv_nsec);
    card_bench_phase(true,1);
    if (native) card_bench_input_end(true,false);
    card_bench_stop();
}
''')
            binary=root/'entry'
            subprocess.run([os.environ.get('CC','cc'),'-std=gnu11','-I'+str(root),
                str(ROOT/'nix/card-shell/telemetry.c'),str(root/'entry.c'),'-o',str(binary)],check=True)
            spec=importlib.util.spec_from_file_location('card_benchmark',ROOT/'tools/card-shell-benchmark.py')
            parser=importlib.util.module_from_spec(spec);spec.loader.exec_module(parser)
            for mode in ('native','ipc','stale'):
                with self.subTest(mode=mode):
                    output=subprocess.check_output([str(binary),mode],text=True)
                    rows,_=parser.parse_rows(output.encode())
                    session=next(row for row in rows if row['event']=='session')
                    baseline=next(row for row in rows if row['event']=='resource')
                    self.assertLessEqual(baseline['t_ns'],session['t_ns'])
                    if mode=='native':
                        event=next(row for row in rows if row['event']=='input')
                        self.assertLessEqual(session['t_ns'],event['t_ns'])
                    else:
                        before=int(next(line.split('=')[1] for line in output.splitlines() if line.startswith('BEFORE_IPC=')))
                        self.assertGreaterEqual(session['t_ns'],before)
                    self.assertEqual(session['cards'],1)
                    # Missing samples may be INCOMPLETE; genuine producer
                    # ordering must never be invalid in the real consumer.
                    parser.analyze_run(session['run'],rows)

            # Deterministic CPU clock: real producer accounting must keep input,
            # failed renders, successful render, and other charged work distinct.
            put('profile.c', r'''#include "sway/output.h"
#include "telemetry.h"
#include <assert.h>
#include <time.h>
static unsigned long long cpu=100, wall=1000;
int profile_clock(clockid_t clock, struct timespec *t) {
    t->tv_sec=10; t->tv_nsec=clock==CLOCK_PROCESS_CPUTIME_ID ? cpu : wall;
    return 0;
}
int main(void) {
    struct wlr_output w={.backend=(void*)1,.render_format=1,.commit_seq=1};
    struct sway_output o={.wlr_output=&w,.scene_output=(void*)1,.width=568,.height=1232};
    assert(card_bench_arm(&o,"injected",1)); card_bench_phase(true,1);
    card_bench_input_begin(1,"motion",true);
    uint64_t start=card_bench_input_stage_begin(); cpu+=2; card_bench_input_stage_end(CARD_BENCH_POLICY,start);
    start=card_bench_input_stage_begin(); cpu+=3; card_bench_input_stage_end(CARD_BENCH_SCENE,start);
    card_bench_scene_damage();
    start=card_bench_input_stage_begin(); cpu+=1; card_bench_input_stage_end(CARD_BENCH_CHROME,start);
    cpu+=1; card_bench_input_end(true,false);
    card_bench_work_begin(); cpu+=3; card_bench_work_end();
    wall+=1000000; card_bench_render_begin(&o); cpu+=2; card_bench_render_stage(&o,CARD_BENCH_BUILD);
    cpu+=5; wall+=2000000; card_bench_commit_begin(&o); cpu+=3; wall+=3000000;
    card_bench_render_end(&o,true);
    card_bench_frame_done(o.scene_output);
    card_bench_frame_done(o.scene_output); /* multiple surfaces: one frame event */
    struct wlr_output_event_present shown={.when={.tv_sec=10,.tv_nsec=wall},.commit_seq=1,.presented=true};
    card_bench_present(&o,&shown);
    card_bench_input_begin(1,"release",true); cpu+=2;
    card_bench_scene_damage(); card_bench_input_end(true,true);
    card_bench_render_begin(&o); cpu+=1; card_bench_render_stage(&o,CARD_BENCH_BUILD);
    cpu+=4; card_bench_render_end(&o,false);
    card_bench_schedule(&o,3);
    wall+=4000000;
    card_bench_render_begin(&o); cpu+=1; card_bench_render_stage(&o,CARD_BENCH_BUILD);
    cpu+=2; w.commit_seq=2; card_bench_motion_settled(true); wall+=5000000; card_bench_commit_begin(&o); cpu+=3; wall+=6000000;
    card_bench_render_end(&o,true);
    card_bench_frame_done(o.scene_output);
    shown.commit_seq=2; shown.when.tv_nsec=wall; card_bench_present(&o,&shown);
    card_bench_stop();
}
''')
            binary=root/'profile'
            subprocess.run([os.environ.get('CC','cc'),'-std=gnu11','-Dclock_gettime=profile_clock',
                '-I'+str(root),str(ROOT/'nix/card-shell/telemetry.c'),str(root/'profile.c'),
                '-o',str(binary)],check=True)
            output=subprocess.check_output([str(binary)],text=True)
            profiles=[dict(field.split('=') for field in line.split()[2:])
                      for line in output.splitlines() if line.startswith('K230_CARD_SHELL frame-cost ')]
            self.assertEqual(len(profiles),2)
            for record,expected in zip(profiles,((1,20,10,7),(2,13,11,2))):
                self.assertEqual(tuple(int(record[k]) for k in
                    ('frame_id','total_cpu_ns','render_cpu_ns','input_cpu_ns')),expected)
            stages=[dict(field.split('=') for field in line.split()[2:])
                    for line in output.splitlines() if line.startswith('K230_CARD_SHELL repaint-cost ')]
            self.assertEqual(len(stages),2)
            for record,expected in zip(stages,((1,10,2,5,3,1,0),(2,11,2,6,3,2,1))):
                self.assertEqual(tuple(int(record[k]) for k in
                    ('frame_id','render_cpu_ns','prepare_cpu_ns','build_cpu_ns','commit_cpu_ns','attempts','failed_attempts')),expected)
            costs=[dict(field.split('=') for field in line.split()[2:])
                   for line in output.splitlines() if line.startswith('K230_CARD_SHELL input-cost ')]
            self.assertEqual(len(costs),2)
            self.assertEqual(tuple(int(costs[0][k]) for k in
                ('cpu_ns','policy_cpu_ns','scene_cpu_ns','chrome_cpu_ns')),(7,2,3,1))
            self.assertEqual(tuple(int(costs[1][k]) for k in
                ('cpu_ns','policy_cpu_ns','scene_cpu_ns','chrome_cpu_ns')),(2,0,0,0))
            rows,ignored=parser.parse_rows(output.encode())
            timing=[dict(field.split('=') for field in line.split()[2:])
                    for line in output.splitlines() if line.startswith('K230_CARD_SHELL repaint-timing ')]
            self.assertEqual(len(timing),2) # failed render emits no committed-frame timing
            self.assertEqual((int(timing[0]['scheduled_ns']),int(timing[0]['delay_ms'])),(0,0))
            self.assertEqual((int(timing[1]['scheduled_ns']),int(timing[1]['delay_ms'])),(10_006_001_000,3))
            self.assertEqual(tuple(int(timing[0][k]) for k in
                ('start_ns','commit_start_ns','end_ns')),(10_001_001_000,10_003_001_000,10_006_001_000))
            self.assertEqual(tuple(int(timing[1][k]) for k in
                ('start_ns','commit_start_ns','end_ns')),(10_010_001_000,10_015_001_000,10_021_001_000))
            self.assertEqual(ignored,14) # two diagnostic rows; frozen benchmark schema unchanged
            self.assertEqual([row['update_cpu_ns'] for row in rows if row['event']=='submit'],[20,13])
            # Feed the actual C producer output into the motion consumer. The
            # existing benchmark parser continues accepting its frozen schema.
            spec=importlib.util.spec_from_file_location('motion_trace',ROOT/'tools/shell-motion-trace.py')
            motion=importlib.util.module_from_spec(spec);spec.loader.exec_module(motion)
            motion_rows=motion.rows_from_log(output.encode())
            measured=next(iter(motion.analyze(motion_rows).values()))
            self.assertEqual(measured['stages_observed'],list(motion.STAGES))
            self.assertEqual(measured['incomplete_stage_chains'],0)
            self.assertEqual(measured['status'],'INCOMPLETE') # deliberately short sample
            self.assertEqual(len([line for line in output.splitlines() if 'motion-frame' in line]),2)
            # Removing actual final-frame evidence must not turn the first
            # post-release present into a settlement measurement.
            partial='\n'.join(line for line in output.splitlines() if 'motion-settle' not in line)
            unfinished=next(iter(motion.analyze(motion.rows_from_log(partial.encode())).values()))
            self.assertEqual(unfinished['unresolved_traces'],1)
            self.assertEqual(unfinished['settle_ms'],[])


            put('coalesce.c', r'''#include "sway/output.h"
#include "telemetry.h"
#include <assert.h>
#include <time.h>
int main(void) {
    struct wlr_output w={.backend=(void*)1,.render_format=1,.commit_seq=1};
    struct sway_output o={.wlr_output=&w,.scene_output=(void*)1,.width=568,.height=1232};
    assert(card_bench_arm(&o,"injected",1)); card_bench_phase(true,1);
    card_bench_input_begin(1,"motion",true); card_bench_input_end(true,false);
    card_bench_input_begin(1,"motion",true); card_bench_scene_damage();
    card_bench_input_end(true,false);
    card_bench_render_begin(&o); card_bench_commit_begin(&o); card_bench_render_end(&o,true);
    struct wlr_output_event_present shown={.commit_seq=1,.presented=true};
    clock_gettime(CLOCK_MONOTONIC,&shown.when);
    card_bench_frame_done(o.scene_output); card_bench_present(&o,&shown);
    card_bench_stop();
}
''')
            coalesced=root/'coalesce'
            subprocess.run([os.environ.get('CC','cc'),'-std=gnu11','-I'+str(root),
                str(ROOT/'nix/card-shell/telemetry.c'),str(root/'coalesce.c'),'-o',str(coalesced)],check=True)
            emitted=subprocess.check_output([str(coalesced)],text=True)
            sample=next(iter(motion.analyze(motion.rows_from_log(emitted.encode())).values()))
            self.assertEqual(sample['incomplete_stage_chains'],0)
            self.assertEqual(sample['traces'],2)
            self.assertLess(sample['stage_timings']['frame_done_to_present_ms']['p50'],0)
            spec=importlib.util.spec_from_file_location('repaint_profile',ROOT/'docs/evidence/card-shell/repaint-stages/analyze.py')
            repaint=importlib.util.module_from_spec(spec);spec.loader.exec_module(repaint)
            result=repaint.analyze(output.encode())['runs'][0]
            self.assertEqual((result['frames'],result['attempts'],result['uncommitted_attempts']),(2,3,1))
            self.assertAlmostEqual(result['stages']['build']['percent_of_render_cpu'],100*11/21)
            spec=importlib.util.spec_from_file_location('input_profile',ROOT/'docs/evidence/card-shell/input-cost-probe/analyze.py')
            input_profile=importlib.util.module_from_spec(spec);spec.loader.exec_module(input_profile)
            input_result=input_profile.analyze(output.encode())['runs'][0]
            self.assertEqual((input_result['inputs'],input_result['hottest_inputs'][0]['frame_id']),(2,1))
            self.assertEqual(input_result['hottest_inputs'][0]['scene_cpu_ns'],3)
            cost=next(line for line in output.splitlines() if line.startswith('K230_CARD_SHELL input-cost '))
            for corrupted in (output.replace(cost+'\n',''),output+cost+'\n',
                              output.replace('scene_cpu_ns=3','scene_cpu_ns=8',1),
                              output.replace('cpu_ns=7 policy_cpu_ns=2','cpu_ns=8 policy_cpu_ns=2',1)):
                with self.subTest(input_corrupted=corrupted):
                    with self.assertRaises(ValueError):input_profile.analyze(corrupted.encode())
            diagnostic=next(line for line in output.splitlines() if line.startswith('K230_CARD_SHELL repaint-cost '))
            for corrupted in (output.replace(diagnostic+'\n',''),output+diagnostic+'\n',
                              output.replace('prepare_cpu_ns=2','prepare_cpu_ns=3',1),
                              output.replace('attempts=1 failed_attempts=0','attempts=2 failed_attempts=0',1),
                              output.replace('render_cpu_ns=10 prepare_cpu_ns=2','render_cpu_ns=11 prepare_cpu_ns=3',1)):
                with self.subTest(corrupted=corrupted):
                    with self.assertRaises(ValueError):repaint.analyze(corrupted.encode())


if __name__=='__main__':unittest.main()
