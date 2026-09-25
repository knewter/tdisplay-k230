#define _GNU_SOURCE
#include "sway/card_shell_appearance.h"

#include <errno.h>
#include <fcntl.h>
#include <json-c/json.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/un.h>
#include <time.h>
#include <unistd.h>

#define APPEARANCE_FILE_LIMIT (256u * 1024u)
#define APPEARANCE_REQUEST_LIMIT 4096u

static struct {
	int listener, client;
	char socket_path[sizeof(((struct sockaddr_un *)0)->sun_path)];
	char state_root[1025], default_path[1025];
	char input[APPEARANCE_REQUEST_LIMIT + 1];
	size_t used;
	uint64_t deadline_ms;
	struct card_appearance current, candidate, previous, fallback;
	char candidate_path[1025], previous_path[1025];
	bool prepared;
	bool owns_socket;
	card_appearance_apply_fn apply;
	card_appearance_prepare_fn prepare;
	void *apply_data;
} service = {.listener = -1, .client = -1};

static uint64_t monotonic_ms(void) {
	struct timespec t;
	clock_gettime(CLOCK_MONOTONIC, &t);
	return (uint64_t)t.tv_sec * 1000 + t.tv_nsec / 1000000;
}

static bool identity(const char *value) {
	if (!value || strlen(value) != 24) return false;
	for (const char *p = value; *p; ++p)
		if (*p < '0' || (*p > '9' && *p < 'a') || *p > 'f') return false;
	return true;
}

static const char *string(json_object *object, const char *key) {
	json_object *value;
	return object && json_object_object_get_ex(object, key, &value) &&
		json_object_get_type(value) == json_type_string ? json_object_get_string(value) : NULL;
}

static bool number(json_object *object, const char *key, double *out) {
	json_object *value;
	if (!object || !json_object_object_get_ex(object, key, &value) ||
		(json_object_get_type(value) != json_type_double &&
		 json_object_get_type(value) != json_type_int)) return false;
	*out = json_object_get_double(value);
	return isfinite(*out);
}

static bool color(const char *value, uint32_t *result) {
	if (!value || strlen(value) != 9 || value[0] != '#') return false;
	uint32_t out = 0;
	for (int i = 1; i < 9; ++i) {
		char c = value[i];
		unsigned digit = c >= '0' && c <= '9' ? (unsigned)(c - '0') :
			c >= 'a' && c <= 'f' ? (unsigned)(c - 'a' + 10) :
			c >= 'A' && c <= 'F' ? (unsigned)(c - 'A' + 10) : 16;
		if (digit == 16) return false;
		out = (out << 4) | digit;
	}
	*result = out;
	return true;
}

static bool palette_color(json_object *palette, const char *key, uint32_t *result) {
	const char *value = string(palette, key);
	if (!value || value[0] != '#') return false;
	size_t length = strlen(value);
	if (length != 7 && length != 9) return false;
	char argb[10] = "#ff000000";
	memcpy(argb + 3, value + 1, 6);
	if (length == 9) memcpy(argb + 1, value + 7, 2);
	return color(argb, result);
}

static void solid(struct card_brush *brush, uint32_t argb) {
	*brush = (struct card_brush){.count = 1, .alpha = 1};
	brush->stops[0] = (struct card_brush_stop){.argb = argb, .offset = 0};
}

static bool brush(json_object *token, struct card_brush *out) {
	if (!token || json_object_get_type(token) != json_type_object ||
		!string(token, "kind") || strcmp(string(token, "kind"), "brush")) return false;
	json_object *stops;
	if (!json_object_object_get_ex(token, "stops", &stops) ||
		json_object_get_type(stops) != json_type_array) return false;
	size_t count = json_object_array_length(stops);
	if (!count || count > CARD_APPEARANCE_STOPS) return false;
	struct card_brush parsed = {.count = count};
	if (!number(token, "angle_degrees", &parsed.angle_degrees) ||
		!number(token, "alpha", &parsed.alpha) || parsed.alpha < 0 ||
		parsed.alpha > 1 || fabs(parsed.angle_degrees) > 3600) return false;
	double previous = -1;
	for (size_t i = 0; i < count; ++i) {
		json_object *stop = json_object_array_get_idx(stops, i);
		if (!stop || json_object_get_type(stop) != json_type_object ||
			!color(string(stop, "argb"), &parsed.stops[i].argb) ||
			!number(stop, "offset", &parsed.stops[i].offset) ||
			parsed.stops[i].offset < 0 || parsed.stops[i].offset > 1 ||
			parsed.stops[i].offset < previous) return false;
		previous = parsed.stops[i].offset;
	}
	*out = parsed;
	return true;
}

