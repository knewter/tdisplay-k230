#include "sway/card_shell_route.h"
#include <errno.h>
#include <limits.h>
#include <math.h>
#include <stddef.h>
#include <poll.h>
#include <spawn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <time.h>
#include <unistd.h>

extern char **environ;

void card_shell_drawer_down(struct card_shell_drawer_gesture *gesture,
		int32_t id, double x, double y) {
	if (gesture->contacts) {
		if (gesture->contacts < UINT_MAX)
			gesture->contacts++;
		card_shell_drawer_cancel(gesture);
		return;
	}
	*gesture = (struct card_shell_drawer_gesture){
		.contacts = 1, .owner = id, .x = x, .y = y,
	};
}

void card_shell_drawer_motion(struct card_shell_drawer_gesture *gesture,
		int32_t id, double x, double y, double distance) {
	if (gesture->contacts && !gesture->cancelled && id == gesture->owner)
		gesture->armed = isfinite(x) && isfinite(y) &&
			gesture->y - y >= distance && gesture->y - y > fabs(x - gesture->x);
}

void card_shell_shade_motion(struct card_shell_drawer_gesture *gesture,
		int32_t id, double x, double y, double distance) {
	if (gesture->contacts && !gesture->cancelled && id == gesture->owner)
		gesture->armed = isfinite(x) && isfinite(y) &&
			y - gesture->y >= distance && y - gesture->y > fabs(x - gesture->x);
}

bool card_shell_drawer_up(struct card_shell_drawer_gesture *gesture, int32_t id) {
	if (!gesture->contacts)
		return false;
	bool launch = gesture->contacts == 1 && id == gesture->owner &&
		gesture->armed && !gesture->cancelled;
	gesture->contacts--;
	if (!gesture->contacts)
		memset(gesture, 0, sizeof(*gesture));
	return launch;
}

void card_shell_drawer_cancel(struct card_shell_drawer_gesture *gesture) {
	gesture->cancelled = true;
	gesture->armed = false;
}

static uint64_t route_ms(void) {
	struct timespec now;
	clock_gettime(CLOCK_MONOTONIC, &now);
	return (uint64_t)now.tv_sec * 1000 + now.tv_nsec / 1000000;
}

bool card_shell_reveal_enabled(void) {
	const char *value = getenv("SWAY_K230_CARD_REVEAL_STREAM");
	return value && strcmp(value, "1") == 0;
}

void card_shell_reveal_abort(struct card_shell_reveal_stream *stream) {
	if (stream->active && stream->fd >= 0)
		close(stream->fd);
	memset(stream, 0, sizeof(*stream));
}

static bool frame(char *out, size_t capacity, const struct card_shell_reveal_stream *stream,
		const char *phase, uint16_t progress, size_t *length) {
	int n = snprintf(out, capacity,
		"{\"v\":1,\"kind\":\"reveal\",\"surface\":\"%s\",\"phase\":\"%s\","
		"\"seq\":%llu,\"progress\":%u}\n",
		stream->shade ? "shade" : "drawer", phase,
		(unsigned long long)stream->seq, progress);
	if (n < 0 || (size_t)n >= capacity)
		return false;
	*length = (size_t)n;
	return true;
}

bool card_shell_reveal_pump(struct card_shell_reveal_stream *stream) {
	if (!stream->active)
		return false;
	if ((stream->connecting || stream->current_len || stream->update_len || stream->end_len) &&
		route_ms() > stream->deadline_ms) {
		card_shell_reveal_abort(stream);
		return false;
	}
	if (stream->connecting) {
		struct pollfd ready = {.fd = stream->fd, .events = POLLOUT};
		int result = poll(&ready, 1, 0);
		if (result < 0 && errno == EINTR)
			return true;
		if (result < 0 || (result > 0 && (ready.revents & (POLLERR | POLLHUP | POLLNVAL)))) {
			card_shell_reveal_abort(stream);
			return false;
		}
		if (!result)
			return true;
		int error = 0;
		socklen_t size = sizeof(error);
		if (getsockopt(stream->fd, SOL_SOCKET, SO_ERROR, &error, &size) || error) {
			card_shell_reveal_abort(stream);
			return false;
		}
		stream->connecting = false;
	}
	for (unsigned count = 0; count < 3; count++) {
		if (!stream->current_len) {
			if (stream->update_len) {
				memcpy(stream->current, stream->update, stream->update_len);
				stream->current_len = stream->update_len;
				stream->update_len = 0;
			} else if (stream->end_len) {
				memcpy(stream->current, stream->end, stream->end_len);
				stream->current_len = stream->end_len;
				stream->end_len = 0;
			} else if (stream->terminal) {
				card_shell_reveal_abort(stream);
				return true;
			} else {
				return true;
			}
			stream->current_pos = 0;
		}
		ssize_t n = send(stream->fd, stream->current + stream->current_pos,
			stream->current_len - stream->current_pos, MSG_DONTWAIT | MSG_NOSIGNAL);
		if (n < 0 && errno == EINTR)
			return true;
		if (n < 0 && (errno == EAGAIN || errno == EWOULDBLOCK))
			return true;
		if (n <= 0) {
			card_shell_reveal_abort(stream);
			return false;
		}
		stream->current_pos += (size_t)n;
		if (stream->current_pos < stream->current_len)
			return true;
		stream->current_len = stream->current_pos = 0;
	}
	return true;
}

