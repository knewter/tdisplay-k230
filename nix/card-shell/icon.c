#include "sway/card_shell_icon.h"
#include <limits.h>
#include <librsvg/rsvg.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

/* This mirrors the shape of nix/rust-shell-client/src/icon.rs's resolver
 * (freedesktop icon theme spec: index.theme Directories=/Inherits=,
 * per-directory Size=/Type=/MinSize=/MaxSize=/Scale=, hicolor fallback,
 * pixmaps/ fallback) using the same hand-rolled text-parsing style
 * adapter.c already uses for .desktop files, instead of GKeyFile. PNG
 * decodes via Cairo's own decoder; SVG decodes via librsvg
 * (rsvg_handle_new_from_file/rsvg_handle_render_document), the same two
 * calls icon.rs itself uses (there via raw FFI; here via the real
 * librsvg-2.0 C headers) -- librsvg is already a build input of this
 * compositor's sway-unwrapped derivation. No gio/gdk-pixbuf *usage*: only
 * librsvg's own headers/link are added, not a GdkPixbuf-based loader path. */

/* Every path/name buffer below is explicitly bounded (snprintf never
 * overflows; a too-long component is simply, safely truncated and then
 * fails the subsequent stat/open), the same "truncation is the real guard,
 * not the compiler's worst-case static estimate" situation adapter.c's
 * resolve_desktop_name already documents and suppresses this exact warning
 * for. */
#pragma GCC diagnostic ignored "-Wformat-truncation"

#define ICON_FILE_LIMIT (512u * 1024u)
#define ICON_INDEX_LIMIT (64u * 1024u)
#define ICON_CACHE_LIMIT 16
#define ICON_MAX_ROOTS 16
#define ICON_MAX_DEPTH 4

static char icon_theme_name[64] = "hicolor";
static bool icon_theme_from_env_done;

struct icon_cache_entry {
	char key[192];
	cairo_surface_t *surface; /* NULL caches a confirmed miss */
};
static struct icon_cache_entry icon_cache[ICON_CACHE_LIMIT];
static size_t icon_cache_count;

static void icon_cache_clear(void) {
	for (size_t i = 0; i < icon_cache_count; i++)
		if (icon_cache[i].surface)
			cairo_surface_destroy(icon_cache[i].surface);
	icon_cache_count = 0;
}