static bool authored(json_object *sections, const char *key, struct card_brush *out) {
	json_object *section, *token;
	if (!json_object_object_get_ex(sections, "card", &section)) return true;
	if (json_object_get_type(section) != json_type_object) return false;
	if (!json_object_object_get_ex(section, key, &token)) return true;
	return brush(token, out);
}

static bool authored_color(json_object *sections, const char *key, uint32_t *out) {
	json_object *section, *token;
	if (!json_object_object_get_ex(sections, "card", &section)) return true;
	if (json_object_get_type(section) != json_type_object) return false;
	if (!json_object_object_get_ex(section, key, &token)) return true;
	struct card_brush parsed;
	if (!brush(token, &parsed) || parsed.count != 1) return false;
	uint32_t a = parsed.stops[0].argb >> 24;
	a = (uint32_t)lround(a * parsed.alpha);
	*out = (parsed.stops[0].argb & 0x00ffffffu) | (a << 24);
	return true;
}

static json_object *read_json(const char *directory, const char *filename) {
	char path[1200];
	int length = snprintf(path, sizeof(path), "%s/%s", directory, filename);
	if (length <= 0 || (size_t)length >= sizeof(path)) return NULL;
	int fd = open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK);
	if (fd < 0) return NULL;
	struct stat st;
	bool valid = fstat(fd, &st) == 0 && S_ISREG(st.st_mode) &&
		st.st_size > 0 && st.st_size <= APPEARANCE_FILE_LIMIT;
	char *data = valid ? calloc(1, (size_t)st.st_size + 1) : NULL;
	if (!data) valid = false;
	size_t used = 0;
	while (valid && used < (size_t)st.st_size) {
		ssize_t n = read(fd, data + used, (size_t)st.st_size - used);
		if (n <= 0) valid = false;
		else used += (size_t)n;
	}
	close(fd);
	json_object *object = valid ? json_tokener_parse(data) : NULL;
	free(data);
	return object;
}

static bool under_generations(const char *path, const char *id, bool allow_default,
		char *canonical, size_t capacity) {
	if (!path || strlen(path) > 1024 || path[0] != '/' || !identity(id)) return false;
	char *resolved = realpath(path, NULL);
	if (!resolved) return false;
	char prefix[1100];
	int length = snprintf(prefix, sizeof(prefix), "%s/generations/%s", service.state_root, id);
	bool safe = length > 0 && (size_t)length < sizeof(prefix) &&
		!strcmp(resolved, prefix);
	if (!safe && allow_default) safe = !strcmp(resolved, service.default_path);
	if (safe && strlen(resolved) < capacity) strcpy(canonical, resolved);
	else safe = false;
	free(resolved);
	return safe;
}

