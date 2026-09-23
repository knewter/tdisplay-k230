#ifndef K230_LAUNCHER_OVERVIEW_H
#define K230_LAUNCHER_OVERVIEW_H

#include <stdbool.h>

struct launcher_overview {
  bool open;
  int page;
  int page_size;
};

static int overview_pages(const struct launcher_overview *overview, int window_count) {
  int size = overview->page_size > 0 ? overview->page_size : 1;
  return window_count > 0 ? (window_count + size - 1) / size : 1;
}

static void overview_open(struct launcher_overview *overview) {
  overview->open = true;
  overview->page = 0;
}

static void overview_close(struct launcher_overview *overview) {
  overview->open = false;
  overview->page = 0;
}

static void overview_page(struct launcher_overview *overview, int delta, int window_count) {
  int next = overview->page + delta;
  int pages = overview_pages(overview, window_count);
  if (next >= 0 && next < pages)
    overview->page = next;
}
#endif