static bool icon_theme_name_safe(const char *theme) {
	bool safe = theme && *theme && strlen(theme) <= 63;
	if (safe && (strcmp(theme, ".") == 0 || strcmp(theme, "..") == 0))
		safe = false;
	for (const char *p = theme; safe && *p; p++) {
		unsigned char c = (unsigned char)*p;
		safe = (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
			(c >= '0' && c <= '9') || c == '_' || c == '.' || c == '+' || c == '-';
	}
	return safe;
}
void card_icon_set_theme(const char *theme) {
	icon_theme_from_env_done = true; /* an explicit call always wins over the env default */
	const char *accepted = icon_theme_name_safe(theme) ? theme : "hicolor";
	if (strcmp(icon_theme_name, accepted) == 0)
		return;
	snprintf(icon_theme_name, sizeof(icon_theme_name), "%s", accepted);
	icon_cache_clear();
}
/* Same default and env var name as nix/rust-shell-client/src/icon.rs's
 * IconCache::new(), read once lazily (not at static-init time, so tests can
 * set the env var before the first real lookup). */
static void icon_theme_from_env(void) {
	if (icon_theme_from_env_done)
		return;
	icon_theme_from_env_done = true;
	const char *env = getenv("K230_ICON_THEME");
	if (env && icon_theme_name_safe(env))
		snprintf(icon_theme_name, sizeof(icon_theme_name), "%s", env);
}

static bool icon_safe_name(const char *name) {
	if (!name || !*name || strlen(name) > 160)
		return false;
	if (strcmp(name, ".") == 0 || strcmp(name, "..") == 0)
		return false;
	for (const char *p = name; *p; p++) {
		unsigned char c = (unsigned char)*p;
		bool ok = (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
			(c >= '0' && c <= '9') || c == '_' || c == '.' || c == '+' || c == '-';
		if (!ok)
			return false;
	}
	return true;
}

struct icon_roots {
	char *paths[ICON_MAX_ROOTS];
	size_t count;
};

static void icon_roots_add(struct icon_roots *roots, const char *path, size_t len) {
	if (roots->count >= ICON_MAX_ROOTS || len == 0 || path[0] != '/')
		return;
	char *copy = malloc(len + 1);
	if (!copy)
		return;
	memcpy(copy, path, len);
	copy[len] = 0;
	roots->paths[roots->count++] = copy;
}

static void icon_roots_free(struct icon_roots *roots) {
	for (size_t i = 0; i < roots->count; i++)
		free(roots->paths[i]);
	roots->count = 0;
}

/* $XDG_DATA_HOME (or $HOME/.local/share), then $XDG_DATA_DIRS (or the same
 * default adapter.c's resolve_desktop_name uses), matching icon.rs's
 * data_roots() precedence. */
static void icon_data_roots(struct icon_roots *roots) {
	roots->count = 0;
	const char *home_data = getenv("XDG_DATA_HOME");
	if (home_data && home_data[0] == '/')
		icon_roots_add(roots, home_data, strlen(home_data));
	else {
		const char *home = getenv("HOME");
		if (home && *home) {
			char buf[PATH_MAX];
			int n = snprintf(buf, sizeof(buf), "%s/.local/share", home);
			if (n > 0 && (size_t)n < sizeof(buf))
				icon_roots_add(roots, buf, (size_t)n);
		}
	}
	const char *xdg = getenv("XDG_DATA_DIRS");
	if (!xdg || !*xdg)
		xdg = "/run/current-system/sw/share:/usr/local/share:/usr/share";
	char *dirs = strdup(xdg);
	if (!dirs)
		return;
	for (char *dir = strtok(dirs, ":"); dir && roots->count < ICON_MAX_ROOTS;
			dir = strtok(NULL, ":"))
		icon_roots_add(roots, dir, strlen(dir));
	free(dirs);
}

static bool icon_file_usable(const char *path) {
	struct stat st;
	return stat(path, &st) == 0 && S_ISREG(st.st_mode) &&
		st.st_size > 0 && (unsigned long)st.st_size <= ICON_FILE_LIMIT;
}

/* Freedesktop icon theme directories are conventionally "<size>/<context>"
 * (e.g. "48x48/apps") -- a single level of nesting is normal, not a path
 * escape. Reject only a traversal segment ("..", ".") or an empty segment
 * (a leading/trailing/doubled '/'). */
static bool icon_dir_safe(const char *dir) {
	if (!dir || !*dir)
		return false;
	const char *p = dir;
	while (*p) {
		const char *slash = strchr(p, '/');
		size_t seglen = slash ? (size_t)(slash - p) : strlen(p);
		if (seglen == 0 || (seglen <= 2 && strncmp(p, "..", seglen) == 0) ||
				(seglen == 1 && p[0] == '.'))
			return false;
		p += seglen + (slash ? 1 : 0);
		if (!slash)
			break;
	}
	return true;
}
/* <root>/icons/<theme>/<dir>/<name>.{png,svg}, only if it exists and is a
 * sane regular file. PNG preferred over SVG when a directory somehow has
 * both, matching icon.rs's own try_file() order; in practice a themed
 * directory is one or the other, not both. NULL on any path overflow or
 * missing/oversized file. */
static char *icon_try_file(const char *root, const char *theme, const char *dir,
		const char *name) {
	if (!icon_dir_safe(dir))
		return NULL;
	static const char *const exts[] = {"png", "svg"};
	for (size_t e = 0; e < sizeof(exts) / sizeof(exts[0]); e++) {
		char path[PATH_MAX];
		int n = snprintf(path, sizeof(path), "%s/icons/%s/%s/%s.%s", root, theme, dir, name,
			exts[e]);
		if (n > 0 && (size_t)n < sizeof(path) && icon_file_usable(path))
			return strdup(path);
	}
	return NULL;
}

static int icon_dir_score(bool scalable, int decl_size, int min_size, int max_size,
		int scale, int wanted) {
	if (decl_size <= 0)
		return 1000; /* undeclared/legacy directory: always acceptable, lowest priority */
	int s = scale > 0 ? scale : 1;
	if (scalable) {
		int min = (min_size > 0 ? min_size : decl_size) * s;
		int max = (max_size > 0 ? max_size : decl_size) * s;
		if (wanted < min)
			return min - wanted;
		return wanted > max ? wanted - max : 0;
	}
	return abs(decl_size * s - wanted);
}

/* Parses one <root>/icons/<theme>/index.theme: [Icon Theme]'s Directories=/
 * ScaledDirectories=/Inherits= (first occurrence of each; a theme index is
 * not expected to repeat [Icon Theme]), then every OTHER bracketed section
 * that Directories=/ScaledDirectories= actually named, reading that
 * section's Size=/Type=/MinSize=/MaxSize=/Scale=, scoring it against
 * `wanted`, and keeping the best-scoring section whose <name>.png file
 * genuinely exists. `inherits_out` receives the raw Inherits= value for the
 * caller's recursive fallback walk (left untouched if this index has none
 * or was already filled by an earlier root). */
static char *icon_index_lookup(const char *root, const char *theme, const char *name,
		int wanted, char *inherits_out, size_t inherits_len) {
	char index_path[PATH_MAX];
	int n = snprintf(index_path, sizeof(index_path), "%s/icons/%s/index.theme", root, theme);
	if (n <= 0 || (size_t)n >= sizeof(index_path))
		return NULL;
	struct stat st;
	if (stat(index_path, &st) != 0 || !S_ISREG(st.st_mode) ||
			(unsigned long)st.st_size > ICON_INDEX_LIMIT)
		return NULL;
	FILE *f = fopen(index_path, "r");
	if (!f)
		return NULL;
	char directories[8192] = {0}; /* ",dir1,dir2,..." so strstr never partial-matches */
	bool have_directories = false, in_icon_theme = false, current_listed = false;
	char current_dir[192] = {0};
	int current_size = 0, current_min = 0, current_max = 0, current_scale = 1;
	bool current_scalable = false;
	char *best_path = NULL;
	int best_score = INT_MAX;
	char line[1024];
	while (fgets(line, sizeof(line), f)) {
		size_t len = strlen(line);
		while (len && (line[len - 1] == '\n' || line[len - 1] == '\r')) line[--len] = 0;
		if (line[0] == '[') {
			if (current_listed) {
				int score = icon_dir_score(current_scalable, current_size, current_min,
					current_max, current_scale, wanted);
				if (score < best_score) {
					char *found = icon_try_file(root, theme, current_dir, name);
					if (found) {
						free(best_path);
						best_path = found;
						best_score = score;
					}
				}
			}
			in_icon_theme = strcmp(line, "[Icon Theme]") == 0;
			current_listed = false;
			if (!in_icon_theme && len >= 2) {
				size_t dlen = len - 2 >= sizeof(current_dir) ? sizeof(current_dir) - 1 : len - 2;
				memcpy(current_dir, line + 1, dlen);
				current_dir[dlen] = 0;
				char needle[196];
				snprintf(needle, sizeof(needle), ",%s,", current_dir);
				current_listed = have_directories && strstr(directories, needle) != NULL;
			}
			current_size = current_min = current_max = 0;
			current_scale = 1;
			current_scalable = false;
			continue;
		}
		if (in_icon_theme) {
			if (strncmp(line, "Directories=", 12) == 0) {
				size_t used = strlen(directories);
				if (!used) { directories[0] = ','; used = 1; }
				snprintf(directories + used, sizeof(directories) - used, "%s,", line + 12);
				have_directories = true;
			} else if (strncmp(line, "ScaledDirectories=", 18) == 0) {
				size_t used = strlen(directories);
				if (!used) { directories[0] = ','; used = 1; }
				snprintf(directories + used, sizeof(directories) - used, "%s,", line + 18);
				have_directories = true;
			} else if (strncmp(line, "Inherits=", 9) == 0 && inherits_out && !*inherits_out) {
				snprintf(inherits_out, inherits_len, "%s", line + 9);
			}
			continue;
		}
		if (!current_listed)
			continue;
		if (strncmp(line, "Size=", 5) == 0)
			current_size = atoi(line + 5);
		else if (strncmp(line, "MinSize=", 8) == 0)
			current_min = atoi(line + 8);
		else if (strncmp(line, "MaxSize=", 8) == 0)
			current_max = atoi(line + 8);
		else if (strncmp(line, "Scale=", 6) == 0)
			current_scale = atoi(line + 6);
		else if (strncmp(line, "Type=", 5) == 0)
			current_scalable = strcmp(line + 5, "Scalable") == 0;
	}
	if (current_listed) {
		int score = icon_dir_score(current_scalable, current_size, current_min,
			current_max, current_scale, wanted);
		if (score < best_score) {
			char *found = icon_try_file(root, theme, current_dir, name);
			if (found) {
				free(best_path);
				best_path = found;
			}
		}
	}
	fclose(f);
	return best_path;
}

static char *icon_theme_lookup(const struct icon_roots *roots, const char *theme,
		const char *name, int wanted, int depth, char visited[][64], size_t *visited_count) {
	if (depth >= ICON_MAX_DEPTH || !icon_safe_name(theme))
		return NULL;
	for (size_t i = 0; i < *visited_count; i++)
		if (strcmp(visited[i], theme) == 0)
			return NULL;
	if (*visited_count >= ICON_MAX_DEPTH * 4)
		return NULL;
	snprintf(visited[*visited_count], 64, "%s", theme);
	(*visited_count)++;
	char inherits[256] = {0};
	static const char *fallback_dirs[] = {"apps", "places", "actions", "categories"};
	static const int fallback_sizes[] = {48, 64, 32, 24, 128, 256, 16};
	for (size_t i = 0; i < roots->count; i++) {
		char *found = icon_index_lookup(roots->paths[i], theme, name, wanted,
			inherits, sizeof(inherits));
		if (found)
			return found;
		/* A theme with no parsable (or matching) index.theme entry still
		 * commonly ships the conventional "<size>x<size>/<context>/<name>.png"
		 * layout; try the requested size first, then common fallbacks. */
		for (size_t s = 0; s < 1 + sizeof(fallback_sizes) / sizeof(fallback_sizes[0]); s++) {
			int size = s == 0 ? wanted : fallback_sizes[s - 1];
			char dir[64];
			snprintf(dir, sizeof(dir), "%dx%d", size, size);
			for (size_t g = 0; g < sizeof(fallback_dirs) / sizeof(fallback_dirs[0]); g++) {
				char subdir[128];
				snprintf(subdir, sizeof(subdir), "%s/%s", dir, fallback_dirs[g]);
				char *guess = icon_try_file(roots->paths[i], theme, subdir, name);
				if (guess)
					return guess;
			}
		}
	}
	if (*inherits) {
		char copy[256];
		snprintf(copy, sizeof(copy), "%s", inherits);
		for (char *item = strtok(copy, ","); item; item = strtok(NULL, ",")) {
			while (*item == ' ') item++;
			char *found = icon_theme_lookup(roots, item, name, wanted, depth + 1,
				visited, visited_count);
			if (found)
				return found;
		}
	}
	return NULL;
}

static char *icon_resolve(const char *icon_name, int wanted) {
	if (!icon_name || !*icon_name)
		return NULL;
	if (icon_name[0] == '/')
		return icon_file_usable(icon_name) ? strdup(icon_name) : NULL;
	if (!icon_safe_name(icon_name))
		return NULL;
	struct icon_roots roots;
	icon_data_roots(&roots);
	char visited[ICON_MAX_DEPTH * 4][64];
	size_t visited_count = 0;
	char *found = icon_theme_lookup(&roots, icon_theme_name, icon_name, wanted, 0,
		visited, &visited_count);
	if (!found && strcmp(icon_theme_name, "hicolor") != 0) {
		visited_count = 0;
		found = icon_theme_lookup(&roots, "hicolor", icon_name, wanted, 0, visited, &visited_count);
	}
	if (!found) {
		for (size_t i = 0; i < roots.count && !found; i++) {
			static const char *const exts[] = {"png", "svg"};
			for (size_t e = 0; e < sizeof(exts) / sizeof(exts[0]) && !found; e++) {
				char path[PATH_MAX];
				int n = snprintf(path, sizeof(path), "%s/pixmaps/%s.%s", roots.paths[i],
					icon_name, exts[e]);
				if (n > 0 && (size_t)n < sizeof(path) && icon_file_usable(path))
					found = strdup(path);
			}
		}
	}
	icon_roots_free(&roots);
	return found;
}

static bool icon_path_has_suffix(const char *path, const char *suffix) {
	size_t plen = strlen(path), slen = strlen(suffix);
	return plen >= slen && strcmp(path + (plen - slen), suffix) == 0;
}

/* librsvg render, the same two calls icon.rs uses (rsvg_handle_new_from_file
 * then rsvg_handle_render_document into a viewport the size of the target
 * surface -- librsvg itself preserves aspect and centers within it). */
static cairo_surface_t *icon_decode_svg(const char *path, int size) {
	GError *error = NULL;
	RsvgHandle *handle = rsvg_handle_new_from_file(path, &error);
	if (!handle) {
		if (error)
			g_error_free(error);
		return NULL;
	}
	cairo_surface_t *out = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, size, size);
	if (cairo_surface_status(out) != CAIRO_STATUS_SUCCESS) {
		g_object_unref(handle);
		cairo_surface_destroy(out);
		return NULL;
	}
	cairo_t *cr = cairo_create(out);
	RsvgRectangle viewport = {.x = 0, .y = 0, .width = size, .height = size};
	bool rendered = rsvg_handle_render_document(handle, cr, &viewport, &error);
	if (!rendered && error)
		g_error_free(error);
	bool ok = rendered && cairo_status(cr) == CAIRO_STATUS_SUCCESS;
	cairo_destroy(cr);
	g_object_unref(handle);
	cairo_surface_flush(out);
	if (!ok) {
		cairo_surface_destroy(out);
		return NULL;
	}
	return out;
}

static cairo_surface_t *icon_decode(const char *path, int size) {
	if (!icon_file_usable(path) || size < 8 || size > 512)
		return NULL;
	if (icon_path_has_suffix(path, ".svg"))
		return icon_decode_svg(path, size);
	cairo_surface_t *source = cairo_image_surface_create_from_png(path);
	if (!source)
		return NULL;
	if (cairo_surface_status(source) != CAIRO_STATUS_SUCCESS) {
		cairo_surface_destroy(source);
		return NULL;
	}
	int sw = cairo_image_surface_get_width(source), sh = cairo_image_surface_get_height(source);
	if (sw <= 0 || sh <= 0) {
		cairo_surface_destroy(source);
		return NULL;
	}
	cairo_surface_t *out = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, size, size);
	if (cairo_surface_status(out) != CAIRO_STATUS_SUCCESS) {
		cairo_surface_destroy(source);
		cairo_surface_destroy(out);
		return NULL;
	}
	cairo_t *cr = cairo_create(out);
	double scale = fmin((double)size / sw, (double)size / sh);
	cairo_translate(cr, (size - sw * scale) / 2.0, (size - sh * scale) / 2.0);
	cairo_scale(cr, scale, scale);
	cairo_set_source_surface(cr, source, 0, 0);
	cairo_pattern_set_filter(cairo_get_source(cr), CAIRO_FILTER_GOOD);
	cairo_paint(cr);
	bool ok = cairo_status(cr) == CAIRO_STATUS_SUCCESS;
	cairo_destroy(cr);
	cairo_surface_destroy(source);
	cairo_surface_flush(out);
	if (!ok) {
		cairo_surface_destroy(out);
		return NULL;
	}
	return out;
}

