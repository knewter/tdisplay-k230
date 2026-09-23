#ifndef SWAY_K230_CARD_H
#define SWAY_K230_CARD_H
#include <stdbool.h>
#include <stdint.h>
struct wlr_scene_buffer;
struct sway_view;
struct sway_output;
struct sway_seat;
void k230_card_observe(struct sway_view *view);
void k230_card_unmap(struct sway_view *view);
void k230_card_prepare(struct sway_output *output);
void k230_card_frame(struct wlr_scene_buffer *buffer);
void k230_card_present(struct sway_output *output, bool presented);
bool k230_card_down(struct sway_seat *seat, int32_t id, double x, double y);
bool k230_card_motion(struct sway_seat *seat, int32_t id, double x, double y);
bool k230_card_up(struct sway_seat *seat, int32_t id);
bool k230_card_cancel(struct sway_seat *seat);
#endif
