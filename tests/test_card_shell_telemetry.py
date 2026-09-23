#!/usr/bin/env python3
"""Exercise the actual producer's entry ordering with small backend stubs."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class EntryTiming(unittest.TestCase):
    def test_first_native_input_precedes_phase_header_without_invalid_time(self):
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
#include <time.h>
int main(void) {
    struct wlr_output w = {.backend=(void*)1,.render_format=1};
    struct sway_output o = {.wlr_output=&w,.width=568,.height=1232};
    assert(card_bench_arm(&o,"injected",1));
    card_bench_input_begin(1,"motion",true);
    struct timespec delay={.tv_nsec=1000000}; nanosleep(&delay,0);
    card_bench_phase(true,1);
    card_bench_input_end(true,false);
    card_bench_stop();
}
''')
            binary=root/'entry'
            subprocess.run([os.environ.get('CC','cc'),'-std=gnu11','-I'+str(root),
                str(ROOT/'nix/card-shell/telemetry.c'),str(root/'entry.c'),'-o',str(binary)],check=True)
            output=subprocess.check_output([str(binary)],text=True)
            rows=[dict(word.split('=',1) for word in line.split()[1:]) for line in output.splitlines()]
            session=next(row for row in rows if row['event']=='session')
            event=next(row for row in rows if row['event']=='input')
            baseline=next(row for row in rows if row['event']=='resource')
            self.assertLessEqual(int(session['t_ns']),int(baseline['t_ns']))
            self.assertLessEqual(int(session['t_ns']),int(event['t_ns']))
            self.assertEqual(session['cards'],'1')

if __name__=='__main__':unittest.main()
