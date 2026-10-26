/* Read-only k230-settings status, without interpreter startup during a reveal.
 * Keep the JSON/capability semantics in sync with tools/device_settings.py;
 * tests/test_settings_status.py compares both implementations. Actions stay
 * in Python. No user/device identifiers or command output enter this JSON. */
#define _POSIX_C_SOURCE 200809L
#include <ctype.h>
#include <dirent.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <unistd.h>

static bool integer(const char *path, uint64_t *value) {
	char buf[33];
	FILE *f = fopen(path, "r");
	if (!f) return false;
	size_t n = fread(buf, 1, 32, f);
	bool ok = !ferror(f);
	fclose(f);
	if (!ok) return false;
	buf[n] = '\0';
	char *start = buf, *end = buf + n;
	while (start < end && isspace((unsigned char)*start)) ++start;
	while (end > start && isspace((unsigned char)end[-1])) --end;
	if (end - start < 1 || end - start > 10) return false;
	uint64_t result = 0;
	for (char *p = start; p < end; ++p) {
		if (*p < '0' || *p > '9') return false;
		result = result * 10 + (unsigned)(*p - '0');
	}
	*value = result;
	return true;
}

static bool path(char *dest, size_t size, const char *root,
		 const char *branch, const char *name, const char *file) {
	int n = snprintf(dest, size, "%s/class/%s/%s/%s", root, branch, name, file);
	return n >= 0 && (size_t)n < size;
}

static int visible(const struct dirent *entry) {
	return strcmp(entry->d_name, ".") && strcmp(entry->d_name, "..");
}

static int entries(const char *root, const char *branch, struct dirent ***list) {
	char dir[4096];
	int n = snprintf(dir, sizeof(dir), "%s/class/%s", root, branch);
	if (n < 0 || (size_t)n >= sizeof(dir)) return -1;
	return scandir(dir, list, visible, alphasort);
}

static void free_entries(struct dirent **list, int count) {
	for (int i = 0; i < count; ++i) free(list[i]);
	free(list);
}

static void network(const char *root) {
	struct dirent **list = NULL;
	int count = entries(root, "net", &list), links = 0;
	bool up = false, all_down = true;
	for (int i = 0; i < count && i < 64; ++i) {
		if (!strcmp(list[i]->d_name, "lo")) continue;
		++links;
		char file[4096];
		uint64_t carrier;
		if (!path(file, sizeof(file), root, "net", list[i]->d_name, "carrier") ||
		    !integer(file, &carrier)) {
			all_down = false;
			continue;
		}
		if (carrier == 1) up = true;
		if (carrier != 0) all_down = false;
	}
	free_entries(list, count);
	if (up)
		fputs("{\"state\":\"read-only\",\"value\":\"link-up\",\"label\":\"Network link available\"}", stdout);
	else if (links && all_down)
		fputs("{\"state\":\"read-only\",\"value\":\"disconnected\",\"label\":\"No network link\"}", stdout);
	else
		fputs("{\"state\":\"unavailable\",\"value\":null,\"label\":\"Network state unavailable\"}", stdout);
}

static void brightness(const char *root) {
	struct dirent **list = NULL;
	int count = entries(root, "backlight", &list);
	char maximum_path[4096], actual_path[4096], writable_path[4096];
	uint64_t maximum, actual;
	bool valid = count == 1 &&
		path(maximum_path, sizeof(maximum_path), root, "backlight", list[0]->d_name, "max_brightness") &&
		path(actual_path, sizeof(actual_path), root, "backlight", list[0]->d_name, "actual_brightness") &&
		path(writable_path, sizeof(writable_path), root, "backlight", list[0]->d_name, "brightness") &&
		integer(maximum_path, &maximum) && integer(actual_path, &actual) &&
		maximum > 0 && actual <= maximum;
	free_entries(list, count);
	if (!valid) {
		fputs("{\"state\":\"unavailable\",\"value\":null,\"label\":\"Brightness control unavailable\"}", stdout);
		return;
	}
	/* Python round(actual * 100 / maximum): nearest, with ties to even.
	 * Values are bounded to ten decimal digits, so these products fit. */
	uint64_t numerator = actual * 100;
	uint64_t percent = numerator / maximum, remainder = numerator % maximum;
	if (remainder * 2 > maximum || (remainder * 2 == maximum && percent % 2)) ++percent;
	printf("{\"state\":\"%s\",\"value\":%" PRIu64 ",\"label\":\"Brightness\",\"unit\":\"percent\"}",
	       access(writable_path, W_OK) == 0 ? "writable" : "read-only", percent);
}

/* `pgrep -u UID -x wvkbd-mobintl` without pgrep. procps's pgrep cost about
 * 79 ms of CPU per call on the board (every /proc entry read in full, plus
 * gconv setup for its regex), on the one CPU the shade animates on. This
 * reads each process's comm, and its status only for a name match. pgrep -u
 * matches the effective UID, the second Uid: field. */
static bool keyboard_running(const char *proc, uintmax_t uid) {
	DIR *dir = opendir(proc);
	if (!dir) return false;
	bool found = false;
	struct dirent *entry;
	while (!found && (entry = readdir(dir))) {
		const char *pid = entry->d_name;
		if (!*pid || strspn(pid, "0123456789") != strlen(pid)) continue;
		char path[512], line[256];
		if (snprintf(path, sizeof(path), "%s/%s/comm", proc, pid) >= (int)sizeof(path)) continue;
		FILE *f = fopen(path, "r");
		if (!f) continue;
		bool named = fgets(line, sizeof(line), f) && !strcmp(line, "wvkbd-mobintl\n");
		fclose(f);
		if (!named) continue;
		if (snprintf(path, sizeof(path), "%s/%s/status", proc, pid) >= (int)sizeof(path)) continue;
		if (!(f = fopen(path, "r"))) continue;
		while (fgets(line, sizeof(line), f)) {
			uintmax_t real, effective;
			if (!strncmp(line, "Uid:", 4)) {
				found = sscanf(line + 4, "%ju %ju", &real, &effective) == 2 && effective == uid;
				break;
			}
		}
		fclose(f);
	}
	closedir(dir);
	return found;
}

static int print_status(const char *root, bool keyboard, const char *motion) {
	fputs("{\"schema\":1,\"controls\":{\"network\":", stdout);
	network(root);
	fputs(",\"brightness\":", stdout);
	brightness(root);
	printf(",\"keyboard\":{\"state\":\"%s\",\"value\":null,\"label\":\"Show or hide\",\"action\":%s}",
	       keyboard ? "action" : "unavailable", keyboard ? "\"keyboard-toggle\"" : "null");
	bool known = motion && (!strcmp(motion, "0") || !strcmp(motion, "1"));
	printf(",\"motion\":{\"state\":\"%s\",\"value\":%s,\"label\":\"Reduced motion\",\"detail\":\"Fewer animations\"}}}\n",
	       known ? "read-only" : "unavailable", known ? (!strcmp(motion, "1") ? "true" : "false") : "null");
	return fflush(stdout) == 0 && !ferror(stdout) ? 0 : 1;
}

int main(void) {
	return print_status("/sys", keyboard_running("/proc", (uintmax_t)getuid()),
	                    getenv("K230_SETTINGS_REDUCED_MOTION"));
}
