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
void card_bench_input_end(bool consumed, bool final);
void card_bench_work_begin(void);
void card_bench_work_end(void);
void card_bench_render_begin(struct sway_output *output);
void card_bench_commit_begin(struct sway_output *output);
void card_bench_render_end(struct sway_output *output, bool success);
void card_bench_present(struct sway_output *output, struct wlr_output_event_present *event);
#endif
