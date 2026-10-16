#!/usr/bin/env python3
"""Exercise the compositor's drawer gesture and fixed-argv helper route."""
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CardDrawerRoute(unittest.TestCase):
    def test_exact_output_endpoint_enters_real_card_policy(self):
        with tempfile.TemporaryDirectory(prefix="card-route-endpoint-") as directory:
            path = Path(directory)
            (path / "sway").mkdir()
            (path / "sway/card_shell_route.h").write_bytes(
                (ROOT / "nix/card-shell/route.h").read_bytes())
            source = path / "endpoint.c"
            source.write_text(r'''
#include <assert.h>
#include <math.h>
#include "sway/card_shell_route.h"
#include "card-shell-policy.h"
int main(void) {
    const double sizes[][2] = {{568,1232},{1080,1920}};
    for (unsigned i=0; i<2; i++) {
        double w=sizes[i][0], h=sizes[i][1];
        struct cs_config cfg=cs_default_config(w,h);
        cfg.touch_first_motion=true;
        struct cs_policy p;
        assert(cs_init(&p,&cfg));
        struct cs_card cards[]={{7,CS_LIVE,true,true}};
        cs_set_cards(&p,cards,1);
        /* Replay the physical HDMI failure: y == height is outside. */
        assert(!cs_begin_entry(&p,1,w/2,h,1,7).consumed);
        double bottom=card_shell_touch_output_coordinate(h,h);
        assert(bottom<h && bottom>h-0.000001);
        assert(cs_begin_entry(&p,1,w/2,bottom,2,7).consumed);
        assert(p.mode==CS_ENTERING && p.edge.tracking);
        cs_stream_cancel(&p);
        cs_leave(&p);
        double right=card_shell_touch_output_coordinate(w,w);
        assert(cs_begin_entry(&p,2,right,bottom,3,7).consumed);
        cs_stream_cancel(&p);
        cs_leave(&p);
        p.config.bottom_reserved=120;
        assert(!cs_begin_entry(&p,3,w/2,bottom,4,7).consumed);
        cs_finish(&p);
        /* Preserve real interior, off-output and nonfinite coordinates. */
        assert(card_shell_touch_output_coordinate(h/2,h)==h/2);
        assert(card_shell_touch_output_coordinate(h+1,h)==h+1);
        assert(card_shell_touch_output_coordinate(-1,h)==-1);
        assert(isnan(card_shell_touch_output_coordinate(NAN,h)));
    }
    return 0;
}
''')
            binary = path / "endpoint"
            subprocess.run([os.environ.get("CC", "cc"), "-std=gnu11", "-Wall",
                            "-Wextra", "-Werror", "-I" + str(path),
                            "-I" + str(ROOT / "nix/card-shell-policy"), str(source),
                            str(ROOT / "nix/card-shell/route.c"),
                            str(ROOT / "nix/card-shell-policy/card-shell-policy.c"),
                            "-lm", "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)

    def test_side_edge_back_and_touch_ownership(self):
        with tempfile.TemporaryDirectory(prefix="card-route-side-") as directory:
            path = Path(directory)
            (path / "sway").mkdir()
            (path / "sway/card_shell_route.h").write_bytes(
                (ROOT / "nix/card-shell/route.h").read_bytes())
            source = path / "side.c"
            source.write_text(r'''
#include <assert.h>
#include <math.h>
#include <string.h>
#include "sway/card_shell_route.h"
/* 568x1232 is the panel; 1280x800 the HDMI landscape output. */
static struct card_shell_ownership at(double w, double h, double x, double y) {
    return (struct card_shell_ownership){.x=x,.y=y,.width=w,.height=h,.edge_band=48};
}
int main(void) {
    const double sizes[][2] = {{568,1232},{1280,800}};
    for (unsigned i=0; i<2; i++) {
        double w=sizes[i][0], h=sizes[i][1], mid=h/2;
        struct card_shell_ownership t;
        /* Dismiss order: sheet, then Settings/shade/drawer, then keyboard. */
        assert(card_shell_back_target(true,true,true)==CARD_BACK_SHEET);
        assert(card_shell_back_target(false,true,true)==CARD_BACK_OVERLAY);
        assert(card_shell_back_target(false,false,true)==CARD_BACK_KEYBOARD);
        assert(card_shell_back_target(false,false,false)==CARD_BACK_NONE);
        /* side-qualified: both edges, with a context to dismiss. */
        t=at(w,h,10,mid); t.overlay=true;
        assert(card_shell_touch_owner(&t)==CARD_OWNER_BACK);
        t=at(w,h,w-10,mid); t.keyboard_shown=true;
        assert(card_shell_touch_owner(&t)==CARD_OWNER_BACK);
        t=at(w,h,10,mid); t.sheet=true;
        assert(card_shell_touch_owner(&t)==CARD_OWNER_BACK);
        /* app-scroll-conflict: no context, or outside the band, stays with the app. */
        t=at(w,h,10,mid);
        assert(card_shell_touch_owner(&t)==CARD_OWNER_APP);
        t.deck=true;
        assert(card_shell_touch_owner(&t)==CARD_OWNER_DECK);
        t=at(w,h,w/2,mid); t.overlay=true; t.keyboard_shown=true;
        assert(card_shell_touch_owner(&t)==CARD_OWNER_APP);
        t=at(w,h,48,mid); t.overlay=true;      /* first pixel outside the band */
        assert(card_shell_touch_owner(&t)==CARD_OWNER_APP);
        t=at(w,h,w-49,mid); t.overlay=true;
        assert(card_shell_touch_owner(&t)==CARD_OWNER_APP);
        /* bottom-qualified and top-qualified corners are not side Back. */
        t=at(w,h,10,h-10); t.overlay=true;
        assert(card_shell_touch_owner(&t)==CARD_OWNER_HOME);
        t=at(w,h,10,10);
        assert(card_shell_touch_owner(&t)==CARD_OWNER_SHADE);
        t=at(w,h,10,10); t.overlay=true;       /* the overlay keeps its own top controls */
        assert(card_shell_touch_owner(&t)==CARD_OWNER_APP);
        t=at(w,h,10,h-10); t.bottom_reserved=120;
        assert(card_shell_touch_owner(&t)!=CARD_OWNER_HOME);
        /* keyboard-inset: the keyboard wins in its reserved area. */
        t=at(w,h,10,h-100); t.overlay=true; t.keyboard_shown=true; t.keyboard_hit=true;
        assert(card_shell_touch_owner(&t)==CARD_OWNER_KEYBOARD);
        t=at(w,h,w/2,h-10); t.keyboard_hit=true;
        assert(card_shell_touch_owner(&t)==CARD_OWNER_KEYBOARD);
        /* Off-output and nonfinite touches never claim an edge. */
        t=at(w,h,-1,mid); t.overlay=true;
        assert(card_shell_touch_owner(&t)==CARD_OWNER_APP);
        t=at(w,h,NAN,mid); t.overlay=true;
        assert(card_shell_touch_owner(&t)==CARD_OWNER_APP);
        t=at(w,h,w,mid); t.overlay=true;
        assert(card_shell_touch_owner(&t)==CARD_OWNER_APP);
        assert(card_shell_side_direction(0,w,48)==1);
        assert(card_shell_side_direction(w-1,w,48)==-1);
        assert(card_shell_side_direction(w/2,w,48)==0);
        assert(!strcmp(card_shell_owner_name(CARD_OWNER_BACK),"back"));
        assert(!strcmp(card_shell_owner_name(CARD_OWNER_APP),"app"));

        /* The recognizer: inward only, past the distance, release decides. */
        struct card_shell_side_gesture g={0};
        card_shell_side_down(&g,4,10,mid,1);
        card_shell_side_motion(&g,4,60,mid+5,72);
        assert(!card_shell_side_up(&g,4));                 /* short of 72 px */
        card_shell_side_down(&g,4,10,mid,1);
        card_shell_side_motion(&g,4,100,mid+10,72);
        assert(card_shell_side_up(&g,4));                  /* left edge inward */
        card_shell_side_down(&g,4,w-10,mid,-1);
        card_shell_side_motion(&g,4,w-100,mid,72);
        assert(card_shell_side_up(&g,4));                  /* right edge inward */
        card_shell_side_down(&g,4,10,mid,1);
        card_shell_side_motion(&g,4,-40,mid,72);
        assert(!card_shell_side_up(&g,4));                 /* outward */
        card_shell_side_down(&g,4,10,mid,1);
        card_shell_side_motion(&g,4,60,mid+200,72);
        assert(!card_shell_side_up(&g,4));                 /* vertical scroll */
        card_shell_side_down(&g,4,10,mid,1);
        card_shell_side_motion(&g,4,100,mid,72);
        card_shell_side_motion(&g,4,30,mid,72);
        assert(!card_shell_side_up(&g,4));                 /* reversal */
        card_shell_side_down(&g,4,10,mid,1);
        card_shell_side_motion(&g,4,100,mid,72);
        card_shell_side_down(&g,5,300,mid,0);
        assert(!card_shell_side_up(&g,5));
        assert(!card_shell_side_up(&g,4));                 /* second contact cancels */
        card_shell_side_down(&g,4,10,mid,1);
        card_shell_side_motion(&g,4,100,mid,72);
        card_shell_side_cancel(&g);
        assert(!card_shell_side_up(&g,4));
        assert(card_shell_side_inward(1,10,mid,50,mid+10));
        assert(!card_shell_side_inward(1,10,mid,50,mid+80));
        assert(!card_shell_side_inward(-1,w-10,mid,w-5,mid));
        assert(!card_shell_side_inward(0,10,mid,50,mid));
        assert(!card_shell_side_inward(1,10,mid,NAN,mid));
    }
    return 0;
}
''')
            binary = path / "side"
            subprocess.run([os.environ.get("CC", "cc"), "-std=gnu11", "-Wall",
                            "-Wextra", "-Werror", "-I" + str(path), str(source),
                            str(ROOT / "nix/card-shell/route.c"), "-lm",
                            "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)

    def test_side_edge_back_in_adapter_never_synthesizes_a_key(self):
        text = (ROOT / "nix/card-shell/adapter.c").read_text()
        start = text.index("static void side_back_fire(void)")
        body = text[start:text.index("\n}\n", start)]
        # Only the shell clients are asked to dismiss; nothing reaches the seat.
        self.assertIn('card_shell_launch_surface("hide")', body)
        self.assertIn('keyboard_signal("hide")', body)
        for forbidden in ("wlr_seat_keyboard", "KEY_", "XKB_KEY", "wlr_seat_touch", "wlr_seat_pointer"):
            self.assertNotIn(forbidden, body)
        # The bottom-edge escape keeps its own recognizer and still sends "hide".
        escape = text[text.index("bool bottom_edge ="):]
        self.assertIn("shell.overlay_escaping = true", escape[:2500])
        self.assertIn("EDGE_OVERLAY", text)
        # Side Back is one more weak edge origin, claimed only by the arbiter.
        self.assertIn("card_shell_touch_owner(&touch) == CARD_OWNER_BACK", text)

    def test_gesture_and_trusted_helper(self):
        with tempfile.TemporaryDirectory(prefix="card-route-") as directory:
            path = Path(directory)
            include = path / "sway"
            include.mkdir()
            (include / "card_shell_route.h").write_bytes(
                (ROOT / "nix/card-shell/route.h").read_bytes()
            )
            program = path / "route-test.c"
            program.write_text(r'''
#include <assert.h>
#include <stdlib.h>
#include "sway/card_shell_route.h"
int main(int argc, char **argv) {
    assert(argc == 2);
    struct card_shell_drawer_gesture gesture = {0};
    card_shell_drawer_down(&gesture, 3, 200, 1100);
    card_shell_drawer_motion(&gesture, 3, 210, 1040, 72);
    assert(!card_shell_drawer_up(&gesture, 3));
    card_shell_drawer_down(&gesture, 3, 200, 1100);
    card_shell_drawer_motion(&gesture, 3, 210, 1000, 72);
    card_shell_drawer_motion(&gesture, 3, 210, 1090, 72);
    assert(!card_shell_drawer_up(&gesture, 3)); /* reversal */
    card_shell_drawer_down(&gesture, 3, 200, 1100);
    card_shell_drawer_motion(&gesture, 3, 350, 1000, 72);
    assert(!card_shell_drawer_up(&gesture, 3)); /* horizontal */
    card_shell_drawer_down(&gesture, 3, 200, 1100);
    card_shell_drawer_motion(&gesture, 3, 210, 1000, 72);
    card_shell_drawer_down(&gesture, 4, 210, 1000);
    assert(!card_shell_drawer_up(&gesture, 4));
    assert(!card_shell_drawer_up(&gesture, 3)); /* second contact cancels */
    card_shell_drawer_down(&gesture, 3, 200, 1100);
    card_shell_drawer_motion(&gesture, 3, 210, 1000, 72);
    card_shell_drawer_cancel(&gesture);
    assert(!card_shell_drawer_up(&gesture, 3));
    card_shell_drawer_down(&gesture, 3, 200, 1100);
    card_shell_drawer_motion(&gesture, 3, 210, 1000, 72);
    assert(card_shell_drawer_up(&gesture, 3));
    assert(!card_shell_drawer_up(&gesture, 3));
    card_shell_drawer_down(&gesture, 5, 200, 10);
    card_shell_shade_motion(&gesture, 5, 210, 110, 72);
    assert(card_shell_drawer_up(&gesture, 5));
    card_shell_drawer_down(&gesture, 5, 200, 10);
    card_shell_shade_motion(&gesture, 5, 350, 110, 72);
    assert(!card_shell_drawer_up(&gesture, 5));
    unsetenv("SWAY_K230_CARD_DRAWER_HELPER");
    assert(!card_shell_launch_surface("drawer"));
    setenv("SWAY_K230_CARD_DRAWER_HELPER", "relative/path", 1);
    assert(!card_shell_launch_surface("drawer"));
    setenv("SWAY_K230_CARD_DRAWER_HELPER", argv[1], 1);
    assert(!card_shell_launch_surface("unsupported"));
    /* The helper runs asynchronously; each route records its own argv. */
    assert(card_shell_launch_surface("hide"));
    assert(card_shell_launch_surface("shade"));
    return 0;
}
''')
            binary = path / "route-test"
            subprocess.run(
                [os.environ.get("CC", "cc"), "-std=gnu11", "-Wall", "-Wextra", "-Werror",
                 "-I" + str(path), str(program), str(ROOT / "nix/card-shell/route.c"),
                 "-lm", "-o", str(binary)], check=True,
            )
            helper = path / "helper with spaces"
            helper.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$CARD_ROUTE_CAPTURE.$2"\n')
            helper.chmod(0o700)
            capture = path / "capture"
            subprocess.run([str(binary), str(helper)], check=True,
                           env={**os.environ, "CARD_ROUTE_CAPTURE": str(capture)})
            deadline = time.monotonic() + 2
            expected = {route: ["--surface", route] for route in ("hide", "shade")}
            def results():
                return {route: Path(str(capture) + "." + route).read_text().splitlines()
                        if Path(str(capture) + "." + route).exists() else [] for route in expected}
            while results() != expected and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual(results(), expected)


if __name__ == "__main__":
    unittest.main()
