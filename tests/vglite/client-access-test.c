#define _GNU_SOURCE
#include <assert.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <k230_vg_lite.h>

/* Only root peer credentials are injected. Transport, received descriptor
 * flags, timeout configuration, non-dumpability and cleanup are real Linux. */
static bool trusted, adopt_ok;
static unsigned adopted;
static int peer_credentials(int fd, int level, int name, void *value, socklen_t *size) {
	int result = getsockopt(fd, level, name, value, size);
	if (!result && level == SOL_SOCKET && name == SO_PEERCRED)
		((struct ucred *)value)->uid = trusted ? 0 : 12345;
	return result;
}
#define getsockopt peer_credentials
#include "../../nix/vglite-access/client.c"
#undef getsockopt

vg_lite_error_t k230_vg_lite_adopt_device_fd(int fd) {
	assert(prctl(PR_GET_DUMPABLE) == 0);
	assert(fcntl(fd, F_GETFD) & FD_CLOEXEC);
	assert((fcntl(fd, F_GETFL) & O_ACCMODE) == O_RDWR);
	adopted++;
	return adopt_ok ? VG_LITE_SUCCESS : VG_LITE_GENERIC_IO;
}
static unsigned descriptor_count(void) {
	DIR *dir = opendir("/proc/self/fd"); assert(dir);
	unsigned count = 0;
	while (readdir(dir)) count++;
	closedir(dir); return count;
}
struct response { int listener; unsigned fds; char byte; };
static void *server(void *opaque) {
	struct response *response = opaque;
	int client = accept4(response->listener, NULL, NULL, SOCK_CLOEXEC); assert(client >= 0);
	char request[4]; ssize_t n = recv(client, request, sizeof(request), MSG_WAITALL);
	if (!trusted) { assert(n == 0); close(client); return NULL; }
	assert(n == 4 && memcmp(request, "VG1\n", 4) == 0);
	int descriptors[32]; assert(response->fds <= 32);
	for (unsigned i = 0; i < response->fds; i++) {
		descriptors[i] = open("/dev/null", O_RDWR | O_CLOEXEC); assert(descriptors[i] >= 0);
	}
	char buffer[CMSG_SPACE(sizeof(descriptors))] = {0};
	struct iovec iov = {.iov_base = &response->byte, .iov_len = 1};
	struct msghdr msg = {.msg_iov = &iov, .msg_iovlen = 1};
	if (response->fds) {
		msg.msg_control = buffer; msg.msg_controllen = CMSG_SPACE(sizeof(int) * response->fds);
		struct cmsghdr *cmsg = CMSG_FIRSTHDR(&msg);
		cmsg->cmsg_level = SOL_SOCKET; cmsg->cmsg_type = SCM_RIGHTS;
		cmsg->cmsg_len = CMSG_LEN(sizeof(int) * response->fds);
		memcpy(CMSG_DATA(cmsg), descriptors, sizeof(int) * response->fds);
	}
	assert(sendmsg(client, &msg, MSG_NOSIGNAL) == 1);
	for (unsigned i = 0; i < response->fds; i++) close(descriptors[i]);
	close(client); return NULL;
}
static void exchange(unsigned fds, char byte, bool root, bool accept_adoption, bool expected, unsigned calls) {
	unsigned baseline = descriptor_count();
	char directory[] = "/tmp/vglite-client-XXXXXX"; assert(mkdtemp(directory));
	struct sockaddr_un address = {.sun_family = AF_UNIX};
	assert(snprintf(address.sun_path, sizeof(address.sun_path), "%s/socket", directory) > 0);
	int listener = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0); assert(listener >= 0);
	assert(bind(listener, (struct sockaddr *)&address, sizeof(address)) == 0);
	assert(listen(listener, 1) == 0);
	trusted = root; adopt_ok = accept_adoption; adopted = 0;
	struct response response = {.listener = listener, .fds = fds, .byte = byte};
	pthread_t thread; assert(pthread_create(&thread, NULL, server, &response) == 0);
	assert(k230_vglite_broker_acquire(address.sun_path) == expected);
	assert(pthread_join(thread, NULL) == 0); assert(adopted == calls);
	close(listener); assert(unlink(address.sun_path) == 0); assert(rmdir(directory) == 0);
	assert(descriptor_count() == baseline); assert(prctl(PR_GET_DUMPABLE) == 0);
}
int main(void) {
	exchange(1, 'G', true, true, true, 1);
	exchange(1, 'G', false, true, false, 0);
	exchange(1, 'X', true, true, false, 0);
	exchange(0, 'G', true, true, false, 0);
	exchange(2, 'G', true, true, false, 0);
	exchange(32, 'G', true, true, false, 0);
	exchange(1, 'G', true, false, false, 1);
	assert(!k230_vglite_broker_acquire("relative"));
	assert(!k230_vglite_broker_acquire("/missing/vglite/socket"));
	puts("PASS: real C receiver transport, CLOEXEC, nondumpability, malformed grants and descriptor cleanup");
}
