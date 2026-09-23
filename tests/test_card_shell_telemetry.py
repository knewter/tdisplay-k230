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
struct sway_output { struct wlr_output *wlr_output; int width,height; };
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

if __name__=='__main__':unittest.main()
