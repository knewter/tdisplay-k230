#ifndef SWAY_CARD_SHELL_ROUTE_H
#define SWAY_CARD_SHELL_ROUTE_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
/* Normalized absolute touch includes 1.0; output rectangles are half-open.
 * Admit exactly that endpoint without pulling off-output coordinates inside. */
double card_shell_touch_output_coordinate(double coordinate, double extent);
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
/* Side-edge contextual Back. An inward swipe that starts in a side band
 * dismisses the topmost shell context; it never becomes a key event for an
 * application. The sheet lives on the Rust Home surface and the overlay
 * routes (Settings, shade, drawer) on the Rust overlay, so the compositor
 * only decides which one to ask. direction is +1 for the left edge (inward
 * is +x) and -1 for the right edge (inward is -x). */
struct card_shell_side_gesture {
	unsigned contacts;
	int32_t owner;
	int direction;
	bool cancelled, armed;
	double x, y;
};
int card_shell_side_direction(double x, double width, double band);
void card_shell_side_down(struct card_shell_side_gesture *gesture,
		int32_t id, double x, double y, int direction);
void card_shell_side_motion(struct card_shell_side_gesture *gesture,
		int32_t id, double x, double y, double distance);
bool card_shell_side_up(struct card_shell_side_gesture *gesture, int32_t id);
void card_shell_side_cancel(struct card_shell_side_gesture *gesture);
/* True when a motion from (x0, y0) to (x, y) is an inward side swipe, so the
 * recognizer may stop forwarding the touch to the client under it. */
bool card_shell_side_inward(int direction, double x0, double y0, double x, double y);

/* What one accepted side-edge Back dismisses, in the order the shell
 * unwinds: the long-press sheet, then Settings/shade/drawer, then the
 * keyboard. CARD_BACK_NONE means app content keeps the gesture alone. */
enum card_shell_back_target {
	CARD_BACK_NONE, CARD_BACK_SHEET, CARD_BACK_OVERLAY, CARD_BACK_KEYBOARD,
};
enum card_shell_back_target card_shell_back_target(bool sheet, bool overlay, bool keyboard);

/* The single touch-down decision. Order: a keyboard hit, then the bottom
 * Home/drawer band, then the top shade band, then a qualified side band that
 * has a shell context to dismiss, then the deck, then app content. */
enum card_shell_owner {
	CARD_OWNER_APP, CARD_OWNER_KEYBOARD, CARD_OWNER_HOME, CARD_OWNER_SHADE,
	CARD_OWNER_BACK, CARD_OWNER_DECK,
};
struct card_shell_ownership {
	double x, y, width, height, edge_band, bottom_reserved;
	bool keyboard_hit, deck, sheet, overlay, keyboard_shown;
};
enum card_shell_owner card_shell_touch_owner(const struct card_shell_ownership *touch);
const char *card_shell_owner_name(enum card_shell_owner owner);

/* Opt-in persistent Rust-client reveal stream. All I/O is nonblocking and
 * bounded; compositor input remains the sole owner of this touch sequence. */
struct card_shell_reveal_stream {
	int fd;
	bool active, connecting, terminal, shade, dismiss;
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
