#ifndef CARD_SHELL_TELEMETRY_H
#define CARD_SHELL_TELEMETRY_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
struct sway_output;
struct wlr_output_event_present;
bool card_bench_arm(struct sway_output *output, const char *source, size_t cards);
void card_bench_stop(void);
void card_bench_phase(bool active, size_t cards);
void card_bench_resource(bool active);
void card_bench_input_begin(uint64_t gesture, const char *kind, bool injected);
/* Device monotonic origin, separate from dispatch-time input rows. */
void card_bench_input_origin(uint64_t source_ns);
void card_bench_input_end(bool consumed, bool final);
enum card_bench_input_stage { CARD_BENCH_POLICY, CARD_BENCH_SCENE, CARD_BENCH_CHROME };
uint64_t card_bench_input_stage_begin(void);
void card_bench_input_stage_end(enum card_bench_input_stage stage, uint64_t start);
void card_bench_work_begin(void);
void card_bench_work_end(void);
void card_bench_render_begin(struct sway_output *output);
enum card_bench_render_stage { CARD_BENCH_PREPARE, CARD_BENCH_BUILD, CARD_BENCH_COMMIT };
void card_bench_render_stage(struct sway_output *output, enum card_bench_render_stage stage);
void card_bench_commit_begin(struct sway_output *output);
void card_bench_render_end(struct sway_output *output, bool success);
/* Diagnostic only: logs the exact damage region wlr_scene_output_build_state
 * computed for this frame (output-buffer-local), so a host or board capture
 * can measure whether card motion damages the whole output or just the
 * moving cards' rects. Takes plain integers (already reduced from the
 * pixman_region32_t at the call site) so this header and telemetry.c stay
 * free of a pixman dependency, matching every other function here. */
void card_bench_render_damage(struct sway_output *output, int rects, uint64_t damage_px,
		int bbox_x1, int bbox_y1, int bbox_x2, int bbox_y2);
void card_bench_present(struct sway_output *output, struct wlr_output_event_present *event);
#endif
