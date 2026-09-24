#ifndef K230_APPEARANCE_H
#define K230_APPEARANCE_H

#include <stdbool.h>
#include <stdint.h>

struct k230_appearance_colors {
  uint32_t background, foreground, muted, tile, selected, accent;
};

extern struct k230_appearance_colors k230_appearance;
uint32_t k230_appearance_error(void);

#define K230_APPEARANCE_MAX_STOPS 4
struct k230_appearance_stop {
  uint32_t argb;             /* Straight alpha, 0xAARRGGBB. */
  double offset;             /* 0..1 in authored stop order. */
};
struct k230_appearance_brush {
  unsigned stop_count;       /* 0 means the token is unavailable. */
  struct k230_appearance_stop stops[K230_APPEARANCE_MAX_STOPS];
  double angle_degrees;     /* 0 for a solid, authored angle for gradients. */
  double alpha;             /* Companion *-alpha, multiplied by stop alpha. */
};
struct k230_appearance_border {
  struct k230_appearance_brush brush;
  double width[4];          /* Top, right, bottom, left; logical px. */
};

/* Section/key names match generated shell.toml, e.g. "launcher" and
 * "selected-background". Functions return false for absent/invalid tokens;
 * the caller keeps its legible fallback. Returned strings remain valid until
 * the next committed generation or stop. */
bool k230_appearance_brush(const char *section, const char *key,
                           struct k230_appearance_brush *out);
bool k230_appearance_border(const char *section, const char *key,
                            struct k230_appearance_border *out);
bool k230_appearance_number(const char *section, const char *key, double *out);
const char *k230_appearance_icon_theme(void);
const char *k230_appearance_background_path(void);
uint64_t k230_appearance_generation_serial(void);

/* Optional receiver: a missing socket leaves the installed palette intact. */
int k230_appearance_start(const char *runtime, const char *state_root,
                          const char *default_generation);
int k230_appearance_listener_fd(void);
int k230_appearance_client_fd(void);
void k230_appearance_service(bool listener_ready, bool client_ready,
                             bool (*redraw)(void));
void k230_appearance_stop(void);

#endif