static bool load(const char *path, const char *id, bool allow_default,
		struct card_appearance *out) {
	char directory[1025];
	if (!under_generations(path, id, allow_default, directory, sizeof(directory))) return false;
	json_object *report = read_json(directory, "report.json");
	json_object *tokens = read_json(directory, "appearance.json");
	bool okay = report && tokens && json_object_get_type(report) == json_type_object &&
		json_object_get_type(tokens) == json_type_object &&
		string(report, "generation") && !strcmp(string(report, "generation"), id) &&
		string(tokens, "generation") && !strcmp(string(tokens, "generation"), id);
	json_object *version = NULL, *sections = NULL, *palette = NULL, *background = NULL;
	if (okay) okay = json_object_object_get_ex(tokens, "version", &version) &&
		json_object_get_type(version) == json_type_int && json_object_get_int(version) == 1 &&
		json_object_object_get_ex(tokens, "sections", &sections) &&
		json_object_get_type(sections) == json_type_object &&
		json_object_object_get_ex(report, "palette", &palette) &&
		json_object_get_type(palette) == json_type_object &&
		json_object_object_get_ex(tokens, "background", &background);
	struct card_appearance next = {0};
	uint32_t canvas, card, selected, text;
	if (okay) okay = palette_color(palette, "background", &canvas) &&
		palette_color(palette, "dark_background", &card) &&
		palette_color(palette, "lighter_background", &selected) &&
		palette_color(palette, "foreground", &text);
	if (okay) {
		next.wallpaper = json_object_get_type(background) == json_type_string &&
			!strcmp(json_object_get_string(background), "background");
		okay = next.wallpaper || json_object_get_type(background) == json_type_null;
	}
	if (okay) {
		solid(&next.canvas, canvas);
		solid(&next.card, card);
		solid(&next.selected, selected);
		next.text = text;
		next.selected_text = text;
		json_object *card_section = NULL;
		json_object *canvas_token = NULL;
		next.canvas_authored = json_object_object_get_ex(sections, "card", &card_section) &&
			json_object_get_type(card_section) == json_type_object &&
			json_object_object_get_ex(card_section, "canvas", &canvas_token);
		okay = authored(sections, "canvas", &next.canvas) &&
			authored(sections, "background", &next.card) &&
			authored(sections, "selected-background", &next.selected) &&
			authored_color(sections, "text", &next.text) &&
			authored_color(sections, "selected-text", &next.selected_text);
	}
	if (okay) {
		strcpy(next.generation, id);
		*out = next;
	}
	if (report) json_object_put(report);
	if (tokens) json_object_put(tokens);
	return okay;
}

static void close_client(void) {
	if (service.client >= 0) close(service.client);
	service.client = -1;
	service.used = 0;
}

/* A new home need not have a theme cache yet. Canonicalize its existing
 * ancestor while refusing ambiguous dot segments in the missing suffix. */
static char *planned_root(const char *path) {
	char *resolved = realpath(path, NULL);
	if (resolved || errno != ENOENT) return resolved;
	char *copy = strdup(path);
	if (!copy) return NULL;
	char *cut = copy + strlen(copy);
	while (cut > copy + 1) {
		while (cut > copy + 1 && *cut != '/') --cut;
		if (cut <= copy + 1) break;
		char saved = *cut;
		*cut = 0;
		resolved = realpath(copy, NULL);
		*cut = saved;
		if (resolved) {
			const char *suffix = path + (cut - copy);
			char *part = strdup(suffix);
			if (!part) { free(resolved); break; }
			bool safe = true;
			for (char *token = strtok(part, "/"); token; token = strtok(NULL, "/"))
				if (!strcmp(token, ".") || !strcmp(token, "..")) safe = false;
			free(part);
			if (!safe) { free(resolved); break; }
			char *result = NULL;
			if (asprintf(&result, "%s%s", resolved, suffix) < 0) result = NULL;
			free(resolved); free(copy);
			return result;
		}
		if (errno != ENOENT) break;
		cut--;
	}
	free(copy);
	return NULL;
}

static void answer(const char *phase, const char *id, bool ok) {
	char response[192];
	int n = id ? snprintf(response, sizeof(response),
		"{\"protocol\":1,\"phase\":\"%s\",\"generation\":\"%s\",\"status\":\"%s\"}\n",
		phase, id, ok ? "ok" : "error") : snprintf(response, sizeof(response),
		"{\"protocol\":1,\"phase\":\"%s\",\"generation\":null,\"status\":\"%s\"}\n",
		phase, ok ? "ok" : "error");
	if (n > 0 && (size_t)n < sizeof(response))
		(void)send(service.client, response, (size_t)n, MSG_NOSIGNAL);
	close_client();
}

