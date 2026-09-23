#!/usr/bin/env python3
"""Actual adapter order helper plus pinned wlroots ordering functions.

Only scene damage notification is stubbed. No panel or frame-cost claim.
Set WLROOTS_SOURCE to the pinned wlroots source directory from Nix.
"""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


def function(text, signature):
    start=text.index(signature)
    return text[start:text.index('\n}',start)+2]+'\n'


class MirrorOrder(unittest.TestCase):
    def test_stable_order_restacks_and_removed_nodes(self):
        source=os.environ.get('WLROOTS_SOURCE')
        if not source:
            raise RuntimeError('Set WLROOTS_SOURCE to the pinned wlroots source directory')
        wlroots=(Path(source)/'types/scene/wlr_scene.c').read_text()
        adapter=(ROOT/'nix/card-shell/adapter.c').read_text()
        program='''#include <assert.h>
#include <stddef.h>
#include <wayland-util.h>
struct wlr_scene_tree;
struct wlr_scene_node { struct wl_list link; struct wlr_scene_tree *parent; int id; };
struct wlr_scene_tree { struct wl_list children; };
struct wlr_scene_buffer { struct wlr_scene_node node; };
static int updates;
static void scene_node_update(struct wlr_scene_node *node, void *damage) {
    (void)node; (void)damage; updates++;
}
'''
        for name in ('place_above','place_below','raise_to_top','lower_to_bottom'):
            program+=function(wlroots,'void wlr_scene_node_'+name+'(')
        program+=function(adapter,'static void order_mirror(')
        program+='''
static struct wlr_scene_tree tree;
static struct wlr_scene_buffer nodes[4];
static void arrange(const int *order, int n) {
    struct wlr_scene_node *previous=NULL;
    for (int i=0;i<n;i++) order_mirror(&previous,&nodes[order[i]]);
}
static void check(const int *order, int n) {
    int i=0; struct wlr_scene_node *node;
    wl_list_for_each(node,&tree.children,link) {
        assert(i<n && node->id==order[i]); i++;
    }
    assert(i==n);
}
int main(void) {
    wl_list_init(&tree.children);
    for (int i=0;i<4;i++) {
        nodes[i].node.parent=&tree; nodes[i].node.id=i;
        wl_list_insert(tree.children.prev,&nodes[i].node.link);
    }
    const int initial[]={0,1,2,3};
    arrange(initial,4); check(initial,4); assert(updates==0);
    /* Old adapter operation restores the same final order but damages every
     * node. The new operation must avoid that churn. */
    for (int i=0;i<4;i++) wlr_scene_node_raise_to_top(&nodes[i].node);
    check(initial,4); assert(updates==4);
    for (int a=0;a<4;a++) for (int b=0;b<4;b++)
    for (int c=0;c<4;c++) for (int d=0;d<4;d++) {
        if (a==b || a==c || a==d || b==c || b==d || c==d) continue;
        const int order[]={a,b,c,d}; arrange(order,4); check(order,4);
        updates=0; arrange(order,4); check(order,4); assert(updates==0);
    }
    wl_list_remove(&nodes[1].node.link);
    const int reduced[]={2,0,3}; arrange(reduced,3); check(reduced,3);
    updates=0; arrange(reduced,3); assert(updates==0);
    wl_list_insert(tree.children.prev,&nodes[1].node.link);
    const int inserted[]={2,1,0,3}; arrange(inserted,4); check(inserted,4);
    updates=0; arrange(inserted,4); assert(updates==0);
}
'''
        with tempfile.TemporaryDirectory(prefix='card-order-') as directory:
            p=Path(directory);(p/'test.c').write_text(program)
            flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','wayland-server'],text=True))
            subprocess.run([os.environ.get('CC','cc'),'-std=gnu11','-Wall','-Wextra','-Werror',
                            '-fsanitize=address,undefined',str(p/'test.c'),'-o',str(p/'test'),*flags],check=True)
            subprocess.run([str(p/'test')],check=True)


if __name__=='__main__':unittest.main()
