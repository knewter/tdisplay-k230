#pragma once
#include <gio/gdesktopappinfo.h>
#include <gio/gio.h>
GPtrArray *k230_app_catalog(void);
gboolean k230_app_launch(const char *id, GError **error);
