"""Exercise the launcher's actual navigation model without a display server."""
from pathlib import Path
import subprocess
import shutil
import os
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Navigation(unittest.TestCase):
    def test_help_return_page_bounds_and_desktop_action_indexes(self):
        source = r'''
#include <assert.h>
#include "navigation.h"
int main(void) {
  for (int size=3; size<=4; size++) {
    for (int apps=0; apps<=9; apps++) {
      struct launcher_navigation nav={.page_size=size};
      int seen=0;
      int pages=launcher_pages(&nav,apps);
      assert(launcher_navigate(&nav,ACT_PREVIOUS,apps)==1);
      assert(nav.page==0);
      for (int page=0; page<pages; page++) {
        assert(nav.page==page);
        for (int row=0; row<size; row++) {
          int item=page*size+row;
          if(item>=BUILTIN_COUNT+apps) break;
          int action=launcher_item_action(item);
          if(item==0) assert(action==ACT_TERMINAL);
          if(item==1) assert(action==ACT_MONITOR);
          if(item==2) assert(action==ACT_NEW_TERMINAL);
          if(item==3) assert(action==ACT_HELP);
          if(item>=BUILTIN_COUNT) assert(action==seen++);
        }
        assert(launcher_navigate(&nav,ACT_NEXT,apps)==1);
      }
      assert(seen==apps);
      assert(nav.page==pages-1);
      /* Help must remain available even with no optional applications. */
      assert(launcher_navigate(&nav,ACT_HELP,apps)==1);
      assert(nav.help && launcher_current_page(&nav)==0);
      assert(launcher_navigate(&nav,ACT_PREVIOUS,apps)==1);
      assert(nav.help_page==0);
      int help_pages=launcher_pages(&nav,apps);
      for(int i=0;i<help_pages+3;i++) launcher_navigate(&nav,ACT_NEXT,apps);
      assert(nav.help_page==help_pages-1);
      assert(launcher_navigate(&nav,ACT_BACK,apps)==1);
      assert(!nav.help && nav.page==pages-1);
      assert(launcher_navigate(&nav,ACT_HELP,apps)==1);
      assert(nav.help_page==0);
      assert(launcher_navigate(&nav,ACT_NONE,apps)==1);
      assert(launcher_navigate(&nav,ACT_BACK,apps)==1);
      assert(launcher_navigate(&nav,ACT_TERMINAL,apps)==0);
      assert(launcher_navigate(&nav,ACT_MONITOR,apps)==0);
      assert(launcher_navigate(&nav,ACT_BACK,apps)==2);
    }
  }
  return 0;
}
'''
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            (path / "navigation.c").write_text(source)
            subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                            "-I", str(ROOT / "nix/touch-launcher"),
                            str(path / "navigation.c"), "-o", str(path / "test")], check=True)
            subprocess.run([str(path / "test")], check=True)


class GesturesAndOverview(unittest.TestCase):
    def test_threshold_dominance_cancellation_and_overview_bounds(self):
        source = r'''
#include <assert.h>
#include "gesture.h"
#include "overview.h"
int main(void) {
  struct launcher_gesture g={.id=-1};
  gesture_begin(&g, 7, 100, 100);
  gesture_motion(&g, 7, 147, 100); assert(g.direction==GESTURE_NONE);
  assert(gesture_release(&g,7)==GESTURE_NONE);
  gesture_begin(&g, 7, 100, 100); gesture_motion(&g,7,160,120);
  assert(gesture_release(&g,7)==GESTURE_RIGHT);
  gesture_begin(&g, 7, 100, 100); gesture_motion(&g,7,40,80);
  assert(gesture_release(&g,7)==GESTURE_LEFT);
  gesture_begin(&g, 7, 100, 100); gesture_motion(&g,7,130,160);
  assert(gesture_release(&g,7)==GESTURE_DOWN);
  gesture_begin(&g, 7, 100, 100); gesture_motion(&g,7,145,145);
  assert(gesture_release(&g,7)==GESTURE_CANCELLED);
  gesture_begin(&g, 7, 100, 100); gesture_reject(&g);
  assert(gesture_release(&g,7)==GESTURE_CANCELLED);
  /* A release consumes the gesture, so it cannot perform a second action. */
  assert(gesture_release(&g,7)==GESTURE_CANCELLED);
  gesture_begin(&g, 7, 100, 100);
  /* A competing contact rejects the original tracked gesture. */
  gesture_reject(&g);
  assert(gesture_release(&g,7)==GESTURE_CANCELLED);
  struct launcher_overview o={.page_size=3};
  overview_open(&o); assert(o.open && o.page==0 && overview_pages(&o,0)==1);
  overview_page(&o,1,0); assert(o.page==0);
  overview_page(&o,1,7); assert(o.page==1);
  overview_page(&o,9,7); assert(o.page==1);
  overview_page(&o,1,7); assert(o.page==2);
  overview_page(&o,-9,7); assert(o.page==2);
  overview_close(&o); assert(!o.open && o.page==0);
  return 0;
}
'''
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            (path / "gesture.c").write_text(source)
            subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                            "-I", str(ROOT / "nix/touch-launcher"),
                            str(path / "gesture.c"), "-o", str(path / "test")], check=True)
            subprocess.run([str(path / "test")], check=True)


