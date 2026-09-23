#ifndef K230_LAUNCHER_GESTURE_H
#define K230_LAUNCHER_GESTURE_H

#include <stdbool.h>

enum gesture_direction {
  GESTURE_NONE,
  GESTURE_LEFT,
  GESTURE_RIGHT,
  GESTURE_UP,
  GESTURE_DOWN,
  GESTURE_CANCELLED,
};

struct launcher_gesture {
  int id, start_x, start_y;
  bool active, rejected;
  enum gesture_direction direction;
};

static int gesture_abs(int value) { return value < 0 ? -value : value; }

static void gesture_begin(struct launcher_gesture *gesture, int id, int x, int y) {
  gesture->id = id;
  gesture->start_x = x;
  gesture->start_y = y;
  gesture->active = true;
  gesture->rejected = false;
  gesture->direction = GESTURE_NONE;
}

static void gesture_reject(struct launcher_gesture *gesture) {
  if (gesture->active) {
    gesture->rejected = true;
    gesture->direction = GESTURE_CANCELLED;
  }
}

static void gesture_motion(struct launcher_gesture *gesture, int id, int x, int y) {
  int dx, dy, horizontal, vertical;

  if (!gesture->active || gesture->rejected || id != gesture->id ||
      gesture->direction != GESTURE_NONE)
    return;
  dx = x - gesture->start_x;
  dy = y - gesture->start_y;
  horizontal = gesture_abs(dx);
  vertical = gesture_abs(dy);
  if (horizontal * horizontal + vertical * vertical < 48 * 48)
    return;
  if (horizontal * 4 >= vertical * 5)
    gesture->direction = dx < 0 ? GESTURE_LEFT : GESTURE_RIGHT;
  else if (vertical * 4 >= horizontal * 5)
    gesture->direction = dy < 0 ? GESTURE_UP : GESTURE_DOWN;
  else
    gesture_reject(gesture);
}

static enum gesture_direction gesture_release(struct launcher_gesture *gesture, int id) {
  enum gesture_direction direction = GESTURE_CANCELLED;

  if (gesture->active && id == gesture->id)
    direction = gesture->direction;
  gesture->active = false;
  gesture->rejected = false;
  gesture->direction = GESTURE_NONE;
  gesture->id = -1;
  return direction;
}
#endif
