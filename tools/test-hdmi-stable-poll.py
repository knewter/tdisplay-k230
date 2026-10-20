#!/usr/bin/env python3
"""Compile the actual patched detector and check its caller/status/cache semantics."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

REL=Path('drivers/gpu/drm/display/drm_bridge_connector.c')
PATCH=Path(__file__).resolve().parents[1]/'nix/patches/mainline/drm-bridge-connector-stable-poll.patch'


def function(text,name):
    match=re.search(r'\b'+re.escape(name)+r'\s*\(',text)
    if not match:raise ValueError('missing source function: '+name)
    start=text.rfind('\nstatic ',0,match.start())+1
    if not start:raise ValueError('missing static function declaration')
    brace=text.index('{',match.end());depth=1;end=brace+1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]


HEADER=r'''
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#define DRM_MODE_CONNECTOR_DPI 1
#define DRM_MODE_CONNECTOR_LVDS 2
#define DRM_MODE_CONNECTOR_DSI 3
#define DRM_MODE_CONNECTOR_eDP 4
#define DRM_MODE_CONNECTOR_Unknown 5
enum drm_connector_status { connector_status_connected=1, connector_status_disconnected=2, connector_status_unknown=3 };
struct drm_connector { enum drm_connector_status status; int connector_type; void *edid_blob_ptr; };
struct drm_bridge;
struct drm_bridge_funcs { enum drm_connector_status (*detect)(struct drm_bridge *,struct drm_connector *); };
struct drm_bridge { struct drm_bridge_funcs *funcs; };
struct drm_bridge_connector { struct drm_connector base; struct drm_bridge *bridge_detect,*bridge_hdmi; };
#define to_drm_bridge_connector(x) ((struct drm_bridge_connector *)(x))
static bool polling;
static enum drm_connector_status physical_status;
static int detected,refreshed,notified;
static bool drm_kms_helper_is_poll_worker(void) { return polling; }
static enum drm_connector_status bridge_detect(struct drm_bridge *b,struct drm_connector *c) { (void)b;(void)c;detected++;return physical_status; }
static void drm_atomic_helper_connector_hdmi_hotplug(struct drm_connector *c,enum drm_connector_status s) { (void)c;(void)s;refreshed++; }
static void drm_bridge_connector_hpd_notify(struct drm_connector *c,enum drm_connector_status s) { (void)c;(void)s;notified++; }
static void require(bool condition,const char *message) { if (!condition) { fprintf(stderr,"FAIL: %s\n",message);exit(1); } }
'''
MAIN=r'''
struct result { int returned,detected,refreshed,notified; };
static struct result run(bool candidate,int old,int next,bool poll,bool hdmi,bool cache,int type,bool detect) {
    struct drm_bridge_funcs funcs={ .detect=bridge_detect };
    struct drm_bridge bridge={ .funcs=&funcs };
    struct drm_bridge_connector c={ .base={.status=old,.connector_type=type,.edid_blob_ptr=cache ? &bridge : NULL},
        .bridge_detect=detect ? &bridge : NULL,.bridge_hdmi=hdmi ? &bridge : NULL };
    polling=poll;physical_status=next;detected=refreshed=notified=0;
    int value=candidate ? candidate_detect(&c.base,false) : baseline_detect(&c.base,false);
    struct result r={value,detected,refreshed,notified};return r;
}
int main(void) {
    int matrix=0,fallback=0;
    for (int old=1;old<=3;old++) for (int next=1;next<=3;next++)
    for (int poll=0;poll<=1;poll++) for (int hdmi=0;hdmi<=1;hdmi++) for (int cache=0;cache<=1;cache++) {
        struct result before=run(false,old,next,poll,hdmi,cache,DRM_MODE_CONNECTOR_Unknown,true);
        struct result after=run(true,old,next,poll,hdmi,cache,DRM_MODE_CONNECTOR_Unknown,true);
        require(after.returned==before.returned && after.detected==before.detected && after.notified==before.notified,"link detection/status/notification changed");
        /* One measured use case changes; every other matrix cell preserves
           the original refresh behavior, including uncached/HPD contexts. */
        if (old==1 && next==1 && poll==1 && hdmi==1 && cache==1)
            require(before.refreshed==1 && after.refreshed==0,"stable cached polling did not avoid refresh");
        else require(after.refreshed==before.refreshed,"refresh changed outside the qualified polling case");
        matrix++;
    }
    struct { const char *name; int old,next,poll,cache,refresh; } sequence[]={
        {"cold discovery",3,1,1,0,1}, {"stable connected poll",1,1,1,1,0},
        {"missing cache retry",1,1,1,0,1}, {"HPD already updated status",1,1,0,1,1},
        {"disconnect",1,2,1,1,1}, {"disconnected poll",2,2,1,0,1}, {"reconnect",2,1,1,0,1}
    };
    for (unsigned int i=0;i<sizeof(sequence)/sizeof(sequence[0]);i++) {
        struct result r=run(true,sequence[i].old,sequence[i].next,sequence[i].poll,true,sequence[i].cache,DRM_MODE_CONNECTOR_Unknown,true);
        require(r.refreshed==sequence[i].refresh && r.detected==1 && r.notified==1 && r.returned==sequence[i].next,sequence[i].name);
    }
    for (int type=1;type<=5;type++) {
        struct result before=run(false,3,1,true,true,true,type,false),after=run(true,3,1,true,true,true,type,false);
        require(after.returned==before.returned && after.detected==0 && after.refreshed==0 && after.notified==0,"connector fallback changed");fallback++;
    }
    printf("PASS: matrix=%d named_scenarios=7 fallback=%d\n",matrix,fallback);return 0;
}
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path);args=p.parse_args()
    original=(args.source/REL).read_text()
    with tempfile.TemporaryDirectory(prefix='hdmi-stable-poll-') as tmp:
        root=Path(tmp);target=root/REL;target.parent.mkdir(parents=True);shutil.copyfile(args.source/REL,target)
        subprocess.run(['patch','--batch','--fuzz=0','-p1','-i',str(PATCH)],cwd=root,check=True,stdout=subprocess.PIPE,text=True)
        patched=target.read_text()
        unchanged=('drm_bridge_connector_handle_hpd','drm_bridge_connector_force','drm_bridge_connector_get_modes_edid')
        for name in unchanged:
            if function(original,name)!=function(patched,name):raise ValueError('unrelated refresh path changed: '+name)
        body=HEADER+'\n'+function(original,'drm_bridge_connector_detect').replace('drm_bridge_connector_detect(', 'baseline_detect(',1)
        body+='\n'+function(patched,'drm_bridge_connector_detect').replace('drm_bridge_connector_detect(', 'candidate_detect(',1)+'\n'+MAIN
        harness=root/'harness.c';harness.write_text(body);binary=root/'harness'
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter',str(harness),'-o',str(binary)],check=True)
        result=subprocess.check_output([str(binary)],text=True).strip();print(result)
        report={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'HOST_SEMANTICS_PASS','matrix_cases':72,'named_scenarios':7,'fallback_cases':5,
            'source':str(args.source),'source_file_sha256':hashlib.sha256(original.encode()).hexdigest(),'patched_file_sha256':hashlib.sha256(patched.encode()).hexdigest(),
            'patch_sha256':hashlib.sha256(PATCH.read_bytes()).hexdigest(),'test_tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'unchanged_functions':list(unchanged),'compiler_flags':['-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter'],
            'limits':'Actual patched detector compiled with stub kernel callbacks; source/behavior proof only. Full target kernel/closure build, runtime timing, physical hotplug/input and persistent boot remain separate gates.'}
        if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
    return 0


if __name__=='__main__':raise SystemExit(main())
