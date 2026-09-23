#define _GNU_SOURCE

/*
 * Read-only capability probe for the K230 Canaan/Arm-China MVX V4L2 node.
 * It deliberately does not set a format, allocate buffers, or start streaming.
 */
#include <errno.h>
#include <fcntl.h>
#include <linux/videodev2.h>
#include <stdbool.h>
#include <stdint.h>
#include <time.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

static void fourcc_to_text(__u32 format, char text[5])
{
	text[0] = format & 0x7f;
	text[1] = (format >> 8) & 0x7f;
	text[2] = (format >> 16) & 0x7f;
	text[3] = (format >> 24) & 0x7f;
	text[4] = '\0';
}

static int enumerate_formats(int fd, enum v4l2_buf_type type,
			     const char *name, bool *has_h264)
{
	struct v4l2_fmtdesc fmt;
	char fourcc[5];
	unsigned int count = 0;

	printf("%s:\n", name);
	for (unsigned int index = 0;; index++) {
		memset(&fmt, 0, sizeof(fmt));
		fmt.index = index;
		fmt.type = type;
		if (ioctl(fd, VIDIOC_ENUM_FMT, &fmt) == 0) {
			fourcc_to_text(fmt.pixelformat, fourcc);
			printf("  %s%s%s\n", fourcc,
			       (fmt.flags & V4L2_FMT_FLAG_COMPRESSED) ? " compressed" : "",
			       fmt.description);
			if (type == V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE &&
			    fmt.pixelformat == V4L2_PIX_FMT_H264)
				*has_h264 = true;
			count++;
			continue;
		}
		if (errno == EINVAL)
			break;
		fprintf(stderr, "VIDIOC_ENUM_FMT %s index %u: %s\n", name,
			index, strerror(errno));
		return -1;
	}
	printf("  entries=%u\n", count);
	return 0;
}

int main(int argc, char **argv)
{
	const char *device = argc == 2 ? argv[1] : "/dev/video0";
	struct v4l2_capability cap;
	bool h264_output = false;
	int fd;

	if (argc > 2) {
		fprintf(stderr, "usage: %s [/dev/videoN]\n", argv[0]);
		return 2;
	}
	fd = open(device, O_RDONLY | O_CLOEXEC);
	if (fd < 0) {
		fprintf(stderr, "open %s: %s\n", device, strerror(errno));
		return 1;
	}
	memset(&cap, 0, sizeof(cap));
	if (ioctl(fd, VIDIOC_QUERYCAP, &cap) < 0) {
		fprintf(stderr, "VIDIOC_QUERYCAP %s: %s\n", device, strerror(errno));
		close(fd);
		return 1;
	}
	printf("device=%s\ndriver=%s\ncard=%s\nbus=%s\ncapabilities=0x%08x\ndevice_caps=0x%08x\n",
	       device, cap.driver, cap.card, cap.bus_info, cap.capabilities,
	       cap.device_caps);
	if (enumerate_formats(fd, V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE,
			      "output_mplane", &h264_output) ||
	    enumerate_formats(fd, V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE,
			      "capture_mplane", &h264_output)) {
		close(fd);
		return 1;
	}
	printf("h264_output_mplane=%s\n", h264_output ? "yes" : "no");
	close(fd);
	return h264_output ? 0 : 3;
}
