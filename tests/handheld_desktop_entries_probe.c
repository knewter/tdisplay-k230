// Host GIO catalog check for the packaged desktop override share tree.
// Run with that tree first in XDG_DATA_DIRS, followed by the upstream roots.
#include <gio/gdesktopappinfo.h>
#include <gio/gio.h>
#include <stdio.h>
#include <string.h>

int main(void) {
    const char *ids[] = {
        "foot.desktop", "htop.desktop", "nnn.desktop",
        "footclient.desktop", "foot-server.desktop",
    };
    const char *names[] = {
        "Terminal", "Monitor", "Files", "Foot Client", "Foot Server",
    };
    const char *icons[] = {"foot", "htop", "folder", "foot", "foot"};
    int visible[5] = {0};

    for (int i = 0; i < 5; i++) {
        GDesktopAppInfo *app = g_desktop_app_info_new(ids[i]);
        if (app == NULL) {
            fprintf(stderr, "missing desktop ID: %s\n", ids[i]);
            return 1;
        }
        const char *name = g_app_info_get_display_name(G_APP_INFO(app));
        gboolean shown = g_app_info_should_show(G_APP_INFO(app));
        GIcon *icon = g_app_info_get_icon(G_APP_INFO(app));
        char *icon_name = icon != NULL ? g_icon_to_string(icon) : NULL;
        if (strcmp(name, names[i]) != 0 || shown != (i < 3) ||
            icon_name == NULL || strcmp(icon_name, icons[i]) != 0) {
            fprintf(stderr, "unexpected desktop entry %s: %s shown=%d icon=%s\n",
                    ids[i], name, shown, icon_name != NULL ? icon_name : "(none)");
            return 2;
        }
        printf("%s name=%s shown=%d icon=%s\n", ids[i], name, shown, icon_name);
        g_free(icon_name);
        g_object_unref(app);
    }

    GList *all = g_app_info_get_all();
    for (GList *item = all; item != NULL; item = item->next) {
        GAppInfo *app = G_APP_INFO(item->data);
        const char *id = g_app_info_get_id(app);
        for (int i = 0; i < 5; i++) {
            if (id != NULL && strcmp(id, ids[i]) == 0 &&
                g_app_info_should_show(app)) {
                visible[i]++;
            }
        }
    }
    g_list_free_full(all, g_object_unref);
    for (int i = 0; i < 5; i++) {
        if (visible[i] != (i < 3)) {
            fprintf(stderr, "unexpected visible count for %s: %d\n", ids[i], visible[i]);
            return 3;
        }
    }
    return 0;
}
