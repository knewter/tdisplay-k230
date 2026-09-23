#include <fcntl.h>
#include <linux/videodev2.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

/* Exercises the observer's QBUF formatting with an intentionally invalid fd. */
int main(void)
{
	struct v4l2_buffer buffer;
	struct v4l2_plane plane;
	int fd;

	fd = open("/dev/null", O_RDONLY | O_CLOEXEC);
	if (fd < 0)
		return 1;
	memset(&buffer, 0, sizeof(buffer));
	memset(&plane, 0, sizeof(plane));
	buffer.type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE;
	buffer.memory = V4L2_MEMORY_MMAP;
	buffer.index = 7;
	buffer.length = 1;
	buffer.m.planes = &plane;
	buffer.timestamp.tv_sec = 12;
	buffer.timestamp.tv_usec = 345678;
	plane.bytesused = 99;
	(void)ioctl(fd, VIDIOC_QBUF, &buffer);
	close(fd);
	return 0;
}
