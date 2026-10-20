/* Bounded host V4L2 MJPEG capture with unmodified per-buffer timestamps.
 * See https://docs.kernel.org/userspace-api/media/v4l/buffer.html .
 * Capture success does not qualify camera exposure or kernel/video alignment.
 */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <time.h>
#include <linux/videodev2.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

struct mapping { void *data; size_t size; };
static volatile sig_atomic_t interrupted;

static void stop(int sig) { interrupted = sig; }

static uint64_t ns(clockid_t clock)
{
    struct timespec t;
    if (clock_gettime(clock, &t)) { perror("clock_gettime"); exit(2); }
    return (uint64_t)t.tv_sec * 1000000000 + (uint64_t)t.tv_nsec;
}

static int call(int fd, unsigned long request, void *value)
{
    int r;
    do { r = ioctl(fd, request, value); } while (r < 0 && errno == EINTR && !interrupted);
    return r;
}

static unsigned number(const char *s, unsigned max)
{
    char *end;
    errno = 0;
    if (!*s || *s < '0' || *s > '9') return 0;
    unsigned long v = strtoul(s, &end, 10);
    return errno || *end || v == 0 || v > max ? 0 : (unsigned)v;
}

int main(int argc, char **argv)
{
    unsigned seconds = argc >= 5 ? number(argv[3], 600) : 0;
    unsigned mib = argc >= 5 ? number(argv[4], 4096) : 0;
    unsigned limit = argc == 6 ? number(argv[5], 36000) : 36000;
    if ((argc != 5 && argc != 6) || !seconds || !mib || !limit) {
        fprintf(stderr, "usage: %s DEVICE NEW_OUTPUT_DIR SECONDS(1..600) MAX_MIB(1..4096) [MAX_FRAMES(1..36000)]\n", argv[0]);
        return 2;
    }
    int fd = -1, directory = -1, streaming = 0, result = 2;
    FILE *video = NULL, *records = NULL;
    struct mapping *maps = NULL;
    unsigned mapped = 0, frames = 0, gaps = 0;
    uint32_t previous_sequence = 0;
    uint32_t previous_clock = 0, previous_source = 0;
    uint64_t previous_timestamp = 0, bytes = 0;
    const char *reason = "setup_error";
    enum v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    struct v4l2_requestbuffers request = { .count = 8, .type = type, .memory = V4L2_MEMORY_MMAP };
    int allocated = 0;
#define CHECK(condition, label) do { if (!(condition)) { perror(label); reason = label; goto done; } } while (0)
    signal(SIGINT, stop);
    signal(SIGTERM, stop);
    fd = open(argv[1], O_RDWR | O_NONBLOCK | O_CLOEXEC);
    CHECK(fd >= 0, "open_camera");
    CHECK(flock(fd, LOCK_EX | LOCK_NB) == 0, "camera_lock");
    struct v4l2_capability capability = {0};
    CHECK(call(fd, VIDIOC_QUERYCAP, &capability) == 0, "VIDIOC_QUERYCAP");
    uint32_t caps = capability.capabilities & V4L2_CAP_DEVICE_CAPS ? capability.device_caps : capability.capabilities;
    if (!(caps & V4L2_CAP_VIDEO_CAPTURE) || !(caps & V4L2_CAP_STREAMING)) {
        fprintf(stderr, "camera needs single-planar capture and streaming\n");
        goto done;
    }
    struct v4l2_format format = { .type = type };
    CHECK(call(fd, VIDIOC_G_FMT, &format) == 0, "VIDIOC_G_FMT");
    if (format.fmt.pix.pixelformat != V4L2_PIX_FMT_MJPEG) {
        fprintf(stderr, "camera must already be configured for MJPEG; format and controls are not changed\n");
        goto done;
    }
    CHECK(call(fd, VIDIOC_REQBUFS, &request) == 0, "VIDIOC_REQBUFS");
    allocated = 1;
    if (!request.count || request.count > 64) {
        fprintf(stderr, "invalid camera buffer count\n"); goto done;
    }
    maps = calloc(request.count, sizeof(*maps));
    CHECK(maps != NULL, "calloc");
    for (unsigned i = 0; i < request.count; i++) {
        struct v4l2_buffer buffer = { .type = type, .memory = V4L2_MEMORY_MMAP, .index = i };
        CHECK(call(fd, VIDIOC_QUERYBUF, &buffer) == 0, "VIDIOC_QUERYBUF");
        if (!buffer.length) { fprintf(stderr, "empty camera buffer\n"); goto done; }
        void *data = mmap(NULL, buffer.length, PROT_READ | PROT_WRITE, MAP_SHARED, fd, buffer.m.offset);
        CHECK(data != MAP_FAILED, "mmap");
        maps[i] = (struct mapping){ data, buffer.length };
        mapped++;
        CHECK(call(fd, VIDIOC_QBUF, &buffer) == 0, "VIDIOC_QBUF");
    }
    /* Never reuse an output directory, overwrite a capture or follow its files. */
    CHECK(mkdir(argv[2], 0700) == 0, "mkdir_output");
    directory = open(argv[2], O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    CHECK(directory >= 0, "open_output");
    int vf = openat(directory, "frames.mjpeg", O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
    CHECK(vf >= 0, "open_video");
    video = fdopen(vf, "wb");
    if (!video) close(vf);
    CHECK(video != NULL, "fdopen_video");
    int rf = openat(directory, "frames.jsonl", O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
    CHECK(rf >= 0, "open_records");
    records = fdopen(rf, "w");
    if (!records) close(rf);
    CHECK(records != NULL, "fdopen_records");
    fprintf(records, "{\"kind\":\"header\",\"schema\":1,\"format\":\"MJPEG\",\"width\":%u,\"height\":%u,\"duration_limit_seconds\":%u,\"byte_limit\":%" PRIu64 ",\"frame_limit\":%u,\"host_monotonic_ns\":%" PRIu64 ",\"host_utc_ns\":%" PRIu64 ",\"kernel_video_alignment_qualified\":false}\n",
            format.fmt.pix.width, format.fmt.pix.height, seconds, (uint64_t)mib * 1048576, limit, ns(CLOCK_MONOTONIC), ns(CLOCK_REALTIME));
    CHECK(fflush(records) == 0, "flush_header");
    uint64_t started = ns(CLOCK_MONOTONIC);
    CHECK(call(fd, VIDIOC_STREAMON, &type) == 0, "VIDIOC_STREAMON");
    streaming = 1;
    reason = "duration_limit";
    result = 0;
    while (frames < limit && !interrupted) {
        uint64_t before = ns(CLOCK_MONOTONIC);
        if (before - started >= (uint64_t)seconds * 1000000000) break;
        int remaining = (int)(((uint64_t)seconds * 1000000000 - (before - started) + 999999) / 1000000);
        struct pollfd ready = { .fd = fd, .events = POLLIN };
        int polled = poll(&ready, 1, remaining < 2000 ? remaining : 2000);
        if (polled < 0 && errno == EINTR) continue;
        if (polled == 0 && remaining <= 2000) break;
        if (polled <= 0 || !(ready.revents & POLLIN) || ready.revents & (POLLERR | POLLHUP | POLLNVAL)) {
            reason = "camera_stall_or_poll_error"; result = 2; break;
        }
        struct v4l2_buffer buffer = { .type = type, .memory = V4L2_MEMORY_MMAP };
        uint64_t dq_before = ns(CLOCK_MONOTONIC);
        if (call(fd, VIDIOC_DQBUF, &buffer) != 0) {
            if (errno == EAGAIN) continue;
            reason = "VIDIOC_DQBUF"; result = 2; break;
        }
        uint64_t dq_after = ns(CLOCK_MONOTONIC);
        if (buffer.index >= mapped || !buffer.bytesused || buffer.bytesused > maps[buffer.index].size ||
            buffer.timestamp.tv_sec < 0 || buffer.timestamp.tv_usec < 0 || buffer.timestamp.tv_usec >= 1000000) {
            reason = "invalid_buffer"; result = 2; break;
        }
        uint64_t timestamp = (uint64_t)buffer.timestamp.tv_sec * 1000000000 + (uint64_t)buffer.timestamp.tv_usec * 1000;
        uint32_t sequence_delta = buffer.sequence - previous_sequence;
        int gap = frames > 0 && sequence_delta != 1;
        int timestamp_regression = frames > 0 && timestamp <= previous_timestamp;
        if (gap) gaps++;
        uint32_t clock = buffer.flags & V4L2_BUF_FLAG_TIMESTAMP_MASK;
        uint32_t source = buffer.flags & V4L2_BUF_FLAG_TSTAMP_SRC_MASK;
        int clock_flags_changed = frames > 0 && (clock != previous_clock || source != previous_source);
        int timestamp_invalid = !timestamp || (clock == V4L2_BUF_FLAG_TIMESTAMP_MONOTONIC && timestamp > dq_after);
        const char *clock_name = clock == V4L2_BUF_FLAG_TIMESTAMP_MONOTONIC ? "monotonic" : clock == V4L2_BUF_FLAG_TIMESTAMP_COPY ? "copy" : "unknown";
        const char *source_name = source == V4L2_BUF_FLAG_TSTAMP_SRC_SOE ? "start_of_exposure" : source == V4L2_BUF_FLAG_TSTAMP_SRC_EOF ? "end_of_frame" : "unknown";
        if (bytes + buffer.bytesused > (uint64_t)mib * 1048576) {
            reason = "byte_limit"; result = 2; break;
        }
        CHECK(fwrite(maps[buffer.index].data, 1, buffer.bytesused, video) == buffer.bytesused, "write_frame");
        fprintf(records, "{\"kind\":\"frame\",\"frame\":%u,\"sequence\":%u,\"sequence_gap\":%s,\"timestamp_regression\":%s,\"clock_flags_changed\":%s,\"timestamp_invalid\":%s,\"flags\":%u,\"buffer_error\":%s,\"camera_timestamp_ns\":%" PRIu64 ",\"camera_clock\":\"%s\",\"timestamp_source\":\"%s\",\"host_dq_before_ns\":%" PRIu64 ",\"host_dq_after_ns\":%" PRIu64 ",\"offset\":%" PRIu64 ",\"bytes\":%u}\n",
                frames, buffer.sequence, gap ? "true" : "false", timestamp_regression ? "true" : "false", clock_flags_changed ? "true" : "false", timestamp_invalid ? "true" : "false", buffer.flags, buffer.flags & V4L2_BUF_FLAG_ERROR ? "true" : "false", timestamp, clock_name, source_name, dq_before, dq_after, bytes, buffer.bytesused);
        CHECK(fflush(records) == 0, "flush_frame_record");
        bytes += buffer.bytesused;
        frames++;
        previous_sequence = buffer.sequence;
        previous_timestamp = timestamp;
        previous_clock = clock;
        previous_source = source;
        if (gap || timestamp_regression || clock_flags_changed || timestamp_invalid || buffer.flags & V4L2_BUF_FLAG_ERROR) result = 2;
        CHECK(call(fd, VIDIOC_QBUF, &buffer) == 0, "VIDIOC_QBUF");
    }
    if (frames == limit) reason = "frame_limit";
    if (interrupted) { reason = "interrupted"; result = 128 + interrupted; }
    if (!frames && result == 0) { reason = "no_frames"; result = 2; }
done:
    /* CHECK failures must override an earlier successful frame. */
    if (strcmp(reason, "duration_limit") && strcmp(reason, "frame_limit") && !interrupted) result = 2;
    if (streaming && call(fd, VIDIOC_STREAMOFF, &type)) { perror("VIDIOC_STREAMOFF"); result = 2; }
    for (unsigned i = 0; i < mapped; i++)
        if (munmap(maps[i].data, maps[i].size)) result = 2;
    free(maps);
    if (allocated) {
        request.count = 0;
        if (call(fd, VIDIOC_REQBUFS, &request)) result = 2;
    }
    if (video) {
        if (fflush(video) || fsync(fileno(video))) result = 2;
        if (fclose(video)) result = 2;
    }
    if (records) {
        if (fprintf(records, "{\"kind\":\"summary\",\"frames\":%u,\"bytes\":%" PRIu64 ",\"sequence_gaps\":%u,\"reason\":\"%s\",\"capture_complete\":%s,\"kernel_video_alignment_qualified\":false,\"host_monotonic_ns\":%" PRIu64 "}\n",
                    frames, bytes, gaps, reason, result == 0 ? "true" : "false", ns(CLOCK_MONOTONIC)) < 0) result = 2;
        if (fflush(records) || fsync(fileno(records))) result = 2;
        if (fclose(records)) result = 2;
    }
    if (directory >= 0) { if (fsync(directory)) result = 2; close(directory); }
    if (fd >= 0) close(fd);
    fprintf(stderr, "frames=%u bytes=%" PRIu64 " reason=%s exit=%d; kernel/video alignment UNQUALIFIED\n", frames, bytes, reason, result);
    return result;
}
