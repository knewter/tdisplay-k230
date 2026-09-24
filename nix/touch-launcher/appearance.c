#define _GNU_SOURCE
#include "appearance.h"
#include <errno.h>
#include <fcntl.h>
#include <glib.h>
#include <glib/gstdio.h>
#include <json-glib/json-glib.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <unistd.h>

struct k230_appearance_colors k230_appearance = {
  .background=0xff111827, .foreground=0xfff8fafc,
  .muted=0xffcbd5e1, .tile=0xff243547,
  .selected=0xff24495a, .accent=0xff304f65
};
static const struct k230_appearance_colors defaults = {
  .background=0xff111827, .foreground=0xfff8fafc,
  .muted=0xffcbd5e1, .tile=0xff243547,
  .selected=0xff24495a, .accent=0xff304f65
};
uint32_t k230_appearance_error(void) {
  uint32_t background=k230_appearance.background;
  unsigned brightness=3*((background>>16)&255)+6*((background>>8)&255)+(background&255);
  return brightness>=1280 ? 0xff9f1239 : 0xfffca5a5;
}
static struct k230_appearance_colors candidate, previous;
static char candidate_id[25], previous_id[25], active_id[25];
static bool candidate_prepared;
static int listener=-1, client=-1;
static char socket_path[sizeof(((struct sockaddr_un *)0)->sun_path)];
static char input[4097];
static size_t used;
static gint64 client_deadline;

