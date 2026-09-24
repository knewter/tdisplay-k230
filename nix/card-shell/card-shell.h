#ifndef SWAY_CARD_SHELL_H
#define SWAY_CARD_SHELL_H
#include <stdbool.h>
#include <stdint.h>
struct wlr_scene_buffer;
struct wlr_box;
struct sway_view;
struct sway_output;
struct sway_seat;
struct wlr_touch;
void card_shell_observe(struct sway_view *view);
void card_shell_unmap(struct sway_view *view);
void card_shell_output_disable(struct sway_output *output);
void card_shell_prepare(struct sway_output *output);
void card_shell_usable_area_changed(struct sway_output *output);
void card_shell_keyboard_adjust_usable(struct sway_output *output, struct wlr_box *usable);
void card_shell_frame(struct wlr_scene_buffer *buffer);
void card_shell_present(struct sway_output *output, bool presented);
bool card_shell_down(struct sway_seat *seat, struct wlr_touch *touch, int32_t id, double x, double y, uint32_t time_msec);
bool card_shell_motion(struct sway_seat *seat, struct wlr_touch *touch, int32_t id, double x, double y, uint32_t time_msec);
bool card_shell_up(struct sway_seat *seat, struct wlr_touch *touch, int32_t id, uint32_t time_msec);
bool card_shell_cancel(struct sway_seat *seat);
#endif
