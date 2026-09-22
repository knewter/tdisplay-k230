#include <gio/gdesktopappinfo.h>
#include <gio/gio.h>
#include <stdio.h>
#include <string.h>
/* GDesktopAppInfo owns XDG precedence, Hidden/NoDisplay/TryExec and Exec
 * quoting/field-code parsing. Never pass Exec through a shell. */
static GDesktopAppInfo *find_id(const char *id) {
  GList *all=g_app_info_get_all(); GDesktopAppInfo *hit=NULL;
  for(GList*l=all;l;l=l->next) { GAppInfo *a=l->data;
    if(G_IS_DESKTOP_APP_INFO(a) && g_app_info_should_show(a) && !strcmp(g_app_info_get_id(a),id)) { hit=G_DESKTOP_APP_INFO(g_object_ref(a)); break; }
  } g_list_free_full(all,g_object_unref); return hit;
}
int main(int argc,char**argv) {
 if(argc==1 || (argc==2 && !strcmp(argv[1],"list"))) { GList*all=g_app_info_get_all();
  for(GList*l=all;l;l=l->next){GAppInfo*a=l->data; if(G_IS_DESKTOP_APP_INFO(a)&&g_app_info_should_show(a)) printf("%s\t%s\t%d\n",g_app_info_get_id(a),g_app_info_get_display_name(a),g_desktop_app_info_get_boolean(G_DESKTOP_APP_INFO(a),"Terminal"));}
  g_list_free_full(all,g_object_unref); return 0; }
 if(argc!=3||strcmp(argv[1],"launch")){fprintf(stderr,"usage: k230-desktop-catalog [list|launch ID]\n");return 2;}
 GDesktopAppInfo*a=find_id(argv[2]); if(!a){fprintf(stderr,"desktop entry unavailable: %s\n",argv[2]);return 1;}
 GError*e=NULL; gboolean ok;
 if(g_desktop_app_info_get_boolean(a,"Terminal")){ const char*foot=g_getenv("K230_FOOT"); if(!foot){fprintf(stderr,"Terminal entry needs K230_FOOT\n");g_object_unref(a);return 1;} char *cmd=g_strdup_printf("%s --config %s -e %s",foot,g_getenv("K230_TERMINAL_CONFIG"),g_app_info_get_commandline(G_APP_INFO(a))); ok=g_spawn_command_line_async(cmd,&e);g_free(cmd); }
 else ok=g_app_info_launch(G_APP_INFO(a),NULL,NULL,&e);
 if(!ok){fprintf(stderr,"launch failed: %s\n",e?e->message:"unknown");g_clear_error(&e);} g_object_unref(a);return ok?0:1;
}
