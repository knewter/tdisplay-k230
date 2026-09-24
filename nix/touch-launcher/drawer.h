#ifndef K230_LAUNCHER_DRAWER_H
#define K230_LAUNCHER_DRAWER_H

#include <stdbool.h>
#include <stdint.h>

/* Geometry and touch state for a continuous installed-app list. The caller
 * owns rendering and the desktop-entry identities; this model never pages or
 * activates an item merely because a flick was stopped. */
struct shell_drawer {
  int viewport, content, offset;
  int pointer_id, down_y, last_y, start_offset;
  int64_t down_ms, last_ms;
  double velocity;
  bool tracking, moved, suppress_tap, holding, cancelled;
};

static inline int drawer_limit(const struct shell_drawer *d) {
  return d->content > d->viewport ? d->content - d->viewport : 0;
}
static inline int drawer_clamp(const struct shell_drawer *d, int value) {
  if (value < 0) return 0;
  int limit = drawer_limit(d);
  return value > limit ? limit : value;
}
static inline void drawer_geometry(struct shell_drawer *d, int viewport, int content) {
  d->viewport = viewport > 0 ? viewport : 1;
  d->content = content > 0 ? content : 0;
  d->offset = drawer_clamp(d, d->offset);
}
static inline void drawer_cancel(struct shell_drawer *d) {
  d->tracking = false;
  d->holding = false;
  d->cancelled = true;
  d->suppress_tap = true;
  d->velocity = 0;
  d->pointer_id = -1;
}
static inline bool drawer_begin(struct shell_drawer *d, int id, int y, int64_t ms) {
  if (d->tracking) { drawer_cancel(d); return false; }
  bool stopping = d->velocity > 0.05 || d->velocity < -0.05;
  d->velocity = 0;
  d->tracking = true;
  d->pointer_id = id;
  d->down_y = d->last_y = y;
  d->down_ms = d->last_ms = ms;
  d->start_offset = d->offset;
  d->moved = d->holding = d->cancelled = false;
  d->suppress_tap = stopping;
  return true;
}
static inline bool drawer_move(struct shell_drawer *d, int id, int y, int64_t ms) {
  if (!d->tracking || d->cancelled || id != d->pointer_id) return false;
  int distance = y - d->down_y;
  if (distance > 12 || distance < -12) d->moved = true;
  if (!d->moved) return false;
  int before = d->offset;
  d->offset = drawer_clamp(d, d->start_offset - distance);
  int64_t dt = ms - d->last_ms;
  if (dt > 0 && dt < 250) {
    double sample = (double)(d->last_y - y) / (double)dt;
    if (sample > 2.5) sample = 2.5;
    if (sample < -2.5) sample = -2.5;
    d->velocity = (d->velocity * 0.45) + (sample * 0.55);
  }
  d->last_y = y;
  d->last_ms = ms;
  d->holding = false;
  return before != d->offset;
}
static inline bool drawer_press_cue(struct shell_drawer *d, int id, int64_t ms) {
  return d->tracking && !d->moved && !d->cancelled && !d->suppress_tap &&
    id == d->pointer_id && ms - d->down_ms >= 250;
}
static inline bool drawer_long_press(struct shell_drawer *d, int id, int64_t ms) {
  if (!drawer_press_cue(d, id, ms) || ms - d->down_ms < 500) return false;
  d->holding = true;
  d->suppress_tap = true;
  d->velocity = 0;
  return true;
}
/* True means a clean, stationary tap. A hold, scroll, second contact, or a
 * touch that merely stopped a flick must never launch an application. */
static inline bool drawer_release(struct shell_drawer *d, int id) {
  if (!d->tracking || id != d->pointer_id) return false;
  bool tap = !d->moved && !d->suppress_tap && !d->cancelled && !d->holding;
  d->tracking = false;
  d->pointer_id = -1;
  if (!d->moved) d->velocity = 0;
  return tap;
}
static inline bool drawer_tick(struct shell_drawer *d, int elapsed_ms) {
  if (d->tracking || elapsed_ms <= 0 || (d->velocity < 0.05 && d->velocity > -0.05)) {
    d->velocity = 0;
    return false;
  }
  int before = d->offset;
  d->offset = drawer_clamp(d, d->offset + (int)(d->velocity * elapsed_ms));
  if (d->offset == 0 || d->offset == drawer_limit(d)) d->velocity = 0;
  else {
    double friction = 1.0 - (double)elapsed_ms / 160.0;
    if (friction < 0) friction = 0;
    d->velocity *= friction;
  }
  return before != d->offset;
}

#endif