static const char *member(JsonObject *object, const char *key) {
  if (!object || !json_object_has_member(object,key)) return NULL;
  JsonNode *node=json_object_get_member(object,key);
  return JSON_NODE_HOLDS_VALUE(node) && json_node_get_value_type(node)==G_TYPE_STRING
    ? json_node_get_string(node) : NULL;
}
static bool hex_color(const char *value, uint32_t *color) {
  if (!value || strlen(value)!=7 || value[0]!='#') return false;
  unsigned parsed=0;
  for (int i=1; i<7; i++) {
    char c=value[i];
    if (!g_ascii_isxdigit(c)) return false;
    parsed=(parsed<<4)|(unsigned)(g_ascii_isdigit(c)?c-'0':g_ascii_tolower(c)-'a'+10);
  }
  *color=0xff000000u|parsed;
  return true;
}
static bool valid_id(const char *value) {
  if (!value || strlen(value)!=24) return false;
  for (const char *p=value; *p; p++) if (!g_ascii_isxdigit(*p)) return false;
  return true;
}
static bool read_palette(const char *path, const char *identity,
                         struct k230_appearance_colors *out) {
  if (!path || strlen(path)>1024 || !g_path_is_absolute(path)) return false;
  char *basename=g_path_get_basename(path);
  char *parent=g_path_get_dirname(path);
  char *parent_name=g_path_get_basename(parent);
  bool shaped=!strcmp(basename,identity) && !strcmp(parent_name,"generations");
  g_free(basename); g_free(parent); g_free(parent_name);
  if (!shaped) return false;
  char *filename=g_build_filename(path,"report.json",NULL);
  GStatBuf metadata;
  bool safe=g_stat(filename,&metadata)==0 && S_ISREG(metadata.st_mode)
    && metadata.st_size>0 && metadata.st_size<=65536;
  gchar *data=NULL; gsize length=0;
  if (safe) safe=g_file_get_contents(filename,&data,&length,NULL) && length<=65536;
  g_free(filename);
  if (!safe) { g_free(data); return false; }
  JsonParser *parser=json_parser_new();
  safe=json_parser_load_from_data(parser,data,(gssize)length,NULL);
  g_free(data);
  if (safe) {
    JsonNode *root=json_parser_get_root(parser);
    safe=JSON_NODE_HOLDS_OBJECT(root);
    if (safe) {
      JsonObject *report=json_node_get_object(root);
      JsonObject *palette=json_object_get_object_member(report,"palette");
      const char *reported=member(report,"generation");
      safe=reported && !strcmp(reported,identity) && palette
        && hex_color(member(palette,"background"),&out->background)
        && hex_color(member(palette,"foreground"),&out->foreground);
      if (safe) {
        out->muted=out->foreground;
        out->tile=out->background;
        out->selected=out->background;
        out->accent=out->foreground;
        /* Pinned light/dark muted swatches fall below 4.5:1 on this panel's
         * small hint text; retain the authored value in report.json while
         * the launcher uses foreground until the full role adapter lands. */
        (void)hex_color(member(palette,"dark_background"),&out->tile);
        (void)hex_color(member(palette,"lighter_background"),&out->selected);
        (void)hex_color(member(palette,"accent"),&out->accent);
      }
    }
  }
  g_object_unref(parser);
  return safe;
}
static void load_startup_palette(const char *state_root, const char *default_generation) {
  if (default_generation) {
    char *identity=g_path_get_basename(default_generation);
    struct k230_appearance_colors colors=defaults;
    if (valid_id(identity) && read_palette(default_generation,identity,&colors)) {
      k230_appearance=colors;
      strcpy(active_id,identity);
    } else fprintf(stderr,"k230-touch-launcher: pinned default theme unavailable\n");
    g_free(identity);
  }
  if (!state_root) return;
  char *pointer=g_build_filename(state_root,"active",NULL);
  bool selected=g_file_test(pointer,G_FILE_TEST_IS_SYMLINK);
  char *target=selected ? realpath(pointer,NULL) : NULL;
  char *cache=g_build_filename(state_root,"generations",NULL);
  char *cache_real=realpath(cache,NULL);
  if (selected) {
    char *identity=target ? g_path_get_basename(target) : NULL;
    struct k230_appearance_colors colors=defaults;
    size_t length=cache_real ? strlen(cache_real) : 0;
    bool safe=target && cache_real && !strncmp(target,cache_real,length)
      && target[length]=='/' && valid_id(identity)
      && read_palette(target,identity,&colors);
    if (safe) { k230_appearance=colors; strcpy(active_id,identity); }
    else fprintf(stderr,"k230-touch-launcher: cached theme unavailable; using pinned default\n");
    g_free(identity);
  }
  free(target); free(cache_real); g_free(cache); g_free(pointer);
}
static void close_client(void) {
  if (client>=0) close(client);
  client=-1; used=0; client_deadline=0;
}
static void reply(const char *phase, const char *identity, bool ok) {
  char response[192];
  int length=snprintf(response,sizeof response,
    "{\"protocol\":1,\"phase\":\"%s\",\"generation\":%s,\"status\":\"%s\"}\n",
    phase, identity ? "\"\"" : "null", ok ? "ok" : "error");
  if (identity && length>0 && (size_t)length<sizeof response) {
    length=snprintf(response,sizeof response,
      "{\"protocol\":1,\"phase\":\"%s\",\"generation\":\"%s\",\"status\":\"%s\"}\n",
      phase,identity,ok?"ok":"error");
  }
  if (length>0 && (size_t)length<sizeof response) (void)send(client,response,(size_t)length,MSG_NOSIGNAL);
  close_client();
}
static void handle(bool (*redraw)(void)) {
  JsonParser *parser=json_parser_new();
  bool parsed=json_parser_load_from_data(parser,input,(gssize)used,NULL)
    && JSON_NODE_HOLDS_OBJECT(json_parser_get_root(parser));
  if (!parsed) { g_object_unref(parser); close_client(); return; }
  JsonObject *request=json_node_get_object(json_parser_get_root(parser));
  const char *phase=member(request,"phase");
  const char *id=member(request,"generation");
  const char *path=member(request,"path");
  const char *old_id=member(request,"previous_generation");
  const char *old_path=member(request,"previous_path");
  bool null_id=json_object_has_member(request,"generation")
    && JSON_NODE_HOLDS_NULL(json_object_get_member(request,"generation"));
  bool ok=false;
  if (json_object_has_member(request,"protocol")
      && json_object_get_int_member(request,"protocol")==1 && phase) {
    if (!strcmp(phase,"prepare") && valid_id(id)) {
      candidate_prepared=false;
      struct k230_appearance_colors colors=defaults;
      ok=read_palette(path,id,&colors);
      if (ok) {
        struct k230_appearance_colors former=k230_appearance;
        if (old_id || old_path) {
          ok=valid_id(old_id) && read_palette(old_path,old_id,&former);
          if (ok) strcpy(previous_id,old_id);
        } else previous_id[0]=0;
        if (ok) {
          candidate=colors; strcpy(candidate_id,id);
          previous=former;
          candidate_prepared=true;
        }
      }
    } else if (!strcmp(phase,"commit") && valid_id(id)
               && candidate_prepared && !strcmp(candidate_id,id)) {
      struct k230_appearance_colors former=k230_appearance;
      k230_appearance=candidate;
      ok=redraw();
      if (ok) strcpy(active_id,id);
      else k230_appearance=former;
    } else if (!strcmp(phase,"rollback")
               && candidate_prepared
               && ((valid_id(id) && !strcmp(id,previous_id))
                   || (null_id && !previous_id[0]))) {
      struct k230_appearance_colors former=k230_appearance;
      k230_appearance=previous;
      ok=redraw();
      if (ok) strcpy(active_id,previous_id);
      else k230_appearance=former;
    }
  }
  if (phase && (!strcmp(phase,"prepare") || !strcmp(phase,"commit")
                || !strcmp(phase,"rollback"))) reply(phase,id,ok);
  else close_client();
  g_object_unref(parser);
}
int k230_appearance_start(const char *runtime, const char *state_root,
                          const char *default_generation) {
  if (!runtime) return -1;
  load_startup_palette(state_root,default_generation);
  int length=snprintf(socket_path,sizeof socket_path,"%s/appearance.sock",runtime);
  if (length<=0 || (size_t)length>=sizeof socket_path) return -1;
  listener=socket(AF_UNIX,SOCK_STREAM|SOCK_NONBLOCK|SOCK_CLOEXEC,0);
  if (listener<0) return -1;
  struct sockaddr_un address={.sun_family=AF_UNIX};
  strcpy(address.sun_path,socket_path);
  unlink(socket_path); /* Singleton launcher lock is already held. */
  mode_t old=umask(0077);
  int result=bind(listener,(struct sockaddr *)&address,sizeof address);
  umask(old);
  if (result || chmod(socket_path,0600) || listen(listener,1)) {
    k230_appearance_stop(); return -1;
  }
  return 0;
}
int k230_appearance_listener_fd(void) { return listener; }
int k230_appearance_client_fd(void) { return client; }
void k230_appearance_service(bool listener_ready, bool client_ready,
                             bool (*redraw)(void)) {
  if (client>=0 && g_get_monotonic_time()>client_deadline) close_client();
  if (listener_ready && client<0) {
    client=accept4(listener,NULL,NULL,SOCK_NONBLOCK|SOCK_CLOEXEC);
    if (client>=0) {
      struct ucred peer; socklen_t length=sizeof peer;
      if (getsockopt(client,SOL_SOCKET,SO_PEERCRED,&peer,&length)<0
          || length!=sizeof peer || peer.uid!=geteuid()) close_client();
      else { used=0; client_deadline=g_get_monotonic_time()+2000000; }
    }
  }
  if (client_ready && client>=0) {
    ssize_t amount=recv(client,input+used,sizeof input-used-1,0);
    if (amount<=0) { close_client(); return; }
    used+=(size_t)amount;
    if (used>=sizeof input-1) { close_client(); return; }
    input[used]=0;
    char *end=memchr(input,'\n',used);
    if (end) { used=(size_t)(end-input); input[used]=0; handle(redraw); }
  }
}
void k230_appearance_stop(void) {
  close_client();
  if (listener>=0) close(listener);
  listener=-1;
  if (socket_path[0]) unlink(socket_path);
}
