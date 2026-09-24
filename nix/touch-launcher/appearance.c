#define _GNU_SOURCE
#include "appearance.h"
#include <errno.h>
#include <fcntl.h>
#include <glib.h>
#include <glib/gstdio.h>
#include <json-glib/json-glib.h>
#include <math.h>
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
static JsonParser *active_tokens, *candidate_tokens, *previous_tokens;
static char *active_path, *candidate_path, *previous_path;
static char *background_path;
static uint64_t generation_serial;
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
static JsonParser *read_tokens(const char *path, const char *identity) {
  if (!path || strlen(path)>1024) return NULL;
  char *filename=g_build_filename(path,"appearance.json",NULL);
  GStatBuf metadata;
  bool safe=g_stat(filename,&metadata)==0 && S_ISREG(metadata.st_mode)
    && metadata.st_size>0 && metadata.st_size<=256*1024;
  gchar *data=NULL; gsize length=0;
  if (safe) safe=g_file_get_contents(filename,&data,&length,NULL) && length<=256*1024;
  g_free(filename);
  if (!safe) { g_free(data); return NULL; }
  JsonParser *parser=json_parser_new();
  safe=json_parser_load_from_data(parser,data,(gssize)length,NULL);
  g_free(data);
  if (safe) {
    JsonNode *root=json_parser_get_root(parser);
    safe=JSON_NODE_HOLDS_OBJECT(root);
    if (safe) {
      JsonObject *object=json_node_get_object(root);
      safe=member(object,"generation") && !strcmp(member(object,"generation"),identity)
        && json_object_has_member(object,"version")
        && json_object_get_int_member(object,"version")==1
        && json_object_has_member(object,"sections")
        && JSON_NODE_HOLDS_OBJECT(json_object_get_member(object,"sections"));
    }
  }
  if (!safe) { g_object_unref(parser); return NULL; }
  return parser;
}
static void set_active_tokens(JsonParser *parser, const char *path) {
  if (active_tokens) g_object_unref(active_tokens);
  active_tokens=parser ? g_object_ref(parser) : NULL;
  g_free(active_path);
  active_path=path ? g_strdup(path) : NULL;
  g_free(background_path); background_path=NULL;
  if (active_tokens && active_path) {
    JsonObject *root=json_node_get_object(json_parser_get_root(active_tokens));
    if (g_strcmp0(member(root,"background"),"background")==0) {
      char *candidate_file=g_build_filename(active_path,"background",NULL);
      char *resolved=realpath(candidate_file,NULL);
      char *asset_root=g_build_filename(active_path,"theme","backgrounds",NULL);
      char *canonical_root=realpath(asset_root,NULL);
      GStatBuf metadata;
      size_t count=canonical_root ? strlen(canonical_root) : 0;
      if (resolved && canonical_root && !strncmp(resolved,canonical_root,count)
          && resolved[count]=='/' && g_stat(resolved,&metadata)==0
          && S_ISREG(metadata.st_mode) && metadata.st_size>0
          && metadata.st_size<=256*1024*1024) background_path=g_strdup(candidate_file);
      free(resolved); free(canonical_root); g_free(asset_root); g_free(candidate_file);
    }
  }
  generation_serial++;
}
static JsonObject *token(const char *section, const char *key) {
  if (!active_tokens || !section || !key) return NULL;
  JsonObject *root=json_node_get_object(json_parser_get_root(active_tokens));
  JsonObject *sections=json_object_get_object_member(root,"sections");
  if (!sections || !json_object_has_member(sections,section)) return NULL;
  JsonObject *group=json_object_get_object_member(sections,section);
  if (!group || !json_object_has_member(group,key)) return NULL;
  JsonNode *node=json_object_get_member(group,key);
  return JSON_NODE_HOLDS_OBJECT(node) ? json_node_get_object(node) : NULL;
}
static bool argb_value(const char *value, uint32_t *out) {
  if (!value || strlen(value)!=9 || value[0]!='#') return false;
  uint32_t parsed=0;
  for (int i=1; i<9; i++) {
    char c=value[i];
    if (!g_ascii_isxdigit(c)) return false;
    parsed=(parsed<<4)|(uint32_t)(g_ascii_isdigit(c)?c-'0':g_ascii_tolower(c)-'a'+10);
  }
  *out=parsed; return true;
}
bool k230_appearance_brush(const char *section, const char *key,
                           struct k230_appearance_brush *out) {
  JsonObject *field=token(section,key);
  if (!out || !field || g_strcmp0(member(field,"kind"),"brush")) return false;
  JsonArray *stops=json_object_get_array_member(field,"stops");
  guint count=stops ? json_array_get_length(stops) : 0;
  if (count<1 || count>K230_APPEARANCE_MAX_STOPS) return false;
  struct k230_appearance_brush result={0};
  result.stop_count=count;
  result.alpha=json_object_get_double_member(field,"alpha");
  result.angle_degrees=json_object_get_double_member(field,"angle_degrees");
  if (!isfinite(result.alpha) || result.alpha<0 || result.alpha>1
      || !isfinite(result.angle_degrees) || fabs(result.angle_degrees)>3600) return false;
  for (guint i=0; i<count; i++) {
    JsonObject *stop=json_array_get_object_element(stops,i);
    if (!stop || !argb_value(member(stop,"argb"),&result.stops[i].argb)) return false;
    result.stops[i].offset=json_object_get_double_member(stop,"offset");
    if (!isfinite(result.stops[i].offset) || result.stops[i].offset<0
        || result.stops[i].offset>1) return false;
  }
  *out=result; return true;
}
bool k230_appearance_number(const char *section, const char *key, double *out) {
  JsonObject *field=token(section,key);
  if (!out || !field || g_strcmp0(member(field,"kind"),"number")) return false;
  double value=json_object_get_double_member(field,"value");
  if (!isfinite(value) || fabs(value)>10000) return false;
  *out=value; return true;
}
bool k230_appearance_border(const char *section, const char *key,
                            struct k230_appearance_border *out) {
  if (!out || !k230_appearance_brush(section,key,&out->brush)) return false;
  for (int i=0; i<4; i++) out->width[i]=1.0;
  char *width_key=g_strconcat(key,"-width",NULL);
  JsonObject *width=token(section,width_key);
  if (width && g_strcmp0(member(width,"kind"),"width")==0) {
    JsonArray *values=json_object_get_array_member(width,"value");
    if (!values || json_array_get_length(values)!=4) { g_free(width_key); return false; }
    for (int i=0; i<4; i++) {
      out->width[i]=json_array_get_double_element(values,i);
      if (!isfinite(out->width[i]) || out->width[i]<0 || out->width[i]>128) {
        g_free(width_key); return false;
      }
    }
  }
  const char *sides[]={"top","right","bottom","left"};
  for (int i=0; i<4; i++) {
    char *side_key=g_strconcat(width_key,"-",sides[i],NULL);
    double override=0;
    if (k230_appearance_number(section,side_key,&override)) out->width[i]=override;
    g_free(side_key);
  }
  g_free(width_key); return true;
}
const char *k230_appearance_icon_theme(void) {
  if (!active_tokens) return NULL;
  JsonObject *root=json_node_get_object(json_parser_get_root(active_tokens));
  const char *name=member(root,"icon_theme");
  if (!name || strlen(name)>160 || !g_ascii_isalnum(name[0])) return NULL;
  for (const char *p=name; *p; p++)
    if (!g_ascii_isalnum(*p) && *p!='_' && *p!='-' && *p!='.' && *p!='+') return NULL;
  return name;
}
const char *k230_appearance_background_path(void) { return background_path; }
uint64_t k230_appearance_generation_serial(void) { return generation_serial; }
static void load_startup_palette(const char *state_root, const char *default_generation) {
  if (default_generation) {
    char *identity=g_path_get_basename(default_generation);
    struct k230_appearance_colors colors=defaults;
    JsonParser *tokens=valid_id(identity) ? read_tokens(default_generation,identity) : NULL;
    if (tokens && read_palette(default_generation,identity,&colors)) {
      k230_appearance=colors;
      strcpy(active_id,identity);
      set_active_tokens(tokens,default_generation);
    } else fprintf(stderr,"k230-touch-launcher: pinned default theme unavailable\n");
    if (tokens) g_object_unref(tokens);
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
    JsonParser *tokens=target && valid_id(identity) ? read_tokens(target,identity) : NULL;
    bool safe=target && cache_real && !strncmp(target,cache_real,length)
      && target[length]=='/' && valid_id(identity)
      && tokens && read_palette(target,identity,&colors);
    if (safe) {
      k230_appearance=colors; strcpy(active_id,identity);
      set_active_tokens(tokens,target);
    }
    else fprintf(stderr,"k230-touch-launcher: cached theme unavailable; using pinned default\n");
    if (tokens) g_object_unref(tokens);
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
        JsonParser *next=read_tokens(path,id);
        if (!next) ok=false;
        struct k230_appearance_colors former=k230_appearance;
        if (ok && (old_id || old_path)) {
          ok=valid_id(old_id) && read_palette(old_path,old_id,&former);
          if (ok) strcpy(previous_id,old_id);
        } else if (ok) previous_id[0]=0;
        JsonParser *old_tokens=(ok && old_id && old_path)
          ? read_tokens(old_path,old_id) : NULL;
        if (ok && old_id && old_path && !old_tokens) ok=false;
        if (ok) {
          candidate=colors; strcpy(candidate_id,id);
          previous=former;
          if (candidate_tokens) g_object_unref(candidate_tokens);
          candidate_tokens=next;
          g_free(candidate_path); candidate_path=g_strdup(path);
          if (previous_tokens) g_object_unref(previous_tokens);
          previous_tokens=(old_id && old_path) ? old_tokens
            : (active_tokens ? g_object_ref(active_tokens) : NULL);
          g_free(previous_path);
          previous_path=(old_id && old_path) ? g_strdup(old_path)
            : (active_path ? g_strdup(active_path) : NULL);
          candidate_prepared=true;
        } else {
          if (next) g_object_unref(next);
          if (old_tokens) g_object_unref(old_tokens);
        }
      }
    } else if (!strcmp(phase,"commit") && valid_id(id)
               && candidate_prepared && !strcmp(candidate_id,id)) {
      struct k230_appearance_colors former=k230_appearance;
      JsonParser *former_tokens=active_tokens ? g_object_ref(active_tokens) : NULL;
      char *former_path=g_strdup(active_path);
      k230_appearance=candidate;
      set_active_tokens(candidate_tokens,candidate_path);
      ok=redraw();
      if (ok) strcpy(active_id,id);
      else { k230_appearance=former; set_active_tokens(former_tokens,former_path); }
      if (former_tokens) g_object_unref(former_tokens);
      g_free(former_path);
    } else if (!strcmp(phase,"rollback")
               && candidate_prepared
               && ((valid_id(id) && !strcmp(id,previous_id))
                   || (null_id && !previous_id[0]))) {
      struct k230_appearance_colors former=k230_appearance;
      JsonParser *former_tokens=active_tokens ? g_object_ref(active_tokens) : NULL;
      char *former_path=g_strdup(active_path);
      k230_appearance=previous;
      set_active_tokens(previous_tokens,previous_path);
      ok=redraw();
      if (ok) strcpy(active_id,previous_id);
      else { k230_appearance=former; set_active_tokens(former_tokens,former_path); }
      if (former_tokens) g_object_unref(former_tokens);
      g_free(former_path);
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
  if (active_tokens) g_object_unref(active_tokens);
  if (candidate_tokens) g_object_unref(candidate_tokens);
  if (previous_tokens) g_object_unref(previous_tokens);
  active_tokens=candidate_tokens=previous_tokens=NULL;
  g_clear_pointer(&active_path,g_free);
  g_clear_pointer(&candidate_path,g_free);
  g_clear_pointer(&previous_path,g_free);
  g_clear_pointer(&background_path,g_free);
}