bool card_shell_reveal_begin(struct card_shell_reveal_stream *stream, const char *surface) {
	if (!card_shell_reveal_enabled() || !surface ||
		(strcmp(surface, "drawer") != 0 && strcmp(surface, "shade") != 0))
		return false;
	card_shell_reveal_abort(stream);
	const char *runtime = getenv("XDG_RUNTIME_DIR");
	struct stat metadata;
	if (!runtime || runtime[0] != '/' || stat(runtime, &metadata) ||
		!S_ISDIR(metadata.st_mode) || metadata.st_uid != geteuid() ||
		(metadata.st_mode & 0077))
		return false;
	struct sockaddr_un address = {.sun_family = AF_UNIX};
	char expected[sizeof(address.sun_path)];
	int path_length = snprintf(expected, sizeof(expected),
		"%s/k230-shell-rust.sock", runtime);
	if (path_length <= 0 || (size_t)path_length >= sizeof(address.sun_path))
		return false;
	const char *configured = getenv("SWAY_K230_CARD_SURFACE_SOCKET");
	if (configured && strcmp(configured, expected) != 0)
		return false;
	struct stat socket_metadata;
	if (lstat(expected, &socket_metadata) || !S_ISSOCK(socket_metadata.st_mode) ||
		socket_metadata.st_uid != geteuid() || (socket_metadata.st_mode & 0077))
		return false;
	memcpy(address.sun_path, expected, (size_t)path_length + 1);
	int fd = socket(AF_UNIX, SOCK_STREAM | SOCK_NONBLOCK | SOCK_CLOEXEC, 0);
	if (fd < 0)
		return false;
	int result = connect(fd, (struct sockaddr *)&address,
		offsetof(struct sockaddr_un, sun_path) + (size_t)path_length + 1);
	if (result < 0 && errno != EINPROGRESS) {
		close(fd);
		return false;
	}
	static uint64_t next_seq;
	if (!next_seq)
		next_seq = ((uint64_t)getpid() << 32) ^ (route_ms() << 12);
	stream->fd = fd;
	stream->active = true;
	stream->connecting = result < 0;
	stream->shade = strcmp(surface, "shade") == 0;
	stream->seq = ++next_seq;
	stream->deadline_ms = route_ms() + 500;
	if (!frame(stream->current, sizeof(stream->current), stream, "begin", 0,
			&stream->current_len)) {
		card_shell_reveal_abort(stream);
		return false;
	}
	return card_shell_reveal_pump(stream);
}

bool card_shell_reveal_update(struct card_shell_reveal_stream *stream, uint16_t progress) {
	if (!stream->active || stream->terminal || progress > 1000)
		return false;
	stream->deadline_ms = route_ms() + 500;
	if (!frame(stream->update, sizeof(stream->update), stream, "update", progress,
			&stream->update_len)) {
		card_shell_reveal_abort(stream);
		return false;
	}
	return card_shell_reveal_pump(stream);
}

static bool end_reveal(struct card_shell_reveal_stream *stream,
		const char *phase, uint16_t progress) {
	if (!stream->active || stream->terminal)
		return false;
	stream->terminal = true;
	stream->deadline_ms = route_ms() + 500;
	if (!frame(stream->end, sizeof(stream->end), stream, phase, progress,
			&stream->end_len)) {
		card_shell_reveal_abort(stream);
		return false;
	}
	return card_shell_reveal_pump(stream);
}

bool card_shell_reveal_finish(struct card_shell_reveal_stream *stream, bool open) {
	return end_reveal(stream, "finish", open ? 1000 : 0);
}

void card_shell_reveal_cancel(struct card_shell_reveal_stream *stream) {
	(void)end_reveal(stream, "cancel", 0);
}

uint16_t card_shell_reveal_progress(const struct card_shell_drawer_gesture *gesture,
		double x, double y, double travel, bool shade) {
	if (!gesture->contacts || gesture->cancelled || !isfinite(x) || !isfinite(y) ||
		!isfinite(travel) || travel <= 0)
		return 0;
	double vertical = shade ? y - gesture->y : gesture->y - y;
	/* This stream already owns the contact. Direction qualification belongs
	 * to the release decision, not its visible position: crossing a diagonal
	 * must not teleport an in-progress panel back to the edge. */
	return (uint16_t)lround(fmin(1000, fmax(0, vertical / travel * 1000)));
}

bool card_shell_launch_surface(const char *surface) {
	if (!surface || (strcmp(surface, "drawer") != 0 && strcmp(surface, "shade") != 0))
		return false;
	const char *path = getenv("SWAY_K230_CARD_SURFACE_HELPER");
	if (!path)
		path = getenv("SWAY_K230_CARD_DRAWER_HELPER");
	if (!path || path[0] != '/' || !path[1])
		return false;
	char *const argv[] = {(char *)path, "--surface", (char *)surface, NULL};
	pid_t pid;
	/* Sway ignores SIGCHLD, so an exited helper cannot leave a zombie. */
	return posix_spawn(&pid, path, NULL, NULL, argv, environ) == 0;
}
