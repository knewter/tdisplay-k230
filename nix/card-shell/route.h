#ifndef SWAY_CARD_SHELL_ROUTE_H
#define SWAY_CARD_SHELL_ROUTE_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
struct card_shell_drawer_gesture {
	unsigned contacts;
	int32_t owner;
	bool cancelled, armed;
	double x, y;
};
void card_shell_drawer_down(struct card_shell_drawer_gesture *gesture,
		int32_t id, double x, double y);
void card_shell_drawer_motion(struct card_shell_drawer_gesture *gesture,
		int32_t id, double x, double y, double distance);
void card_shell_shade_motion(struct card_shell_drawer_gesture *gesture,
		int32_t id, double x, double y, double distance);
bool card_shell_drawer_up(struct card_shell_drawer_gesture *gesture, int32_t id);
void card_shell_drawer_cancel(struct card_shell_drawer_gesture *gesture);
/* Opt-in persistent Rust-client reveal stream. All I/O is nonblocking and
 * bounded; compositor input remains the sole owner of this touch sequence. */
struct card_shell_reveal_stream {
	int fd;
	bool active, connecting, terminal, shade;
	uint64_t seq, deadline_ms;
	char current[128], update[128], end[128];
	size_t current_len, current_pos, update_len, end_len;
};
bool card_shell_reveal_enabled(void);
bool card_shell_reveal_begin(struct card_shell_reveal_stream *stream, const char *surface);
bool card_shell_reveal_update(struct card_shell_reveal_stream *stream, uint16_t progress);
bool card_shell_reveal_finish(struct card_shell_reveal_stream *stream, bool open);
void card_shell_reveal_cancel(struct card_shell_reveal_stream *stream);
void card_shell_reveal_abort(struct card_shell_reveal_stream *stream);
bool card_shell_reveal_pump(struct card_shell_reveal_stream *stream);
uint16_t card_shell_reveal_progress(const struct card_shell_drawer_gesture *gesture,
		double x, double y, double travel, bool shade);
/* Spawns one trusted, absolute helper path with fixed arguments. Never waits
 * inside the compositor event loop for the layer client to map. */
bool card_shell_launch_surface(const char *surface);
#endif
