#include "log.h"
#include "sway/card_shell_telemetry.h"
#include "sway/output.h"
#include <drm_fourcc.h>
#include <inttypes.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <wlr/backend/drm.h>
#include <wlr/backend/headless.h>
struct input {
	uint64_t id;
	bool final;
};
static struct {
	bool armed, ever_active, header_sent, in_input;
	char backend[9], format[16], input[9];
	struct sway_output *output;
	unsigned work_depth;
	uint64_t work_cpu;
	uint64_t input_cpu_start, input_cpu, render_cpu_start, render_cpu;
	uint64_t input_stage_cpu[3];
	bool in_render;
	enum card_bench_render_stage render_stage;
	uint64_t stage_cpu_start, stage_cpu[3], render_attempts, failed_attempts;
	uint64_t submit_time;
	uint64_t run, next_input, input_time, input_gesture, charged_cpu,
		last_resource;
	const char *kind, *source;
	struct input pending[1024];
	size_t count;
	char cgroup[PATH_MAX];
} bench;
static uint64_t stamp(clockid_t clock) {
	struct timespec t;
	if (clock_gettime(clock, &t) != 0)
		return 0;
	return (uint64_t)t.tv_sec * 1000000000 + t.tv_nsec;
}
static bool number_file(const char *path, uint64_t *out) {
	FILE *f = fopen(path, "r");
	if (!f)
		return false;
	int ok = fscanf(f, "%" SCNu64, out);
	fclose(f);
	return ok == 1;
}
static void emit_resource(const char *phase, uint64_t now, uint64_t cpu, uint64_t memory,
						  const char *scope) {
	sway_log(SWAY_INFO,
			 "K230_CARD_BENCH v=1 run=%" PRIu64 " event=resource phase=%s t_ns=%" PRIu64
			 " cpu_ns=%" PRIu64 " memory_bytes=%" PRIu64 " scope=%s",
			 bench.run, phase, now, cpu, memory, scope);
}
void card_bench_resource(bool active) {
	if (!bench.armed)
		return;
	uint64_t now = stamp(CLOCK_MONOTONIC);
	if (now - bench.last_resource < 1000000000)
		return;
	bench.last_resource = now;
	if (active)
		bench.ever_active = true;
	const char *phase = active ? "active" : bench.ever_active ? "restored" : "baseline";
	FILE *f = fopen("/proc/self/statm", "r");
	unsigned long total, resident;
	if (f) {
		if (fscanf(f, "%lu %lu", &total, &resident) == 2)
			emit_resource(phase, now, stamp(CLOCK_PROCESS_CPUTIME_ID),
						  (uint64_t)resident * sysconf(_SC_PAGESIZE), "compositor");
		fclose(f);
	}
	if (*bench.cgroup) {
		char path[PATH_MAX];
		uint64_t memory, cpu = 0;
		int n = snprintf(path, sizeof(path), "%s/memory.current", bench.cgroup);
		if (n < 0 || n >= (int)sizeof(path) || !number_file(path, &memory))
			return;
		n = snprintf(path, sizeof(path), "%s/cpu.stat", bench.cgroup);
		if (n < 0 || n >= (int)sizeof(path))
			return;
		f = fopen(path, "r");
		if (!f)
			return;
		char key[80];
		uint64_t value;
		while (fscanf(f, "%79s %" SCNu64, key, &value) == 2)
			if (strcmp(key, "usage_usec") == 0) {
				cpu = value * 1000;
				break;
			}
		fclose(f);
		if (cpu)
			emit_resource(phase, now, cpu, memory, "session");
	}
}
bool card_bench_arm(struct sway_output *output, const char *source, size_t cards) {
	if (strcmp(source, "physical") && strcmp(source, "injected"))
		return false;
	const char *backend = wlr_backend_is_drm(output->wlr_output->backend)		 ? "drm"
						  : wlr_backend_is_headless(output->wlr_output->backend) ? "headless"
																				 : NULL;
	if (!backend)
		return false;
	memset(&bench, 0, sizeof(bench));
	bench.armed = true;
	bench.output = output;
	bench.run = stamp(CLOCK_MONOTONIC);
	snprintf(bench.backend, sizeof(bench.backend), "%s", backend);
	snprintf(bench.input, sizeof(bench.input), "%s", source);
	const char *isolated = getenv("SWAY_K230_CARD_BENCH_CGROUP");
	if (isolated && strcmp(isolated, "1") == 0) {
		FILE *f = fopen("/proc/self/cgroup", "r");
		char line[PATH_MAX];
		if (f) {
			while (fgets(line, sizeof(line), f))
				if (strncmp(line, "0::/", 4) == 0) {
					line[strcspn(line, "\n")] = 0;
					int n =
						snprintf(bench.cgroup, sizeof(bench.cgroup), "/sys/fs/cgroup%s", line + 3);
					if (n < 0 || n >= (int)sizeof(bench.cgroup))
						*bench.cgroup = 0;
					break;
				}
			fclose(f);
		}
	}
	char format[16];
	uint32_t pixel = output->wlr_output->render_format;
	if (pixel == DRM_FORMAT_RGB565)
		snprintf(format, sizeof(format), "RGB565");
	else if (pixel == DRM_FORMAT_XRGB8888)
		snprintf(format, sizeof(format), "XRGB8888");
	else
		snprintf(format, sizeof(format), "%08x", pixel);
	snprintf(bench.format, sizeof(bench.format), "%s", format);
	card_bench_resource(false);
	return true;
}
void card_bench_phase(bool active, size_t cards) {
	if (!bench.armed)
		return;
	if (active && !bench.header_sent) {
		bench.header_sent = true;
		/* Native entry begins inside input handling. Use that input's start,
		 * keeping baseline resources before entry without a negative latency.
		 * IPC entry has no current input and uses the current monotonic time. */
		uint64_t entry = bench.in_input ? bench.input_time : stamp(CLOCK_MONOTONIC);
		sway_log(SWAY_INFO,
				 "K230_CARD_BENCH v=1 run=%" PRIu64 " event=session t_ns=%" PRIu64
				 " clock=monotonic backend=%s renderer=pixman width=%d height=%d "
				 "output_format=%s "
				 "input=%s cards=%zu",
				 bench.run, entry, bench.backend, bench.output->width, bench.output->height,
				 bench.format, bench.input, cards);
	}
	if (active)
		bench.ever_active = true;
}

