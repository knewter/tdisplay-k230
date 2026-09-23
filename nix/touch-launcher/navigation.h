#ifndef K230_LAUNCHER_NAVIGATION_H
#define K230_LAUNCHER_NAVIGATION_H
#include <stdbool.h>

enum action {
  ACT_TERMINAL = -1, ACT_MONITOR = -2, ACT_NEW_TERMINAL = -3,
  ACT_BACK = -4, ACT_PREVIOUS = -5, ACT_NEXT = -6, ACT_HELP = -7,
  ACT_NONE = -8
};
enum { BUILTIN_COUNT = 4, HELP_TOPIC_COUNT = 8 };
struct launcher_navigation {
  int page, help_page, page_size;
  bool help;
};
static int launcher_item_action(int item) {
  if (item < 0) return ACT_NONE;
  if (item < 3) return -item - 1;
  if (item == 3) return ACT_HELP;
  return item - BUILTIN_COUNT;
}
static int launcher_pages(const struct launcher_navigation *nav, int app_count) {
  int count = nav->help ? HELP_TOPIC_COUNT : BUILTIN_COUNT + app_count;
  return (count + nav->page_size - 1) / nav->page_size;
}
static int launcher_current_page(const struct launcher_navigation *nav) {
  return nav->help ? nav->help_page : nav->page;
}
/* 0: launch action, 1: stay on the surface, 2: close the launcher. */
static int launcher_navigate(struct launcher_navigation *nav, int action, int app_count) {
  if (action == ACT_NONE) return 1;
  if (action == ACT_HELP) {
    nav->help = true;
    nav->help_page = 0;
    return 1;
  }
  if (action == ACT_BACK) {
    if (!nav->help) return 2;
    nav->help = false;
    return 1;
  }
  if (action == ACT_PREVIOUS || action == ACT_NEXT) {
    int *page = nav->help ? &nav->help_page : &nav->page;
    int next = *page + (action == ACT_NEXT ? 1 : -1);
    if (next >= 0 && next < launcher_pages(nav, app_count)) *page = next;
    return 1;
  }
  return 0;
}
#endif
