#include "sway/card_shell_route.h"
#include <limits.h>
#include <math.h>
#include <spawn.h>
#include <stdlib.h>
#include <string.h>

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

bool card_shell_launch_drawer(void) {
	const char *path = getenv("SWAY_K230_CARD_DRAWER_HELPER");
	if (!path || path[0] != '/' || !path[1])
		return false;
	char *const argv[] = {(char *)path, "--surface", "drawer", NULL};
	pid_t pid;
	/* Sway ignores SIGCHLD, so an exited helper cannot leave a zombie. */
	return posix_spawn(&pid, path, NULL, NULL, argv, environ) == 0;
}