static void request(void) {
	json_object *message = json_tokener_parse(service.input);
	if (!message || json_object_get_type(message) != json_type_object) {
		if (message) json_object_put(message);
		close_client();
		return;
	}
	const char *phase = string(message, "phase");
	const char *id = string(message, "generation");
	const char *path = string(message, "path");
	json_object *version = NULL, *id_field = NULL, *path_field = NULL;
	bool valid = json_object_object_get_ex(message, "protocol", &version) &&
		json_object_get_type(version) == json_type_int && json_object_get_int(version) == 1 &&
		json_object_object_get_ex(message, "generation", &id_field) &&
		json_object_object_get_ex(message, "path", &path_field) &&
		((id && path) || (json_object_get_type(id_field) == json_type_null &&
		 json_object_get_type(path_field) == json_type_null));
	bool ok = false;
	if (valid && phase && !strcmp(phase, "prepare") && identity(id)) {
		service.prepared = false;
		service.candidate_path[0] = 0;
		service.previous_path[0] = 0;
		struct card_appearance next, prior = service.current;
		const char *old_id = string(message, "previous_generation");
		const char *old_path = string(message, "previous_path");
		json_object *old_id_field = NULL, *old_path_field = NULL;
		valid = json_object_object_get_ex(message, "previous_generation", &old_id_field) &&
			json_object_object_get_ex(message, "previous_path", &old_path_field) &&
			((old_id && old_path && identity(old_id) && load(old_path, old_id, false, &prior)) ||
			 (json_object_get_type(old_id_field) == json_type_null &&
			  json_object_get_type(old_path_field) == json_type_null));
		if (valid && load(path, id, false, &next)) {
			service.candidate = next;
			service.previous = old_id ? prior : service.fallback;
			(void)under_generations(path, id, false, service.candidate_path,
				sizeof(service.candidate_path));
			if (old_id)
				(void)under_generations(old_path, old_id, false, service.previous_path,
					sizeof(service.previous_path));
			service.prepared = true;
			ok = true;
			/* Advisory warm-up hook (task 3.1b): give the caller a chance to
			 * pre-build whatever commit will want for this exact candidate.
			 * Runs only after `load()` above has fully validated `next`, so
			 * `service.candidate` is never a partially parsed or rejected
			 * appearance -- and before `answer()` below, so its own
			 * (possibly nonzero) cost is paid before this prepare's ack,
			 * same as the Rust receiver's own prepare-time decode. */
			if (service.prepare) service.prepare(&service.candidate, service.apply_data);
		}
	} else if (valid && phase && !strcmp(phase, "commit") && identity(id) &&
		service.prepared && !strcmp(service.candidate.generation, id)) {
		char canonical[1025];
		if (!under_generations(path, id, false, canonical, sizeof(canonical)) ||
			strcmp(canonical, service.candidate_path)) goto done;
		struct card_appearance old = service.current;
		if (service.apply(&service.candidate, service.apply_data)) {
			service.current = service.candidate;
			ok = true;
		} else (void)service.apply(&old, service.apply_data);
	} else if (valid && phase && !strcmp(phase, "rollback") &&
		((id && identity(id)) || (!id && json_object_get_type(id_field) == json_type_null))) {
		struct card_appearance previous = service.fallback;
		char canonical[1025];
		bool cached = id && service.prepared &&
			!strcmp(service.previous.generation, id) &&
			under_generations(path, id, false, canonical, sizeof(canonical)) &&
			!strcmp(canonical, service.previous_path);
		if (cached) previous = service.previous;
		if ((!id || cached || load(path, id, false, &previous)) &&
			service.apply(&previous, service.apply_data)) {
			service.current = previous;
			service.prepared = false;
			ok = true;
		}
	}
done:
	if (phase && (!strcmp(phase, "prepare") || !strcmp(phase, "commit") ||
		!strcmp(phase, "rollback"))) answer(phase, id, ok);
	else close_client();
	json_object_put(message);
}

