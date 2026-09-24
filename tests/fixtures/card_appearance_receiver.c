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
int main(int argc, char **argv) {
	if (argc != 4 || !card_appearance_start(argv[1], argv[2], argv[3], apply, NULL)) return 2;
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
