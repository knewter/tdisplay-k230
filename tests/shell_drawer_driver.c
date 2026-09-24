#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "drawer.h"

static struct shell_drawer fresh(void) {
  struct shell_drawer d = { .pointer_id = -1 };
  drawer_geometry(&d, 400, 1200);
  return d;
}
int main(int argc, char **argv) {
  if (argc != 2) return 2;
  const char *name = argv[1];
  struct shell_drawer d = fresh();
  if (!strcmp(name, "drawer-drag")) {
    assert(drawer_begin(&d, 1, 300, 0));
    assert(drawer_move(&d, 1, 180, 50));
    assert(d.offset == 120);
    assert(!drawer_release(&d, 1));
  } else if (!strcmp(name, "flick-stop")) {
    assert(drawer_begin(&d, 1, 300, 0));
    assert(drawer_move(&d, 1, 150, 50));
    assert(!drawer_release(&d, 1));
    assert(drawer_tick(&d, 16));
    int coasting = d.offset;
    assert(coasting > 150 && coasting <= drawer_limit(&d));
    assert(drawer_begin(&d, 2, 150, 90));
    assert(!drawer_release(&d, 2));
    assert(!drawer_tick(&d, 16) && d.offset == coasting);
  } else if (!strcmp(name, "cancel-below-threshold")) {
    assert(drawer_begin(&d, 1, 300, 0));
    assert(!drawer_move(&d, 1, 289, 50));
    assert(d.offset == 0);
    drawer_cancel(&d);
    assert(!drawer_release(&d, 1));
  } else if (!strcmp(name, "tap-launch")) {
    assert(drawer_begin(&d, 1, 300, 0));
    assert(drawer_release(&d, 1));
    assert(!drawer_release(&d, 1));
  } else if (!strcmp(name, "hold-cue")) {
    assert(drawer_begin(&d, 1, 300, 0));
    assert(!drawer_press_cue(&d, 1, 249));
    assert(drawer_press_cue(&d, 1, 250));
    assert(!drawer_long_press(&d, 1, 499));
    assert(drawer_long_press(&d, 1, 500));
    assert(!drawer_release(&d, 1));
  } else if (!strcmp(name, "move-cancel")) {
    assert(drawer_begin(&d, 1, 300, 0));
    assert(drawer_press_cue(&d, 1, 260));
    drawer_move(&d, 1, 275, 280);
    assert(!drawer_long_press(&d, 1, 600));
    assert(!drawer_release(&d, 1));
  } else if (!strcmp(name, "back-cancel")) {
    assert(drawer_begin(&d, 1, 300, 0));
    drawer_cancel(&d);
    assert(!drawer_release(&d, 1));
  } else if (!strcmp(name, "second-contact")) {
    assert(drawer_begin(&d, 1, 300, 0));
    assert(!drawer_begin(&d, 2, 310, 20));
    assert(!drawer_release(&d, 1));
    assert(!drawer_release(&d, 2));
  } else return 2;
  puts(name);
  return 0;
}