bool card_appearance_start(const char *socket_path, const char *state_root,
		const char *default_generation, card_appearance_apply_fn apply,
		card_appearance_prepare_fn prepare, void *data) {
	if (!socket_path || !state_root || !default_generation || !apply ||
		strlen(socket_path) >= sizeof(service.socket_path) ||
		strlen(state_root) >= sizeof(service.state_root) ||
		strlen(default_generation) >= sizeof(service.default_path) ||
		socket_path[0] != '/' || state_root[0] != '/' || default_generation[0] != '/') return false;
	char *root = planned_root(state_root);
	char *pinned = realpath(default_generation, NULL);
	if (!root || !pinned) { free(root); free(pinned); return false; }
	if (strlen(root) >= sizeof(service.state_root) ||
		strlen(pinned) >= sizeof(service.default_path)) {
		free(root); free(pinned); return false;
	}
	strcpy(service.state_root, root);
	strcpy(service.default_path, pinned);
	free(root); free(pinned);
	strcpy(service.socket_path, socket_path);
	const char *id = strrchr(service.default_path, '/');
	if (!id || !identity(++id) ||
		!load(service.default_path, id, true, &service.fallback)) return false;
	service.current = service.fallback;
	char pointer[1100];
	if (snprintf(pointer, sizeof(pointer), "%s/active", service.state_root) <
		(int)sizeof(pointer)) {
		char *active = realpath(pointer, NULL);
		if (active) {
			const char *active_id = strrchr(active, '/');
			struct card_appearance selected;
			if (active_id && load(active, active_id + 1, false, &selected))
				service.current = selected;
			free(active);
		}
	}
	service.apply = apply;
	service.prepare = prepare;
	service.apply_data = data;
	char parent[sizeof(service.socket_path)];
	strcpy(parent, socket_path);
	char *slash = strrchr(parent, '/');
	if (!slash || slash == parent) return false;
	*slash = 0;
	struct stat st;
	if (stat(parent, &st) != 0 || !S_ISDIR(st.st_mode) ||
		st.st_uid != geteuid() || (st.st_mode & 0077)) return false;
	if (lstat(socket_path, &st) == 0) {
		if (!S_ISSOCK(st.st_mode) || st.st_uid != geteuid()) return false;
		int probe = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
		if (probe < 0) return false;
		struct sockaddr_un existing = {.sun_family = AF_UNIX};
		strcpy(existing.sun_path, socket_path);
		int connected = connect(probe, (struct sockaddr *)&existing, sizeof(existing));
		int failure = errno;
		close(probe);
		if (connected == 0 || failure != ECONNREFUSED || unlink(socket_path) != 0)
			return false;
	} else if (errno != ENOENT) return false;
	service.listener = socket(AF_UNIX, SOCK_STREAM | SOCK_NONBLOCK | SOCK_CLOEXEC, 0);
	if (service.listener < 0) return false;
	struct sockaddr_un address = {.sun_family = AF_UNIX};
	strcpy(address.sun_path, socket_path);
	mode_t old_umask = umask(0077);
	int bound = bind(service.listener, (struct sockaddr *)&address, sizeof(address));
	umask(old_umask);
	if (bound != 0 || chmod(socket_path, 0600) != 0 || listen(service.listener, 2) != 0) {
		service.owns_socket = bound == 0;
		card_appearance_stop();
		return false;
	}
	service.owns_socket = true;
	if (!service.apply(&service.current, service.apply_data)) {
		card_appearance_stop();
		return false;
	}
	return true;
}

void card_appearance_poll(void) {
	if (service.listener < 0) return;
	if (service.client >= 0 && monotonic_ms() > service.deadline_ms) close_client();
	if (service.client < 0) {
		int client = accept4(service.listener, NULL, NULL, SOCK_NONBLOCK | SOCK_CLOEXEC);
		if (client >= 0) {
			struct ucred peer;
			socklen_t length = sizeof(peer);
			if (getsockopt(client, SOL_SOCKET, SO_PEERCRED, &peer, &length) != 0 ||
				length != sizeof(peer) || peer.uid != geteuid()) close(client);
			else {
				service.client = client;
				service.deadline_ms = monotonic_ms() + 2000;
				service.used = 0;
			}
		}
	}
	if (service.client < 0) return;
	ssize_t n = recv(service.client, service.input + service.used,
		APPEARANCE_REQUEST_LIMIT - service.used, MSG_DONTWAIT);
	if (n == 0 || (n < 0 && errno != EAGAIN && errno != EWOULDBLOCK)) {
		close_client(); return;
	}
	if (n > 0) {
		service.used += (size_t)n;
		char *end = memchr(service.input, '\n', service.used);
		if (end) {
			*end = 0;
			request();
		} else if (service.used == APPEARANCE_REQUEST_LIMIT) close_client();
	}
}

void card_appearance_stop(void) {
	close_client();
	if (service.listener >= 0) close(service.listener);
	service.listener = -1;
	if (service.owns_socket && service.socket_path[0]) unlink(service.socket_path);
	service.owns_socket = false;
	service.socket_path[0] = 0;
}

const struct card_appearance *card_appearance_current(void) { return &service.current; }
