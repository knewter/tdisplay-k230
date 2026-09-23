"""Exercise the launcher's actual navigation model without a display server."""
from pathlib import Path
import subprocess
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


if __name__ == "__main__":
    unittest.main()
