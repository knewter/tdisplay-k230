#include "catalog.h"
#include <stdio.h>
#include <string.h>

/* Known implementation endpoints and duplicated built-ins.  The built-in
 * Terminal, Monitor, New terminal and Help rows stay first on page one; these
 * entries either duplicate them or are not an independent person-facing task.
 * Unknown entries are always retained under their own name. */
static const struct {
  const char *id, *label, *hint;
  enum k230_app_placement placement;
} policy[] = {
  {"footclient.desktop", "Foot Client", "Connects to a running terminal server", K230_APP_HIDE},
  {"foot-server.desktop", "Foot Server", "Background terminal server", K230_APP_HIDE},
  {"foot.desktop", "Plain terminal", "A terminal without the shell's theme", K230_APP_DEMOTE},
  {"htop.desktop", "Process viewer", "The same htop view as Monitor", K230_APP_DEMOTE},
};

static int policy_index(GAppInfo *app) {
  const char *id = app ? g_app_info_get_id(app) : NULL;
  if (!id) return -1;
  for (guint i = 0; i < G_N_ELEMENTS(policy); i++)
    if (!strcmp(policy[i].id, id)) return (int)i;
  return -1;
}
enum k230_app_placement k230_app_placement(GAppInfo *app) {
  int i = policy_index(app);
  return i < 0 ? K230_APP_SHOW : policy[i].placement;
}
const char *k230_app_label(GAppInfo *app) {
  int i = policy_index(app);
  if (i >= 0) return policy[i].label;
  const char *name = app ? g_app_info_get_display_name(app) : NULL;
  return name && *name ? name : "Application";
}
const char *k230_app_hint(GAppInfo *app) {
  int i = policy_index(app);
  if (i >= 0) return policy[i].hint;
  const char *comment = app ? g_app_info_get_description(app) : NULL;
  if (comment && *comment) return comment;
  if (app && G_IS_DESKTOP_APP_INFO(app)) {
    const char *generic = g_desktop_app_info_get_generic_name(G_DESKTOP_APP_INFO(app));
    if (generic && *generic) return generic;
  }
  return "Installed application";
}
char *k230_app_failure_copy(const char *label) {
  return g_strdup_printf("Could not open %s · Back returns to Apps",
                         label && *label ? label : "the application");
}

static gint compare_apps(gconstpointer left, gconstpointer right) {
  GAppInfo *a = *(GAppInfo * const *)left, *b = *(GAppInfo * const *)right;
  /* Ordinary entries first, then demoted duplicates, each by curated label. */
  int placement = (int)k230_app_placement(a) - (int)k230_app_placement(b);
  if (placement) return placement;
  int result = g_utf8_collate(k230_app_label(a), k230_app_label(b));
  return result ? result : strcmp(g_app_info_get_id(a), g_app_info_get_id(b));
}
GPtrArray *k230_app_catalog(void) {
  GPtrArray *out = g_ptr_array_new_with_free_func(g_object_unref);
  GList *all = g_app_info_get_all();
  for (GList *it = all; it; it = it->next) {
    GAppInfo *app = it->data;
    if (G_IS_DESKTOP_APP_INFO(app) && g_app_info_get_id(app) &&
        g_app_info_should_show(app) && k230_app_placement(app) != K230_APP_HIDE)
      g_ptr_array_add(out, g_object_ref(app));
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
  gboolean describe = argc == 2 && !strcmp(argv[1], "describe");
  if (argc == 1 || describe || (argc == 2 && !strcmp(argv[1], "list"))) {
    GPtrArray *apps = k230_app_catalog();
    for (guint i = 0; i < apps->len; i++) {
      GAppInfo *app = g_ptr_array_index(apps, i);
      char *id = g_strescape(g_app_info_get_id(app), NULL);
      char *name = g_strescape(k230_app_label(app), NULL);
      if (describe) {
        char *hint = g_strescape(k230_app_hint(app), NULL);
        printf("%s\t%s\t%s\t%s\n", id, name, hint,
          k230_app_placement(app) == K230_APP_DEMOTE ? "demoted" : "shown");
        g_free(hint);
      } else printf("%s\t%s\t%d\n", id, name,
        g_desktop_app_info_get_boolean(G_DESKTOP_APP_INFO(app), "Terminal"));
      g_free(id); g_free(name);
    }
    g_ptr_array_unref(apps); return 0;
  }
  if (argc != 3 || strcmp(argv[1], "launch")) {
    fprintf(stderr, "usage: k230-desktop-catalog [list|describe|launch ID]\n"); return 2;
  }
  GError *error = NULL;
  if (k230_app_launch(argv[2], &error)) return 0;
  /* Person-facing copy on stdout; the raw diagnostic stays on stderr. */
  GDesktopAppInfo *known = g_desktop_app_info_new(argv[2]);
  char *copy = k230_app_failure_copy(known ? k230_app_label(G_APP_INFO(known)) : NULL);
  printf("%s\n", copy);
  fprintf(stderr, "launch failed: %s\n", error ? error->message : "unknown error");
  g_free(copy); g_clear_object(&known); g_clear_error(&error); return 1;
}
#endif
