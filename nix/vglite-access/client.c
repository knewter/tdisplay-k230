#define _GNU_SOURCE
#include <fcntl.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <sys/un.h>
#include <unistd.h>
#include <k230_vg_lite.h>
#include "client.h"

bool k230_vglite_broker_acquire(const char *path) {
	/* Called in Sway server_init, before IPC/config/ordinary client startup.
	 * The broker's Yama gate closes the earlier process-startup ptrace window. */
	if (prctl(PR_SET_DUMPABLE, 0) < 0 || prctl(PR_GET_DUMPABLE) != 0) return false;
	struct sockaddr_un address = {.sun_family = AF_UNIX};
	if (!path || path[0] != '/' || strlen(path) >= sizeof(address.sun_path)) return false;
	strcpy(address.sun_path, path);
	int sock = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
	if (sock < 0) return false;
	struct timeval timeout = {.tv_sec = 3};
	bool ok = false;
	if (setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) < 0 ||
		setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout)) < 0 ||
		connect(sock, (struct sockaddr *)&address, sizeof(address)) < 0) goto out;
	struct ucred peer; socklen_t peer_size = sizeof(peer);
	if (getsockopt(sock, SOL_SOCKET, SO_PEERCRED, &peer, &peer_size) < 0 || peer.uid != 0) goto out;
	if (send(sock, "VG1\n", 4, MSG_NOSIGNAL) != 4) goto out;
	char reply = 0;
	struct iovec iov = {.iov_base = &reply, .iov_len = 1};
	union { struct cmsghdr align; char bytes[CMSG_SPACE(sizeof(int) * 16)]; } control = {0};
	struct msghdr message = {.msg_iov = &iov, .msg_iovlen = 1,
		.msg_control = control.bytes, .msg_controllen = sizeof(control.bytes)};
	ssize_t received = recvmsg(sock, &message, MSG_CMSG_CLOEXEC);
	int descriptor = -1; unsigned count = 0;
	for (struct cmsghdr *cmsg = CMSG_FIRSTHDR(&message); received >= 0 && cmsg; cmsg = CMSG_NXTHDR(&message, cmsg)) {
		if (cmsg->cmsg_level != SOL_SOCKET || cmsg->cmsg_type != SCM_RIGHTS || cmsg->cmsg_len < CMSG_LEN(0)) continue;
		size_t n = (cmsg->cmsg_len - CMSG_LEN(0)) / sizeof(int);
		int *fds = (int *)CMSG_DATA(cmsg);
		for (size_t i = 0; i < n; i++) {
			count++;
			if (descriptor < 0) descriptor = fds[i]; else close(fds[i]);
		}
	}
	int flags = descriptor >= 0 ? fcntl(descriptor, F_GETFD) : -1;
	if (received == 1 && reply == 'G' && !(message.msg_flags & (MSG_TRUNC | MSG_CTRUNC)) && count == 1 &&
		flags >= 0 && (flags & FD_CLOEXEC) && prctl(PR_GET_DUMPABLE) == 0)
		ok = k230_vg_lite_adopt_device_fd(descriptor) == VG_LITE_SUCCESS;
	if (descriptor >= 0) close(descriptor);
out:
	close(sock); return ok;
}
