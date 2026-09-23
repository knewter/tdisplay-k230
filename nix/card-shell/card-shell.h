#ifndef SWAY_CARD_SHELL_H
#define SWAY_CARD_SHELL_H
#include <stdbool.h>
#include <stdint.h>
struct wlr_scene_buffer;
struct sway_view;
struct sway_output;
struct sway_seat;
struct wlr_touch;
void card_shell_observe(struct sway_view *view);
void card_shell_unmap(struct sway_view *view);
void card_shell_output_disable(struct sway_output *output);
void card_shell_prepare(struct sway_output *output);
void card_shell_frame(struct wlr_scene_buffer *buffer);
void card_shell_present(struct sway_output *output, bool presented);
bool card_shell_down(struct sway_seat *seat, struct wlr_touch *touch, int32_t id, double x, double y);
bool card_shell_motion(struct sway_seat *seat, struct wlr_touch *touch, int32_t id, double x, double y);
bool card_shell_up(struct sway_seat *seat, struct wlr_touch *touch, int32_t id);
bool card_shell_cancel(struct sway_seat *seat);
#endif
