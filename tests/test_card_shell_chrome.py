#!/usr/bin/env python3
"""Execute the adapter's real chrome builder with fault-injectable scene stubs.

This checks cache invalidation and failure recovery, not rendering or board cost.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ChromeCache(unittest.TestCase):
    def test_layout_feedback_and_failed_builds(self):
        source = (ROOT / 'nix/card-shell/adapter.c').read_text()
        state = source[source.index('static struct {'):source.index('static const float backdrop')]
        start = source.index('static bool rebuild_chrome(void) {') if 'static bool rebuild_chrome(void)' in source else source.index('static bool chrome(void) {')
        functions = source[start:source.index('static bool sync_scene(void) {', start)]
        harness = r'''
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include "card-shell-policy.h"
struct wl_list { int unused; };
struct wl_listener { int unused; };
struct sway_output { int lx, ly; };
struct wlr_scene_node { int x, y; };
struct wlr_scene_tree { struct wlr_scene_node node; };
struct wlr_scene_buffer { struct wlr_scene_node node; };
static struct wlr_scene_tree tree;
static struct wlr_scene_buffer label;
static int builds, attempts, fail_at, last_x, last_y;
static bool allocation(void) { return ++attempts != fail_at; }
static void wlr_scene_node_destroy(struct wlr_scene_node *node) { (void)node; }
static struct wlr_scene_tree *wlr_scene_tree_create(struct wlr_scene_tree *parent) {
    (void)parent; builds++; return allocation() ? &tree : NULL;
}
static void wlr_scene_node_set_position(struct wlr_scene_node *node, int x, int y) {
    node->x=x; node->y=y;
}
static bool button(struct wlr_scene_tree *parent, int x, int y, int w,
                   const char *text, bool pressed) {
    (void)parent; (void)w; (void)text; (void)pressed;
    last_x=x; last_y=y; return allocation();
}
static struct wlr_scene_buffer *card_label(struct wlr_scene_tree *parent,
        const char *text, int w, int h, int size) {
    (void)parent; (void)text; (void)w; (void)h; (void)size;
    return allocation() ? &label : NULL;
}
const char *cs_message_text(enum cs_message message) {
    return message == CS_MESSAGE_NONE ? "" : "Close timed out";
}
static bool label_update(struct wlr_scene_tree *parent, struct wlr_scene_buffer **out,
        char **old, const char *text, int w, int h, int size) {
    (void)parent; (void)w; (void)h; (void)size;
    if (!allocation()) return false;
    free(*old); *old=strdup(text); *out=&label; return true;
}
'''
        program = harness + state + functions + r'''
#define CHANGED(expr) do { int before=builds; expr; assert(chrome()); \
    assert(builds==before+1); assert(chrome()); assert(builds==before+1); } while (0)
int main(void) {
    struct sway_output output={0}; shell.output=&output; shell.ui=&tree;
    shell.active=true;
    shell.policy.config=(struct cs_config){.width=568,.height=1232,
        .top_reserved=56,.bottom_reserved=0,.footer_height=56};
    assert(chrome()); assert(builds==1);
    for (int i=0;i<100;i++) { shell.policy.dx=i; assert(chrome()); }
    assert(builds==1);
    CHANGED(output.lx=100); assert(last_x==492);
    CHANGED(output.ly=80); assert(last_y==1256);
    CHANGED(shell.policy.config.footer_height=80); assert(last_y==1232);
    CHANGED(shell.policy.config.width=600);
    CHANGED(shell.policy.config.height=1300);
    CHANGED(shell.policy.config.top_reserved=64);
    CHANGED(shell.policy.config.bottom_reserved=400); assert(last_y==900);
    CHANGED(shell.policy.message=CS_MESSAGE_CLOSE_TIMEOUT);
    assert(!strcmp(shell.status_text,"Close timed out"));
    shell.pressed_button=2; CHANGED(shell.button_down=true);
    CHANGED(shell.pressed_button=3); CHANGED(shell.button_down=false);
    CHANGED(shell.active=false); CHANGED(shell.active=true);
    /* Fail each actual builder operation, then retry identical state. A
     * partially constructed tree must never be accepted as a cache hit. */
    for (int step=1;step<=7;step++) {
        shell.policy.config.width++;
        fail_at=attempts+step;
        assert(!chrome());
        int before=builds; fail_at=0;
        assert(chrome()); assert(builds==before+1);
        assert(chrome()); assert(builds==before+1);
    }
    shell.chrome=NULL; int before=builds;
    assert(chrome()); assert(builds==before+1);
    free(shell.status_text);
}
'''
        with tempfile.TemporaryDirectory(prefix='card-chrome-') as directory:
            path = Path(directory)
            (path / 'test.c').write_text(program)
            subprocess.run([os.environ.get('CC', 'cc'), '-std=gnu11', '-Wall', '-Wextra',
                            '-Werror', '-I' + str(ROOT / 'nix/card-shell-policy'),
                            str(path / 'test.c'), '-o', str(path / 'test')], check=True)
            subprocess.run([str(path / 'test')], check=True)


if __name__ == '__main__':
    unittest.main()
