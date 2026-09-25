#define _POSIX_C_SOURCE 200809L
#include "sway/card_shell_appearance.h"
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

static volatile sig_atomic_t running = 1;
static void stop(int signal_number) { (void)signal_number; running = 0; }
static bool apply(const struct card_appearance *appearance, void *unused) {
	(void)unused;
	printf("APPLY %s %zu %zu %d\n", appearance->generation,
		appearance->card.count, appearance->selected.count, appearance->wallpaper);
	fflush(stdout);
	return true;
}
/* Task 3.1b's advisory warm-up hook: this harness has no real scene graph to
 * warm, so it only proves the hook fires, with the fully validated
 * candidate, before that prepare's own ack -- see
 * test_card_shell_appearance.py's assertions on this line's ordering. */
static void prepare_candidate(const struct card_appearance *appearance, void *unused) {
	(void)unused;
	printf("PREPARE %s %zu %zu %d\n", appearance->generation,
		appearance->card.count, appearance->selected.count, appearance->wallpaper);
	fflush(stdout);
}
int main(int argc, char **argv) {
	if (argc != 4 ||
		!card_appearance_start(argv[1], argv[2], argv[3], apply, prepare_candidate, NULL))
		return 2;
	signal(SIGTERM, stop);
	puts("READY"); fflush(stdout);
	while (running) {
		card_appearance_poll();
		struct timespec pause = {.tv_nsec = 5000000};
		nanosleep(&pause, NULL);
	}
	card_appearance_stop();
	return 0;
}
