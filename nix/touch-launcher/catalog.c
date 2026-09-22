#include "catalog.h"
#include <stdio.h>
#include <string.h>

static gint compare_apps(gconstpointer left, gconstpointer right) {
  GAppInfo *a = *(GAppInfo * const *)left, *b = *(GAppInfo * const *)right;
  int result = g_utf8_collate(g_app_info_get_display_name(a), g_app_info_get_display_name(b));
  return result ? result : strcmp(g_app_info_get_id(a), g_app_info_get_id(b));
}
GPtrArray *k230_app_catalog(void) {
  GPtrArray *out = g_ptr_array_new_with_free_func(g_object_unref);
  GList *all = g_app_info_get_all();
  for (GList *it = all; it; it = it->next) {
    GAppInfo *app = it->data;
    if (G_IS_DESKTOP_APP_INFO(app) && g_app_info_get_id(app) &&
        g_app_info_should_show(app)) g_ptr_array_add(out, g_object_ref(app));
  }
  g_list_free_full(all, g_object_unref);
  g_ptr_array_sort(out, compare_apps);
  return out;
}
gboolean k230_app_launch(const char *id, GError **error) {
  GDesktopAppInfo *app = g_desktop_app_info_new(id);
  if (!app || !g_app_info_should_show(G_APP_INFO(app))) {
    g_set_error(error, G_IO_ERROR, G_IO_ERROR_NOT_FOUND, "Application is no longer available: %s", id);
    g_clear_object(&app); return FALSE;
  }
  /* GLib owns Exec expansion, cwd and terminal selection. Our private PATH
   * supplies xdg-terminal-exec, forwarding expanded argv to Foot unchanged. */
  gboolean ok = g_app_info_launch(G_APP_INFO(app), NULL, NULL, error);
  g_object_unref(app); return ok;
}
#ifndef K230_CATALOG_LIBRARY
int main(int argc, char **argv) {
  if (argc == 1 || (argc == 2 && !strcmp(argv[1], "list"))) {
    GPtrArray *apps = k230_app_catalog();
    for (guint i = 0; i < apps->len; i++) {
      GAppInfo *app = g_ptr_array_index(apps, i);
      char *id = g_strescape(g_app_info_get_id(app), NULL);
      char *name = g_strescape(g_app_info_get_display_name(app), NULL);
      printf("%s\t%s\t%d\n", id, name,
        g_desktop_app_info_get_boolean(G_DESKTOP_APP_INFO(app), "Terminal"));
      g_free(id); g_free(name);
    }
    g_ptr_array_unref(apps); return 0;
  }
  if (argc != 3 || strcmp(argv[1], "launch")) {
    fprintf(stderr, "usage: k230-desktop-catalog [list|launch ID]\n"); return 2;
  }
  GError *error = NULL;
  if (k230_app_launch(argv[2], &error)) return 0;
  fprintf(stderr, "launch failed: %s\n", error ? error->message : "unknown error");
  g_clear_error(&error); return 1;
}
#endif
