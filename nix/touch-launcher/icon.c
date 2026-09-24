#define _POSIX_C_SOURCE 200809L
#include "icon.h"
#include <librsvg/rsvg.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

#define ICON_CACHE_LIMIT 12
#define ICON_FILE_LIMIT (512 * 1024)
#define THEME_DIRECTORY_LIMIT 128
#define THEME_DEPTH_LIMIT 4

struct icon_entry {
  char *key, *path;
  cairo_surface_t *surface;
  time_t mtime;
  off_t bytes;
  ino_t inode;
  guint64 touched;
};
static GPtrArray *cache;
static char *environment_key;
static guint64 touch_clock;
static guint decode_count;

static void free_entry(gpointer value) {
  struct icon_entry *entry = value;
  g_free(entry->key);
  g_free(entry->path);
  if (entry->surface) cairo_surface_destroy(entry->surface);
  g_free(entry);
}
void k230_icon_cache_invalidate(void) {
  if (cache) g_ptr_array_set_size(cache, 0);
}
guint k230_icon_cache_count(void) { return cache ? cache->len : 0; }
guint k230_icon_decode_count(void) { return decode_count; }

static int icon_size(enum k230_icon_use use) {
  return use == K230_ICON_DRAWER ? 48 :
    use == K230_ICON_NOTIFICATION || use == K230_ICON_PRIVATE_NOTIFICATION ? 24 : 32;
}
static gboolean private_use(enum k230_icon_use use) {
  return use == K230_ICON_PRIVATE_CARD || use == K230_ICON_PRIVATE_NOTIFICATION;
}
static gboolean safe_component(const char *name) {
  if (!name || !*name || strlen(name) > 160) return FALSE;
  for (const unsigned char *p = (const unsigned char *)name; *p; p++)
    if (!g_ascii_isalnum(*p) && *p != '_' && *p != '-' && *p != '.' && *p != '+') return FALSE;
  return strcmp(name, ".") && strcmp(name, "..");
}
static gboolean usable_file(const char *path, struct stat *st) {
  return path && stat(path, st) == 0 && S_ISREG(st->st_mode) &&
    st->st_size > 0 && st->st_size <= ICON_FILE_LIMIT;
}
static char *try_icon_in(const char *directory, const char *name) {
  for (int i = 0; i < 2; i++) {
    char *filename = g_strconcat(name, i == 0 ? ".png" : ".svg", NULL);
    char *path = g_build_filename(directory, filename, NULL);
    struct stat st;
    g_free(filename);
    if (usable_file(path, &st)) return path;
    g_free(path);
  }
  return NULL;
}
static GPtrArray *data_roots(void) {
  GPtrArray *roots = g_ptr_array_new_with_free_func(g_free);
  const char *home = g_getenv("XDG_DATA_HOME");
  if (home && g_path_is_absolute(home)) g_ptr_array_add(roots, g_strdup(home));
  else g_ptr_array_add(roots, g_build_filename(g_get_home_dir(), ".local", "share", NULL));
  const char *system = g_getenv("XDG_DATA_DIRS");
  if (!system || !*system) system = "/usr/local/share:/usr/share";
  char **dirs = g_strsplit(system, ":", 17);
  for (int i = 0; dirs[i] && i < 16; i++)
    if (g_path_is_absolute(dirs[i])) g_ptr_array_add(roots, g_strdup(dirs[i]));
  g_strfreev(dirs);
  return roots;
}
static int directory_score(GKeyFile *index, const char *directory, int wanted) {
  int size = g_key_file_get_integer(index, directory, "Size", NULL);
  int scale = g_key_file_get_integer(index, directory, "Scale", NULL);
  if (scale < 1) scale = 1;
  char *type = g_key_file_get_string(index, directory, "Type", NULL);
  int score = 1000;
  if (size > 0) {
    if (g_strcmp0(type, "Scalable") == 0) {
      int min = g_key_file_get_integer(index, directory, "MinSize", NULL);
      int max = g_key_file_get_integer(index, directory, "MaxSize", NULL);
      if (!min) min = size;
      if (!max) max = size;
      score = wanted < min * scale ? min * scale - wanted :
        wanted > max * scale ? wanted - max * scale : 0;
    } else score = abs(size * scale - wanted);
  }
  g_free(type);
  return score;
}
static char *search_one_theme_root(const char *root, const char *theme,
                                    const char *name, int wanted,
                                    char ***inherits_out) {
  char *theme_dir = g_build_filename(root, "icons", theme, NULL);
  char *index_path = g_build_filename(theme_dir, "index.theme", NULL);
  GKeyFile *index = g_key_file_new();
  gboolean has_index = g_key_file_load_from_file(index, index_path, G_KEY_FILE_NONE, NULL);
  char *best = NULL;
  int best_score = G_MAXINT;
  if (has_index) {
    if (inherits_out && !*inherits_out)
      *inherits_out = g_key_file_get_string_list(index, "Icon Theme", "Inherits", NULL, NULL);
    gsize count = 0;
    char **dirs = g_key_file_get_string_list(index, "Icon Theme", "Directories", &count, NULL);
    for (gsize i = 0; dirs && i < count && i < THEME_DIRECTORY_LIMIT; i++) {
      if (!dirs[i] || strstr(dirs[i], "..") || dirs[i][0] == '/') continue;
      char *directory = g_build_filename(theme_dir, dirs[i], NULL);
      char *path = try_icon_in(directory, name);
      int score = directory_score(index, dirs[i], wanted);
      if (path && score < best_score) { g_free(best); best = path; best_score = score; }
      else g_free(path);
      g_free(directory);
    }
    g_strfreev(dirs);
  }
  if (!best) {
    char *sizes[] = { g_strdup_printf("%dx%d", wanted, wanted), "48x48", "64x64",
      "32x32", "24x24", "128x128", "256x256", "scalable", "16x16" };
    for (guint i = 0; i < G_N_ELEMENTS(sizes) && !best; i++) {
      char *directory = g_build_filename(theme_dir, sizes[i], "apps", NULL);
      best = try_icon_in(directory, name);
      g_free(directory);
    }
    g_free(sizes[0]);
  }
  g_key_file_unref(index);
  g_free(index_path);
  g_free(theme_dir);
  return best;
}
static char *search_theme(GPtrArray *roots, const char *theme, const char *name,
                          int wanted, int depth) {
  if (depth >= THEME_DEPTH_LIMIT || !safe_component(theme)) return NULL;
  char **inherits = NULL;
  for (guint i = 0; i < roots->len; i++) {
    char *path = search_one_theme_root(g_ptr_array_index(roots, i), theme,
                                       name, wanted, &inherits);
    if (path) { g_strfreev(inherits); return path; }
  }
  for (int i = 0; inherits && inherits[i] && i < 8; i++) {
    if (!strcmp(inherits[i], theme)) continue;
    char *path = search_theme(roots, inherits[i], name, wanted, depth + 1);
    if (path) { g_strfreev(inherits); return path; }
  }
  g_strfreev(inherits);
  return NULL;
}
static char *resolve_icon(GIcon *icon, int size) {
  if (G_IS_FILE_ICON(icon)) {
    GFile *file = g_file_icon_get_file(G_FILE_ICON(icon));
    char *path = g_file_get_path(file);
    struct stat st;
    if (path && g_path_is_absolute(path) && usable_file(path, &st)) return path;
    g_free(path);
    return NULL;
  }
  if (!G_IS_THEMED_ICON(icon)) return NULL;
  GPtrArray *roots = data_roots();
  const char *theme = g_getenv("K230_ICON_THEME");
  if (!safe_component(theme)) theme = "hicolor";
  char *path = NULL;
  const char * const *names = g_themed_icon_get_names(G_THEMED_ICON(icon));
  for (int i = 0; names && names[i] && i < 16 && !path; i++) {
    if (!safe_component(names[i])) continue;
    path = search_theme(roots, theme, names[i], size, 0);
    if (!path && strcmp(theme, "hicolor"))
      path = search_theme(roots, "hicolor", names[i], size, 0);
    for (guint j = 0; j < roots->len && !path; j++) {
      char *pixmaps = g_build_filename(g_ptr_array_index(roots, j), "pixmaps", NULL);
      path = try_icon_in(pixmaps, names[i]);
      g_free(pixmaps);
    }
  }
  g_ptr_array_unref(roots);
  return path;
}
static cairo_surface_t *decode_icon(const char *path, int size) {
  cairo_surface_t *out = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, size, size);
  if (cairo_surface_status(out) != CAIRO_STATUS_SUCCESS) { cairo_surface_destroy(out); return NULL; }
  cairo_t *cr = cairo_create(out);
  gboolean ok = FALSE;
  if (g_str_has_suffix(path, ".svg")) {
    GError *error = NULL;
    RsvgHandle *handle = rsvg_handle_new_from_file(path, &error);
    if (handle) {
      RsvgRectangle viewport = { 0, 0, size, size };
      ok = rsvg_handle_render_document(handle, cr, &viewport, &error);
      g_object_unref(handle);
    }
    g_clear_error(&error);
  } else if (g_str_has_suffix(path, ".png")) {
    cairo_surface_t *source = cairo_image_surface_create_from_png(path);
    if (cairo_surface_status(source) == CAIRO_STATUS_SUCCESS) {
      int w = cairo_image_surface_get_width(source), h = cairo_image_surface_get_height(source);
      if (w > 0 && h > 0 && w <= 4096 && h <= 4096) {
        double scale = fmin((double)size / w, (double)size / h);
        cairo_translate(cr, (size - w * scale) / 2, (size - h * scale) / 2);
        cairo_scale(cr, scale, scale);
        cairo_set_source_surface(cr, source, 0, 0);
        cairo_paint(cr);
        ok = TRUE;
      }
    }
    cairo_surface_destroy(source);
  }
  cairo_destroy(cr);
  if (!ok || cairo_surface_status(out) != CAIRO_STATUS_SUCCESS) {
    cairo_surface_destroy(out);
    return NULL;
  }
  decode_count++;
  return out;
}
static void check_environment(void) {
  const char *home = g_getenv("XDG_DATA_HOME");
  const char *dirs = g_getenv("XDG_DATA_DIRS");
  const char *theme = g_getenv("K230_ICON_THEME");
  char *key = g_strdup_printf("%s\n%s\n%s", home ? home : "",
    dirs ? dirs : "", theme ? theme : "");
  if (g_strcmp0(key, environment_key)) {
    k230_icon_cache_invalidate();
    g_free(environment_key);
    environment_key = key;
  } else g_free(key);
  if (!cache) cache = g_ptr_array_new_with_free_func(free_entry);
}
static cairo_surface_t *cached_icon(GIcon *icon, int size) {
  if (!icon) return NULL;
  check_environment();
  char *identity = g_icon_to_string(icon);
  if (!identity) return NULL;
  char *key = g_strdup_printf("%d:%s", size, identity);
  g_free(identity);
  for (guint i = 0; i < cache->len; i++) {
    struct icon_entry *entry = g_ptr_array_index(cache, i);
    if (strcmp(entry->key, key)) continue;
    struct stat st;
    if (!entry->path ||
        (usable_file(entry->path, &st) && st.st_mtime == entry->mtime &&
         st.st_size == entry->bytes && st.st_ino == entry->inode)) {
      entry->touched = ++touch_clock;
      g_free(key);
      return entry->surface;
    }
    g_ptr_array_remove_index(cache, i);
    break;
  }
  char *path = resolve_icon(icon, size);
  cairo_surface_t *surface = path ? decode_icon(path, size) : NULL;
  struct icon_entry *entry = g_new0(struct icon_entry, 1);
  entry->key = key;
  entry->path = path;
  entry->surface = surface;
  entry->touched = ++touch_clock;
  if (path) {
    struct stat st;
    if (usable_file(path, &st)) {
      entry->mtime = st.st_mtime; entry->bytes = st.st_size; entry->inode = st.st_ino;
    }
  }
  if (cache->len >= ICON_CACHE_LIMIT) {
    guint oldest = 0;
    for (guint i = 1; i < cache->len; i++)
      if (((struct icon_entry *)g_ptr_array_index(cache, i))->touched <
          ((struct icon_entry *)g_ptr_array_index(cache, oldest))->touched) oldest = i;
    g_ptr_array_remove_index(cache, oldest);
  }
  g_ptr_array_add(cache, entry);
  return surface;
}
static void neutral_glyph(cairo_t *cr, double x, double y, int size, gboolean private) {
  cairo_save(cr);
  cairo_set_source_rgb(cr, private ? 0.20 : 0.24, private ? 0.30 : 0.39, 0.42);
  cairo_rectangle(cr, x, y, size, size);
  cairo_fill(cr);
  cairo_set_source_rgb(cr, 0.91, 0.95, 0.96);
  cairo_set_line_width(cr, size / 13.0);
  if (private) {
    cairo_arc(cr, x + size * .5, y + size * .38, size * .16, G_PI, 2 * G_PI);
    cairo_stroke(cr);
    cairo_rectangle(cr, x + size * .27, y + size * .42, size * .46, size * .32);
    cairo_stroke(cr);
  } else {
    cairo_arc(cr, x + size * .5, y + size * .38, size * .14, 0, 2 * G_PI);
    cairo_stroke(cr);
    cairo_move_to(cr, x + size * .25, y + size * .76);
    cairo_curve_to(cr, x + size * .28, y + size * .56,
      x + size * .72, y + size * .56, x + size * .75, y + size * .76);
    cairo_stroke(cr);
  }
  cairo_restore(cr);
}
gboolean k230_icon_draw(cairo_t *cr, GIcon *icon, enum k230_icon_use use,
                        double x, double y) {
  int size = icon_size(use);
  /* Do this before lookup: a private caller cannot populate or observe the
   * app-specific cache, even when it passes an identifying GIcon by mistake. */
  if (private_use(use)) { neutral_glyph(cr, x, y, size, TRUE); return FALSE; }
  cairo_surface_t *surface = cached_icon(icon, size);
  if (!surface) { neutral_glyph(cr, x, y, size, FALSE); return FALSE; }
  cairo_save(cr);
  cairo_set_source_surface(cr, surface, x, y);
  cairo_paint(cr);
  cairo_restore(cr);
  return TRUE;
}