class WindowCatalogClient(unittest.TestCase):
    def test_parser_stale_focus_and_hung_helper_are_safe(self):
        """Compile the production client helpers and exercise their child boundary."""
        def first_existing(candidates):
            return next((candidate for candidate in candidates if candidate.exists()), None)

        layer = first_existing([
            Path('/usr/share/wlr-protocols/unstable/wlr-layer-shell-unstable-v1.xml'),
            *Path('/nix/store').glob('*-source/protocol/wlr-layer-shell-unstable-v1.xml'),
        ])
        xdg = first_existing([
            Path('/usr/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml'),
            *Path('/nix/store').glob('*-wayland-protocols-*/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml'),
        ])
        if not shutil.which('wayland-scanner') or not layer or not xdg:
            self.skipTest('Wayland protocol sources are unavailable for the production-client fixture')
        source = r'''
#define main launcher_program_main
#include "TOUCH_LAUNCHER"
#undef main
#include <assert.h>
#include <time.h>
static void pause_ms(long ms) {
  struct timespec wait = { .tv_sec = 0, .tv_nsec = ms * 1000000 };
  nanosleep(&wait, NULL);
}
static void drain_catalog(void) {
  for (int i = 0; catalog.pid && i < 100; i++) {
    catalog_poll();
    pause_ms(5);
  }
  assert(catalog.pid == 0);
}
int main(int argc, char **argv) {
  assert(argc == 6);
  GPtrArray *parsed = parse_window_catalog(
    "17\tTerminal\tfoot\tfocused\nnot-an-id\tbad\tbad\tnormal\n");
  assert(parsed->len == 1);
  assert(!strcmp(((struct window_card *)g_ptr_array_index(parsed, 0))->id, "17"));
  g_ptr_array_unref(parsed);
  parsed = parse_window_catalog("18\tOne\tfirst\tnormal\n19\tTwo\tsecond\turgent\n");
  assert(parsed->len == 2);
  g_ptr_array_unref(parsed);
  parsed = parse_window_catalog("");
  assert(parsed->len == 0);
  g_ptr_array_unref(parsed);

  /* A second contact rejects the whole sequence until every contact lifts. */
  width=568; height=1232; touch_id=-1; touch_contact_count=0; touch_rejected=false;
  touch_down(NULL,NULL,0,0,NULL,7,0,0);
  touch_down(NULL,NULL,0,0,NULL,8,0,0);
  assert(touch_rejected && touch_contact_count==2);
  touch_up(NULL,NULL,0,0,7);
  assert(touch_rejected && touch_contact_count==1 && touch_id==-1);
  touch_down(NULL,NULL,0,0,NULL,9,0,0);
  assert(touch_rejected && touch_contact_count==2 && touch_id==-1);
  touch_up(NULL,NULL,0,0,8);
  touch_up(NULL,NULL,0,0,9);
  assert(!touch_rejected && touch_contact_count==0);
  touch_down(NULL,NULL,0,0,NULL,10,0,0);
  assert(touch_id==10);
  touch_cancel(NULL,NULL);

  windows = g_ptr_array_new_with_free_func(free_window_card);
  struct window_card *old = g_new0(struct window_card, 1);
  old->id = g_strdup("17");
  g_ptr_array_add(windows, old);
  setenv("K230_WINDOW_CATALOG", argv[1], 1);
  assert(catalog_start(CATALOG_FOCUS, "17"));
  drain_catalog();
  assert(windows->len == 1);
  assert(!strcmp(((struct window_card *)g_ptr_array_index(windows, 0))->id, "18"));
  assert(launch_error && !strcmp(launch_error, "Window closed; overview refreshed"));

  struct window_card *current = g_new0(struct window_card, 1);
  current->id = g_strdup("18");
  g_ptr_array_add(windows, current);
  setenv("K230_SWAYMSG", argv[3], 1);
  setenv("K230_WINDOW_CATALOG", argv[1], 1);
  assert(catalog_start(CATALOG_FOCUS, "18"));
  drain_catalog();
  for (int i = 0; access(argv[4], F_OK) && i < 100; i++) pause_ms(5);
  assert(access(argv[4], F_OK) == 0);
  FILE *record=fopen(argv[4], "r");
  char criterion[64], command[16];
  assert(record && fgets(criterion, sizeof criterion, record));
  assert(fgets(command, sizeof command, record));
  fclose(record);
  assert(!strcmp(criterion, "[con_id=18]\n"));
  assert(!strcmp(command, "focus\n"));

  setenv("K230_WINDOW_CATALOG", argv[2], 1);
  assert(catalog_start(CATALOG_OPEN, NULL));
  catalog.deadline_ms = monotonic_ms() - 1;
  catalog_poll();
  assert(launch_error && !strcmp(launch_error, "Window overview refresh exceeded 200 ms"));
  assert(windows->len == 0);
  drain_catalog();

  setenv("K230_WINDOW_CATALOG", argv[5], 1);
  assert(catalog_start(CATALOG_OPEN, NULL));
  for (int i = 0; catalog.output_fd >= 0 && i < 100; i++) {
    catalog_poll();
    pause_ms(2);
  }
  assert(catalog.output_fd == -1 && catalog.term_sent);
  int64_t flood_deadline=catalog.deadline_ms;
  catalog_poll();
  assert(catalog.deadline_ms == flood_deadline);
  drain_catalog();
  return 0;
}
'''
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            for mode, xml, name in [
                ('client-header', layer, 'wlr-layer-shell-unstable-v1-client-protocol.h'),
                ('private-code', layer, 'wlr-layer-shell-unstable-v1-protocol.c'),
                ('client-header', xdg, 'xdg-shell-client-protocol.h'),
                ('private-code', xdg, 'xdg-shell-protocol.c'),
            ]:
                subprocess.run(['wayland-scanner', mode, str(xml), str(path / name)], check=True)
            client = (ROOT / 'nix/touch-launcher/touch-launcher.c').as_posix()
            (path / 'client.c').write_text(source.replace('TOUCH_LAUNCHER', client))
            fresh = path / 'fresh.sh'
            fresh.write_text('#!/bin/sh\nprintf "18\\tNew title\\tnew.app\\tnormal\\n"\n')
            fresh.chmod(0o755)
            hung = path / 'hung.sh'
            hung.write_text('#!/bin/sh\ntrap "" TERM\nwhile :; do :; done\n')
            hung.chmod(0o755)
            flood = path / 'flood.sh'
            flood.write_text('#!/bin/sh\ntrap "" TERM\nwhile :; do printf "9\ttoo much\tapp\tnormal\n"; done\n')
            flood.chmod(0o755)
            focus = path / 'focus.sh'
            record = path / 'focus-record'
            focus.write_text('#!/bin/sh\nprintf "%s\n%s\n" "$1" "$2" > "$RECORD"\n')
            focus.chmod(0o755)
            flags = subprocess.check_output(['pkg-config', '--cflags', '--libs',
                                             'wayland-client', 'gio-unix-2.0', 'pangocairo'], text=True).split()
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-Wno-unused-parameter', '-Wno-misleading-indentation',
                            '-DK230_CATALOG_LIBRARY', '-I', str(path),
                            '-I', str(ROOT / 'nix/touch-launcher'), str(path / 'client.c'),
                            str(ROOT / 'nix/touch-launcher/catalog.c'),
                            str(path / 'wlr-layer-shell-unstable-v1-protocol.c'),
                            str(path / 'xdg-shell-protocol.c'), '-o', str(path / 'test'), *flags], check=True)
            subprocess.run([str(path / 'test'), str(fresh), str(hung), str(focus), str(record), str(flood)],
                           check=True, timeout=3, env=os.environ | {'RECORD': str(record)})


if __name__ == "__main__":
    unittest.main()
