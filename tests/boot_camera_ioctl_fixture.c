/* Host-only ioctl fixture; real mmap/poll/files exercise the recorder writer.
 * This supplies synthetic buffers, never a camera or physical timing proof.
 */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <time.h>
#include <linux/videodev2.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>

static unsigned frame;
static int is(const char *name) { return strcmp(getenv("CAMERA_SCENARIO"), name) == 0; }
static void cleanup(const char *name)
{
    FILE *out = fopen(getenv("CAMERA_CLEANUP_LOG"), "a");
    if (!out) abort();
    fprintf(out, "%s\n", name);
    fclose(out);
}

int __wrap_ioctl(int fd, unsigned long operation, ...)
{
    (void)fd;
    va_list args;
    va_start(args, operation);
    void *value = va_arg(args, void *);
    va_end(args);
    switch (operation) {
    case VIDIOC_QUERYCAP: {
        struct v4l2_capability *v = value;
        v->capabilities = V4L2_CAP_DEVICE_CAPS;
        v->device_caps = V4L2_CAP_VIDEO_CAPTURE | V4L2_CAP_STREAMING;
        return 0;
    }
    case VIDIOC_G_FMT: {
        struct v4l2_format *v = value;
        v->fmt.pix.width = 1280;
        v->fmt.pix.height = 720;
        v->fmt.pix.pixelformat = is("format") ? V4L2_PIX_FMT_YUYV : V4L2_PIX_FMT_MJPEG;
        return 0;
    }
    case VIDIOC_REQBUFS: {
        struct v4l2_requestbuffers *v = value;
        if (v->count == 0) cleanup("release_buffers");
        else v->count = 2;
        return 0;
    }
    case VIDIOC_QUERYBUF: {
        struct v4l2_buffer *v = value;
        v->length = 1048576;
        v->m.offset = v->index * 1048576;
        return 0;
    }
    case VIDIOC_STREAMON: return 0;
    case VIDIOC_STREAMOFF: cleanup("stream_off"); return 0;
    case VIDIOC_QBUF:
        if (is("requeue") && frame) { errno = EIO; return -1; }
        return 0;
    case VIDIOC_DQBUF: {
        if (is("wait_signal") && frame) { errno = EAGAIN; return -1; }
        struct v4l2_buffer *v = value;
        v->index = is("index") ? 64 : frame % 2;
        v->bytesused = is("size") ? 1048577 : is("cap") ? 700000 : 4;
        v->sequence = is("wrap") ? UINT32_MAX + frame : frame + (is("gap") && frame > 0);
        v->flags = V4L2_BUF_FLAG_TIMESTAMP_MONOTONIC | V4L2_BUF_FLAG_TSTAMP_SRC_SOE;
        if (is("unknown")) v->flags = 0;
        if (is("clock_change") && frame) v->flags = V4L2_BUF_FLAG_TIMESTAMP_MONOTONIC;
        if (is("buffer_error")) v->flags |= V4L2_BUF_FLAG_ERROR;
        v->timestamp.tv_sec = is("future") ? 4000000000LL : 10;
        v->timestamp.tv_usec = is("timeval") ? 1000000 : is("regression") ? 1 : (frame + 1) * 33333;
        frame++;
        return 0;
    }
    default:
        fprintf(stderr, "fixture: unexpected ioctl %lu\n", operation);
        errno = EINVAL;
        return -1;
    }
}
