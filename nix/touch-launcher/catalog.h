#pragma once
#include <gio/gdesktopappinfo.h>
#include <gio/gio.h>

/* Curated placement for a discovered desktop entry.  GLib still owns
 * discovery, visibility rules and launch; this only decides what the Apps
 * page says about an entry and where (or whether) it appears. */
enum k230_app_placement { K230_APP_SHOW, K230_APP_DEMOTE, K230_APP_HIDE };

GPtrArray *k230_app_catalog(void);
gboolean k230_app_launch(const char *id, GError **error);
enum k230_app_placement k230_app_placement(GAppInfo *app);
/* Person-facing action name and one-line description.  Never NULL. */
const char *k230_app_label(GAppInfo *app);
const char *k230_app_hint(GAppInfo *app);
/* Short launch-failure copy naming the action and the Back route.  Raw GLib
 * messages (which can carry filesystem paths) belong in logs only. */
char *k230_app_failure_copy(const char *label);