void card_bench_stop(void) {
	bench.armed = false;
	bench.count = 0;
}
void card_bench_input_begin(uint64_t gesture, const char *kind, bool injected) {
	if (!bench.armed)
		return;
	card_bench_work_begin();
	bench.input_time = stamp(CLOCK_MONOTONIC);
	bench.input_cpu_start = stamp(CLOCK_PROCESS_CPUTIME_ID);
	memset(bench.input_stage_cpu, 0, sizeof(bench.input_stage_cpu));
	bench.in_input = true;
	bench.input_gesture = gesture;
	bench.kind = kind;
	bench.source = injected ? "injected" : "physical";
}
void card_bench_input_end(bool consumed, bool final) {
	uint64_t event_cpu = 0;
	if (bench.armed && bench.in_input) {
		event_cpu = stamp(CLOCK_PROCESS_CPUTIME_ID) - bench.input_cpu_start;
		bench.input_cpu += event_cpu;
	}
	card_bench_work_end();
	bench.in_input = false;
	if (!bench.armed || !consumed)
		return;
	uint64_t id = ++bench.next_input;
	/* One row per accepted event. The existing frame and input totals still
	 * include every stage clock and all other handler work. */
	sway_log(SWAY_INFO,
			"K230_CARD_SHELL input-cost run=%" PRIu64 " input_id=%" PRIu64
			" cpu_ns=%" PRIu64 " policy_cpu_ns=%" PRIu64
			" scene_cpu_ns=%" PRIu64 " chrome_cpu_ns=%" PRIu64,
			bench.run, id, event_cpu, bench.input_stage_cpu[CARD_BENCH_POLICY],
			bench.input_stage_cpu[CARD_BENCH_SCENE], bench.input_stage_cpu[CARD_BENCH_CHROME]);

	sway_log(SWAY_INFO,
			 "K230_CARD_BENCH v=1 run=%" PRIu64 " event=input input_id=%" PRIu64
			 " gesture_id=%" PRIu64 " kind=%s t_ns=%" PRIu64 " source=%s",
			 bench.run, id, bench.input_gesture, bench.kind, bench.input_time, bench.source);
	if (bench.count < 1024)
		bench.pending[bench.count++] = (struct input){id, final};
	else
		sway_log(SWAY_ERROR,
				 "K230_CARD_BENCH v=1 run=%" PRIu64 " event=incomplete reason=input-overflow",
				 bench.run);
}
uint64_t card_bench_input_stage_begin(void) {
	return bench.armed && bench.in_input ? stamp(CLOCK_PROCESS_CPUTIME_ID) : 0;
}
void card_bench_input_stage_end(enum card_bench_input_stage stage, uint64_t start) {
	if (start && bench.armed && bench.in_input && stage <= CARD_BENCH_CHROME)
		bench.input_stage_cpu[stage] += stamp(CLOCK_PROCESS_CPUTIME_ID) - start;
}
void card_bench_work_begin(void) {
	if (bench.armed && bench.work_depth++ == 0)
		bench.work_cpu = stamp(CLOCK_PROCESS_CPUTIME_ID);
}
void card_bench_work_end(void) {
	if (bench.armed && bench.work_depth && --bench.work_depth == 0)
		bench.charged_cpu += stamp(CLOCK_PROCESS_CPUTIME_ID) - bench.work_cpu;
}
void card_bench_render_begin(struct sway_output *output) {
	if (bench.armed && bench.output == output) {
		card_bench_work_begin();
		bench.render_cpu_start = stamp(CLOCK_PROCESS_CPUTIME_ID);
		bench.in_render = true;
		bench.render_stage = CARD_BENCH_PREPARE;
		bench.stage_cpu_start = bench.render_cpu_start;
		bench.render_attempts++;
	}
}
void card_bench_render_stage(struct sway_output *output, enum card_bench_render_stage stage) {
	if (!bench.armed || bench.output != output || !bench.in_render ||
		stage < bench.render_stage || stage > CARD_BENCH_COMMIT)
		return;
	uint64_t now = stamp(CLOCK_PROCESS_CPUTIME_ID);
	bench.stage_cpu[bench.render_stage] += now - bench.stage_cpu_start;
	bench.stage_cpu_start = now;
	bench.render_stage = stage;
}
void card_bench_commit_begin(struct sway_output *output) {
	if (bench.armed && bench.output == output) {
		card_bench_render_stage(output, CARD_BENCH_COMMIT);
		bench.submit_time = stamp(CLOCK_MONOTONIC);
	}
}
void card_bench_render_end(struct sway_output *output, bool success) {
	if (!bench.armed || bench.output != output)
		return;
	uint64_t end = stamp(CLOCK_PROCESS_CPUTIME_ID);
	bench.render_cpu += end - bench.render_cpu_start;
	bench.stage_cpu[bench.render_stage] += end - bench.stage_cpu_start;
	bench.in_render = false;
	card_bench_work_end();
	if (!success) {
		bench.failed_attempts++;
		return;
	}
	uint64_t now = bench.submit_time, frame = output->wlr_output->commit_seq;
	for (size_t i = 0; i < bench.count; i++)
		sway_log(SWAY_INFO,
				 "K230_CARD_BENCH v=1 run=%" PRIu64 " event=submit input_id=%" PRIu64
				 " frame_id=%" PRIu64 " t_ns=%" PRIu64 " update_cpu_ns=%" PRIu64 " final=%d",
				 bench.run, bench.pending[i].id, frame, now, bench.charged_cpu,
				 bench.pending[i].final);
	/* Diagnostic subdivision only: keep the acceptance rows and charged total
	 * unchanged. Render includes scene preparation, Pixman and output commit;
	 * input includes synchronous policy/scene updates. Other charged work is
	 * chiefly timer/preparation outside those handlers. Failed renders remain
	 * accumulated until the next successful frame, just like charged_cpu. */
	if (bench.count)
		sway_log(SWAY_INFO,
			"K230_CARD_SHELL frame-cost run=%" PRIu64 " frame_id=%" PRIu64
			" total_cpu_ns=%" PRIu64 " render_cpu_ns=%" PRIu64 " input_cpu_ns=%" PRIu64,
			bench.run, frame, bench.charged_cpu, bench.render_cpu, bench.input_cpu);
	if (bench.count)
		sway_log(SWAY_INFO,
			"K230_CARD_SHELL repaint-cost run=%" PRIu64 " frame_id=%" PRIu64
			" render_cpu_ns=%" PRIu64 " prepare_cpu_ns=%" PRIu64
			" build_cpu_ns=%" PRIu64 " commit_cpu_ns=%" PRIu64
			" attempts=%" PRIu64 " failed_attempts=%" PRIu64,
			bench.run, frame, bench.render_cpu, bench.stage_cpu[CARD_BENCH_PREPARE],
			bench.stage_cpu[CARD_BENCH_BUILD], bench.stage_cpu[CARD_BENCH_COMMIT],
			bench.render_attempts, bench.failed_attempts);
	bench.count = 0;
	bench.charged_cpu = 0;
	bench.render_cpu = 0;
	bench.input_cpu = 0;
	memset(bench.stage_cpu, 0, sizeof(bench.stage_cpu));
	bench.render_attempts = bench.failed_attempts = 0;
}
void card_bench_present(struct sway_output *output, struct wlr_output_event_present *event) {
	if (!bench.armed || bench.output != output)
		return;
	uint64_t now = (uint64_t)event->when.tv_sec * 1000000000 + event->when.tv_nsec;
	sway_log(SWAY_INFO,
			 "K230_CARD_BENCH v=1 run=%" PRIu64 " event=present frame_id=%u t_ns=%" PRIu64
			 " presented=%d clock=monotonic",
			 bench.run, event->commit_seq, now, event->presented);
}
