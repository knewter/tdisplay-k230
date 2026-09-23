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


if __name__ == "__main__":
    unittest.main()
