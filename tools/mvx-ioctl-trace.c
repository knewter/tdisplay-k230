#define _GNU_SOURCE

/*
 * LD_PRELOAD observer for the V4L2 timestamp boundary used by the MVX decoder.
 *
 * It deliberately observes only.  With MVX_IOCTL_TRACE=1, it records QBUF and
 * successful DQBUF calls made on a /dev/video* descriptor.  It neither changes
 * the supplied v4l2_buffer nor opens a device.  The log goes to stderr so a
 * caller can retain its normal stdout protocol.
 */
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/videodev2.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/types.h>
#include <unistd.h>

typedef int (*ioctl_fn)(int, unsigned long, ...);

static bool enabled(void)
{
	const char *value = getenv("MVX_IOCTL_TRACE");

	return value != NULL && strcmp(value, "0") != 0;
}

static const char *type_name(enum v4l2_buf_type type)
{
	switch (type) {
	case V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE:
		return "OUTPUT_MPLANE";
	case V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE:
		return "CAPTURE_MPLANE";
	case V4L2_BUF_TYPE_VIDEO_OUTPUT:
		return "OUTPUT";
	case V4L2_BUF_TYPE_VIDEO_CAPTURE:
		return "CAPTURE";
	default:
		return "OTHER";
	}
}

static bool is_video_fd(int fd, char path[64])
{
	char fd_path[32];
	const char *selected;
	ssize_t length;

	(void)snprintf(fd_path, sizeof(fd_path), "/proc/self/fd/%d", fd);
	length = readlink(fd_path, path, 63);
	if (length < 0)
		return false;
	path[length] = '\0';
	selected = getenv("MVX_IOCTL_TRACE_DEVICE");
	if (selected != NULL)
		return strcmp(path, selected) == 0;
	return strncmp(path, "/dev/video", strlen("/dev/video")) == 0;
}

static unsigned int bytesused(const struct v4l2_buffer *buffer)
{
	if (V4L2_TYPE_IS_MULTIPLANAR(buffer->type))
		return buffer->m.planes != NULL ? buffer->m.planes[0].bytesused : 0;
	return buffer->bytesused;
}

static void trace_buffer(const char *phase, int fd,
			 const struct v4l2_buffer *buffer, int result, int syscall_errno)
{
	char path[64];
	char line[320];
	int length;
	ssize_t written;

	if (!enabled() || !is_video_fd(fd, path))
		return;
	length = snprintf(line, sizeof(line),
		"MVX_IOCTL_TRACE phase=%s path=%s type=%s index=%u "
		"timestamp=%lld.%06lld flags=0x%08x bytesused=%u result=%d errno=%d\n",
		phase, path, type_name(buffer->type), buffer->index,
		(long long)buffer->timestamp.tv_sec,
		(long long)buffer->timestamp.tv_usec, buffer->flags,
		bytesused(buffer), result, result < 0 ? syscall_errno : 0);
	if (length > 0) {
		written = write(STDERR_FILENO, line,
				(size_t)length < sizeof(line) ? (size_t)length : sizeof(line) - 1);
		if (written < 0)
			return;
	}
}

int ioctl(int fd, unsigned long request, ...)
{
	static ioctl_fn real_ioctl;
	void *argument;
	va_list args;
	int caller_errno = errno;
	int result;
	int syscall_errno;

	if (real_ioctl == NULL)
		real_ioctl = (ioctl_fn)dlsym(RTLD_NEXT, "ioctl");
	if (real_ioctl == NULL) {
		errno = ENOSYS;
		return -1;
	}
	/* dlsym/readlink/logging must not alter the application's ioctl errno. */
	errno = caller_errno;

	/* The two intercepted requests always carry struct v4l2_buffer *. */
	if (request != VIDIOC_QBUF && request != VIDIOC_DQBUF) {
		va_start(args, request);
		argument = va_arg(args, void *);
		va_end(args);
		return real_ioctl(fd, request, argument);
	}

	va_start(args, request);
	argument = va_arg(args, void *);
	va_end(args);
	if (request == VIDIOC_QBUF)
		trace_buffer("QBUF", fd, argument, 0, 0);
	errno = caller_errno;
	result = real_ioctl(fd, request, argument);
	syscall_errno = errno;
	if (request == VIDIOC_QBUF)
		trace_buffer("QBUF_RESULT", fd, argument, result, syscall_errno);
	else if (result == 0)
		trace_buffer("DQBUF", fd, argument, result, syscall_errno);
	errno = syscall_errno;
	return result;
}
