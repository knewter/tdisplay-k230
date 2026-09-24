#ifndef K230_APPEARANCE_H
#define K230_APPEARANCE_H

#include <stdbool.h>
#include <stdint.h>

struct k230_appearance_colors {
  uint32_t background, foreground, muted, tile, selected, accent;
};

extern struct k230_appearance_colors k230_appearance;
uint32_t k230_appearance_error(void);

/* Optional receiver: a missing socket leaves the installed palette intact. */
int k230_appearance_start(const char *runtime);
int k230_appearance_listener_fd(void);
int k230_appearance_client_fd(void);
void k230_appearance_service(bool listener_ready, bool client_ready,
                             bool (*redraw)(void));
void k230_appearance_stop(void);

#endif