bool card_icon_paint(cairo_t *cr, const char *icon_name, int size, double x, double y) {
	if (!cr || !icon_name || !*icon_name || size <= 0)
		return false;
	icon_theme_from_env();
	char key[192];
	snprintf(key, sizeof(key), "%s:%d:%s", icon_theme_name, size, icon_name);
	cairo_surface_t *surface = NULL;
	bool cached = false;
	for (size_t i = 0; i < icon_cache_count; i++) {
		if (strcmp(icon_cache[i].key, key) == 0) {
			surface = icon_cache[i].surface;
			cached = true;
			break;
		}
	}
	if (!cached) {
		char *path = icon_resolve(icon_name, size);
		if (path) {
			surface = icon_decode(path, size);
			free(path);
		}
		if (icon_cache_count == ICON_CACHE_LIMIT) {
			if (icon_cache[0].surface)
				cairo_surface_destroy(icon_cache[0].surface);
			memmove(&icon_cache[0], &icon_cache[1], (ICON_CACHE_LIMIT - 1) * sizeof(icon_cache[0]));
			icon_cache_count--;
		}
		snprintf(icon_cache[icon_cache_count].key, sizeof(icon_cache[icon_cache_count].key),
			"%s", key);
		icon_cache[icon_cache_count].surface = surface;
		icon_cache_count++;
	}
	if (!surface)
		return false;
	cairo_set_source_surface(cr, surface, x, y);
	cairo_paint(cr);
	return cairo_status(cr) == CAIRO_STATUS_SUCCESS;
}
