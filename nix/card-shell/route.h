#ifndef SWAY_CARD_SHELL_ROUTE_H
#define SWAY_CARD_SHELL_ROUTE_H
#include <stdbool.h>
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
bool card_shell_drawer_up(struct card_shell_drawer_gesture *gesture, int32_t id);
void card_shell_drawer_cancel(struct card_shell_drawer_gesture *gesture);
/* Spawns one trusted, absolute helper path with fixed arguments. Never waits
 * inside the compositor event loop for the layer client to map. */
bool card_shell_launch_drawer(void);
#endif
