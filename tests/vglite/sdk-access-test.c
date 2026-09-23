#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <unistd.h>
#include <vg_lite_kernel.h>
#include <vg_lite_ioctl.h>

static int reject_advice;
static void *regions[16];
static size_t sizes[16], region_count;
static void *region(size_t size) {
    void *p = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    assert(p != MAP_FAILED && region_count < 16);
    regions[region_count] = p; sizes[region_count++] = size; return p;
}
static void *fake_mmap(void *a, size_t n, int p, int f, int fd, off_t o) {
    (void)a; (void)p; (void)f; (void)fd; (void)o; return region(n);
}
static int fake_madvise(void *address, size_t length, int advice) {
    assert(advice == MADV_DONTFORK);
    if (reject_advice) { errno = EINVAL; return -1; }
    return madvise(address, length, advice);
}
static int fake_ioctl(int fd, unsigned long request, ...) {
    assert(fcntl(fd, F_GETFD) >= 0 && request == VG_LITE_IOCTL);
    va_list args; va_start(args, request); struct ioctl_data *call = va_arg(args, void *); va_end(args);
    call->error = VG_LITE_SUCCESS;
    if (call->command == VG_LITE_INITIALIZE) {
        vg_lite_kernel_initialize_t *init = call->buffer;
        for (int i = 0; i < CMDBUF_COUNT; i++) init->command_buffer[i] = region(init->command_buffer_size);
        init->logical_addr = region(8192); init->tessbuf_size = 4096; init->countbuf_size = 4096;
        init->context->power_context_logical = region(4096); init->context->power_context_size = 4096;
    } else if (call->command == VG_LITE_ALLOCATE) {
        vg_lite_kernel_allocate_t *alloc = call->buffer; alloc->memory = region(alloc->bytes);
    } else if (call->command == VG_LITE_MAP_MEMORY) {
        vg_lite_kernel_map_memory_t *map = call->buffer;
        map->logical = (uint8_t *)region(map->bytes + 128) + 128;
    }
    return 0;
}
#define mmap fake_mmap
#define madvise fake_madvise
#define ioctl fake_ioctl
#include "vg_lite_ioctl.c"
#undef mmap
#undef madvise
#undef ioctl

static void exercise(const char *self, int failure) {
    int fd = open("/dev/null", O_RDONLY | O_CLOEXEC); assert(fd >= 0);
    assert(k230_vg_lite_adopt_device_fd(fd) == VG_LITE_INVALID_ARGUMENT); close(fd);
    fd = open("/dev/null", O_RDWR | O_CLOEXEC); assert(fd >= 0);
    assert(k230_vg_lite_adopt_device_fd(fd) == VG_LITE_SUCCESS); close(fd);
    int private_fd = device;
    assert(private_fd >= 3 && (fcntl(private_fd, F_GETFD) & FD_CLOEXEC));
    assert(k230_vg_lite_adopt_device_fd(private_fd) == VG_LITE_INVALID_ARGUMENT);
    vg_lite_kernel_context_t context = {0};
    vg_lite_kernel_initialize_t init = {.command_buffer_size = 4096, .context = &context};
    assert(vg_lite_kernel(VG_LITE_INITIALIZE, &init) == VG_LITE_SUCCESS);
    vg_lite_kernel_allocate_t alloc = {.bytes = 8192};
    reject_advice = failure;
    assert(vg_lite_kernel(VG_LITE_ALLOCATE, &alloc) == (failure ? VG_LITE_GENERIC_IO : VG_LITE_SUCCESS));
    if (!failure) {
        vg_lite_kernel_map_memory_t map = {.bytes = 8192};
        assert(vg_lite_kernel(VG_LITE_MAP_MEMORY, &map) == VG_LITE_SUCCESS);
        assert(vg_lite_kernel((vg_lite_kernel_command_t)-1, NULL) == VG_LITE_INVALID_ARGUMENT);
    }
    pid_t child = fork(); assert(child >= 0);
    if (!child) {
        assert(!failure); /* protection failure must exit in the atfork hook */
        assert(device == -1 && child_blocked);
        errno = 0; assert(fcntl(private_fd, F_GETFD) == -1 && errno == EBADF);
        assert(vg_lite_kernel(VG_LITE_CHECK, NULL) == VG_LITE_INVALID_ARGUMENT);
        for (size_t i = 0; i < region_count; i++) {
            unsigned char resident;
            errno = 0; assert(mincore(regions[i], 4096, &resident) == -1 && errno == ENOMEM);
            void *end = (uint8_t *)regions[i] + ((sizes[i] - 1) / 4096) * 4096;
            errno = 0; assert(mincore(end, 4096, &resident) == -1 && errno == ENOMEM);
        }
        _exit(0);
    }
    int status; assert(waitpid(child, &status, 0) == child && WIFEXITED(status));
    assert(WEXITSTATUS(status) == (failure ? 127 : 0));
    assert(fcntl(private_fd, F_GETFD) >= 0);
    if (!failure) {
        /* Bypass libc's atfork hook to independently prove CLOEXEC. */
        child = syscall(SYS_fork); assert(child >= 0);
        if (!child) {
            char argument[32]; snprintf(argument, sizeof(argument), "%d", private_fd);
            execl(self, self, "--closed", argument, NULL); _exit(99);
        }
        assert(waitpid(child, &status, 0) == child && WIFEXITED(status) && WEXITSTATUS(status) == 0);
    }
    for (size_t i = 0; i < region_count; i++) munmap(regions[i], sizes[i]);
    close(private_fd);
}
int main(int argc, char **argv) {
    if (argc == 3) { errno = 0; assert(fcntl(atoi(argv[2]), F_GETFD) == -1 && errno == EBADF); return 0; }
    for (int failure = 0; failure < 2; failure++) {
        pid_t child = fork(); assert(child >= 0);
        if (!child) { exercise(argv[0], failure); _exit(0); }
        int status; assert(waitpid(child, &status, 0) == child && WIFEXITED(status) && WEXITSTATUS(status) == 0);
    }
    puts("PASS: patched SDK adoption, real CLOEXEC, atfork fd revocation, command/tessellation/pixel mapping DONTFORK, protection-failure child denial");
}
