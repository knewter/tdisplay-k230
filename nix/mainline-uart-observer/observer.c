/* Opt-in initrd observation only. No TTY reads, opens, settings or MMIO.
 * The observer shares inherited descriptors; output is a bounded printk record.
 */
#define _GNU_SOURCE
#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <limits.h>
#include <linux/serial.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <sys/types.h>
#include <sys/utsname.h>
#include <sys/wait.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>

#ifndef UOBS_SYSTEMD
#define UOBS_SYSTEMD "/bin/systemd"
#endif
#define PAYLOAD_MAX 384
#define FRAME_MAX 900
#ifndef WINDOW_MS
#define WINDOW_MS 12000
#endif
#define GUARD_MS 20000
#define CHILD_MS 3000
#define TEXT_MAX 65536

struct context {
    char nonce[33], from[37], init[PATH_MAX], boot[37];
    char helper[PATH_MAX], shell[PATH_MAX];
    pid_t main_pid;
};
struct sample {
    struct termios term;
    struct serial_icounter_struct count;
    int ldisc, irq, irq_available;
    uint64_t irq_total;
    char runtime[12];
};
static int64_t now_ms(void) {
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t)) return -1;
    return (int64_t)t.tv_sec * 1000 + t.tv_nsec / 1000000;
}
static int wait_ms(int ms) {
    int64_t start = now_ms();
    if (start < 0) return -1;
    int64_t end = start + ms;
    for (;;) {
        int64_t now = now_ms();
        if (now < 0) return -1;
        if (now >= end) return 0;
        int64_t left = end - now;
        if (poll(NULL, 0, left > 100 ? 100 : (int)left) < 0 && errno != EINTR) return -1;
    }
}
static int read_text(const char *path, char *out, size_t size) {
    int fd = open(path, O_RDONLY | O_CLOEXEC | O_NOCTTY | O_NONBLOCK);
    if (fd < 0) return -1;
    size_t n = 0;
    int ok = -1;
    while (n < size - 1) {
        ssize_t got = read(fd, out + n, size - 1 - n);
        if (got == 0) { out[n] = 0; ok = memchr(out, 0, n) ? -1 : 0; break; }
        if (got < 0) { if (errno == EINTR) continue; break; }
        n += (size_t)got;
    }
    close(fd);
    return ok; /* A full buffer is unknown, never truncated success. */
}
static int link_text(const char *path, char *out, size_t size) {
    ssize_t n = readlink(path, out, size - 1);
    if (n < 0 || (size_t)n == size - 1) return -1;
    out[n] = 0;
    return 0;
}
static int lower_hex(const char *s, size_t n) {
    if (strlen(s) != n) return 0;
    for (size_t i = 0; i < n; i++) if (!strchr("0123456789abcdef", s[i])) return 0;
    return 1;
}
static int uuid(const char *s) {
    if (strlen(s) != 36) return 0;
    for (int i = 0; i < 36; i++) {
        int dash = i == 8 || i == 13 || i == 18 || i == 23;
        if (dash ? s[i] != '-' : !strchr("0123456789abcdef", s[i])) return 0;
    }
    return 1;
}
static int immutable_init(const char *s) {
    if (strncmp(s, "/nix/store/", 11)) return 0;
    s += 11;
    if (strlen(s) < 39) return 0;
    for (int i = 0; i < 32; i++) if (!strchr("0123456789abcdfghijklmnpqrsvwxyz", s[i])) return 0;
    if (s[32] != '-') return 0;
    const char *p = s + 33;
    for (; *p && *p != '/'; p++) if (!(isalnum((unsigned char)*p) || strchr("+._=-", *p))) return 0;
    return p > s + 33 && !strcmp(p, "/init");
}
static int parse_context(char *cmdline, struct context *c) {
    const char *required[] = {
        "fsck.mode=skip", "systemd.mask=k230-root-growth.service",
        "systemd.mask=register-nix-paths.service", "rd.systemd.unit=basic.target",
        "rd.systemd.debug_shell=ttyS0"
    };
    unsigned counts[5] = {0}, nonce = 0, from = 0, init = 0, ordinary = 0;
    char selected[PATH_MAX] = "", *save;
    for (char *t = strtok_r(cmdline, " \r\n\t", &save); t; t = strtok_r(NULL, " \r\n\t", &save)) {
        int known = 0;
        for (unsigned i = 0; i < 5; i++) if (!strcmp(t, required[i])) { counts[i]++; known = 1; }
        if (!strncmp(t, "k230.uobs.nonce=", 16)) {
            if (++nonce != 1 || !lower_hex(t + 16, 32)) return -1;
            strcpy(c->nonce, t + 16);
        } else if (!strncmp(t, "k230.uobs.from=", 15)) {
            if (++from != 1 || !uuid(t + 15)) return -1;
            strcpy(c->from, t + 15);
        } else if (!strncmp(t, "k230.uobs.init=", 15)) {
            if (++init != 1 || strlen(t + 15) >= sizeof c->init || !immutable_init(t + 15)) return -1;
            strcpy(c->init, t + 15);
        } else if (!strncmp(t, "init=", 5)) {
            if (++ordinary != 1 || strlen(t + 5) >= sizeof selected || !immutable_init(t + 5)) return -1;
            strcpy(selected, t + 5);
        } else if (!strncmp(t, "k230.uobs.", 10) || !strncmp(t, "rdinit", 6) ||
                   !strcmp(t, "clk_ignore_unused") ||
                   (!known && (!strncmp(t, "fsck.mode", 9) || !strncmp(t, "rd.", 3) ||
                    !strncmp(t, "systemd.", 8) || !strncmp(t, "udev.", 5)))) return -1;
    }
    for (unsigned i = 0; i < 5; i++) if (counts[i] != 1) return -1;
    return nonce == 1 && from == 1 && init == 1 && ordinary == 1 && !strcmp(selected, c->init) ? 0 : -1;
}
static int mount_guard(char *text) {
    unsigned p = 0, s = 0, d = 0, c = 0, r = 0;
    char *save;
    for (char *line = strtok_r(text, "\n", &save); line; line = strtok_r(NULL, "\n", &save)) {
        char src[512], path[512], fs[64], flags[512];
        if (sscanf(line, "%511s %511s %63s %511s", src, path, fs, flags) != 4) return -1;
        if (!strncmp(path, "/sysroot", 8) && (!path[8] || path[8] == '/' || path[8] == '\\')) return -1;
        if (!strcmp(path, "/proc")) { p++; if (strcmp(fs, "proc")) return -1; }
        else if (!strcmp(path, "/sys")) { s++; if (strcmp(fs, "sysfs")) return -1; }
        else if (!strcmp(path, "/dev")) { d++; if (strcmp(fs, "devtmpfs")) return -1; }
        else if (!strcmp(path, "/sys/fs/cgroup")) { c++; if (strcmp(fs, "cgroup2")) return -1; }
        else if (!strcmp(path, "/")) { r++; if (strcmp(fs, "rootfs") && strcmp(fs, "tmpfs") && strcmp(fs, "ramfs")) return -1; }
    }
    return p == 1 && s == 1 && d == 1 && c == 1 && r == 1 ? 0 : -1;
}
static int ppid_from(char *text, pid_t expected) {
    unsigned count = 0;
    char *save;
    for (char *line = strtok_r(text, "\n", &save); line; line = strtok_r(NULL, "\n", &save)) {
        if (!strncmp(line, "PPid:", 5)) {
            char tail; long n;
            if (sscanf(line + 5, " %ld %c", &n, &tail) != 1 || n != expected) return -1;
            count++;
        }
    }
    return count == 1 ? 0 : -1;
}
static int uid_from(const char *text) {
    unsigned seen = 0;
    for (const char *p = text; p && *p; p = strchr(p, '\n')) {
        if (*p == '\n') p++;
        if (!strncmp(p, "Uid:", 4)) {
            unsigned a, b, c, d; char tail;
            const char *end = strchr(p, '\n');
            char line[128]; size_t len = end ? (size_t)(end-p) : strlen(p);
            if (len >= sizeof line) return -1;
            memcpy(line,p,len);line[len]=0;
            if (sscanf(line+4, " %u %u %u %u %c", &a,&b,&c,&d,&tail) != 4 || a || b || c || d) return -1;
            seen++;
        }
    }
    return seen == 1 ? 0 : -1;
}
static int reap_bounded(pid_t pid, int *status, int ms) {
    int64_t start = now_ms();
    if (start < 0) return -1;
    int64_t end = start + ms;
    for (;;) {
        int64_t now = now_ms();
        if (now < 0 || now >= end) return -1;
        pid_t n = waitpid(pid, status, WNOHANG);
        if (n == pid) return 0;
        if (n < 0 && errno != EINTR) return -1;
        if (wait_ms(10)) return -1;
    }
}
/* subprocesses inherit the enclosing guard's process group. */
static int capture(char *const argv[], char *out, size_t size) {
    int64_t start = now_ms();
    if (start < 0) return -1;
    int fds[2];
    if (pipe2(fds, O_CLOEXEC | O_NONBLOCK)) return -1;
    pid_t pid = fork();
    if (pid == 0) {
        close(fds[0]);
        int flags = fcntl(fds[1], F_GETFL);
        if (flags < 0 || fcntl(fds[1], F_SETFL, flags & ~O_NONBLOCK) < 0 || dup2(fds[1], STDOUT_FILENO) < 0) _exit(127);
        int nullfd = open("/dev/null", O_RDWR | O_CLOEXEC);
        if (nullfd < 0 || dup2(nullfd, STDIN_FILENO) < 0 || dup2(nullfd, STDERR_FILENO) < 0) _exit(127);
        close(nullfd); close(fds[1]);
        execv(argv[0], argv); _exit(127);
    }
    close(fds[1]);
    if (pid < 0) { close(fds[0]); return -1; }
    size_t used = 0; int status = 0, finished = 0, eof = 0, bad = 0;
    int64_t end = start + CHILD_MS;
    while (!(finished && eof)) {
        int64_t now = now_ms();
        if (now < 0) { bad = 1; break; }
        if (now >= end) break;
        struct pollfd p = { .fd = fds[0], .events = POLLIN | POLLHUP };
        int polled = poll(&p, 1, 20);
        if (polled < 0 && errno != EINTR) { bad = 1; break; }
        if (polled > 0) {
            char buf[512]; ssize_t n = read(fds[0], buf, sizeof buf);
            if (n == 0) eof = 1;
            else if (n > 0) {
                if (used + (size_t)n >= size || memchr(buf, 0, (size_t)n)) { bad = 1; break; }
                memcpy(out + used, buf, (size_t)n); used += (size_t)n;
            } else if (errno != EAGAIN && errno != EINTR) { bad = 1; break; }
        }
        pid_t n = finished ? 0 : waitpid(pid, &status, WNOHANG);
        if (n == pid) finished = 1;
        else if (n < 0 && errno != EINTR) { bad = 1; break; }
    }
    close(fds[0]);
    if (bad || !finished || !eof) {
        if (!finished) { kill(pid, SIGKILL); (void)reap_bounded(pid, &status, 500); }
        return -1;
    }
    out[used] = 0;
    return WIFEXITED(status) && WEXITSTATUS(status) == 0 ? 0 : -1;
}
static int unit_block(char *block, pid_t main_pid, unsigned *seen) {
    static const char *ids[] = {"debug-shell.service", "sysroot.mount", "initrd-find-nixos-closure.service",
        "initrd-nixos-activation.service", "initrd-switch-root.target", "initrd-switch-root.service"};
    unsigned fields = 0; int which = -1;
    char *values[7] = {0}, *save;
    const char *keys[] = {"Id", "ActiveState", "SubState", "Job", "TTYPath", "ExecMainPID", "LoadState"};
    for (char *line = strtok_r(block, "\n", &save); line; line = strtok_r(NULL, "\n", &save)) {
        char *eq = strchr(line, '=');
        if (!eq) return -1;
        *eq++ = 0; unsigned i;
        for (i = 0; i < 7; i++) if (!strcmp(line, keys[i])) break;
        if (i == 7 || (fields & (1u << i))) return -1;
        fields |= 1u << i; values[i] = eq;
    }
    if (!values[0]) return -1;
    for (unsigned i = 0; i < 6; i++) if (!strcmp(values[0], ids[i])) which = (int)i;
    if (which < 0 || (*seen & (1u << which)) || fields != (which ? 79u : 127u)) return -1;
    if (strcmp(values[1], which ? "inactive" : "active") ||
        strcmp(values[2], which ? "dead" : "running") || *values[3] || strcmp(values[6], "loaded")) return -1;
    if (!which) {
        char pid[32]; snprintf(pid, sizeof pid, "%ld", (long)main_pid);
        if (strcmp(values[4], "/dev/ttyS0") || strcmp(values[5], pid)) return -1;
    }
    *seen |= 1u << which; return 0;
}
static int unit_guard(char *text, pid_t main_pid, unsigned expected) {
    unsigned seen = 0;
    char *start = text;
    while (*start) {
        char *end = strstr(start, "\n\n");
        if (end) *end = 0;
        if (unit_block(start, main_pid, &seen)) return -1;
        if (!end) break;
        start = end + 2;
    }
    return seen == expected ? 0 : -1;
}
static int live_guard(struct context *c, int renewed) {
    char text[TEXT_MAX], path[128], actual[PATH_MAX];
    struct utsname u; struct stat st;
    if (getuid() || c->main_pid <= 1 || uname(&u) || strcmp(u.release, "7.3.0-rc5")) return -1;
    if (access("/etc/initrd-release", F_OK) || read_text("/etc/k230-uobs-version", text, sizeof text) || strcmp(text, "1\n")) return -1;
    if (read_text("/proc/sys/kernel/random/boot_id", text, sizeof text)) return -1;
    text[strcspn(text, "\n")] = 0;
    if (!uuid(text) || !strcmp(text, c->from) || (renewed && strcmp(text, c->boot))) return -1;
    if (!renewed) strcpy(c->boot, text);
    if (link_text("/proc/1/exe", actual, sizeof actual) || strcmp(actual, UOBS_SYSTEMD)) return -1;
    snprintf(path, sizeof path, "/proc/%ld/status", (long)c->main_pid);
    if (read_text(path, text, sizeof text) || uid_from(text) || ppid_from(text, 1)) return -1;
    snprintf(path, sizeof path, "/proc/%ld/exe", (long)c->main_pid);
    if (link_text(path, actual, sizeof actual) || strcmp(actual, renewed ? c->shell : c->helper)) return -1;
    snprintf(path, sizeof path, "/proc/%ld/fd/0", (long)c->main_pid);
    if (link_text(path, actual, sizeof actual) || strcmp(actual, "/dev/ttyS0")) return -1;
    if (fstat(STDIN_FILENO, &st) || !S_ISCHR(st.st_mode) || major(st.st_rdev) != 4 || minor(st.st_rdev) != 64) return -1;
    if (read_text("/proc/cmdline", text, sizeof text)) return -1;
    struct context again = {0};
    if (parse_context(text, &again) || strcmp(again.nonce, c->nonce) || strcmp(again.from, c->from) || strcmp(again.init, c->init)) return -1;
    if (read_text("/proc/mounts", text, sizeof text) || mount_guard(text)) return -1;
    char *shell_args[] = {"/bin/systemctl", "--no-pager", "show", "debug-shell.service",
        "--property=Id,LoadState,ExecMainPID,ActiveState,SubState,TTYPath,Job", NULL};
    if (capture(shell_args, text, sizeof text) || unit_guard(text, c->main_pid, 1)) return -1;
    char *root_args[] = {"/bin/systemctl", "--no-pager", "show", "sysroot.mount",
        "initrd-find-nixos-closure.service", "initrd-nixos-activation.service", "initrd-switch-root.target",
        "initrd-switch-root.service", "--property=Id,LoadState,ActiveState,SubState,Job", NULL};
    if (capture(root_args, text, sizeof text) || unit_guard(text, c->main_pid, 62)) return -1;
    return 0;
}
/* Return only a targeted aggregate IRQ count; never emit the raw table. */
static int irq_count(char *text, int irq, uint64_t *total) {
    unsigned cpus = 0, matches = 0; char *save;
    char *line = strtok_r(text, "\n", &save);
    if (!line) return -1;
    for (char *p = line; (p = strstr(p, "CPU")); p += 3) cpus++;
    if (!cpus || cpus > 64) return -1;
    for (line = strtok_r(NULL, "\n", &save); line; line = strtok_r(NULL, "\n", &save)) {
        char *p = line, *end; errno = 0;
        unsigned long n = strtoul(p, &end, 10);
        if (errno || end == p || *end != ':' || n != (unsigned)irq) continue;
        if (++matches != 1) return -1;
        p = end + 1; uint64_t sum = 0;
        for (unsigned i = 0; i < cpus; i++) {
            while (*p == ' ' || *p == '\t') p++;
            if (!isdigit((unsigned char)*p)) return -1;
            errno = 0; unsigned long long value = strtoull(p, &end, 10);
            if (errno || UINT64_MAX - sum < value || !isspace((unsigned char)*end)) return -1;
            sum += value; p = end;
        }
        *total = sum;
    }
    return matches == 1 ? 0 : -1;
}
static int take_sample(struct sample *s) {
    memset(s, 0, sizeof *s);
    struct serial_struct serial = {0};
    if (tcgetattr(STDIN_FILENO, &s->term) || ioctl(STDIN_FILENO, TIOCGETD, &s->ldisc) ||
        ioctl(STDIN_FILENO, TIOCGICOUNT, &s->count) || ioctl(STDIN_FILENO, TIOCGSERIAL, &serial) ||
        serial.line != 0 || serial.irq <= 0 || serial.irq > 1048576) return -1;
    s->irq = serial.irq;
    char text[TEXT_MAX];
    if (!read_text("/proc/interrupts", text, sizeof text) && !irq_count(text, s->irq, &s->irq_total)) s->irq_available = 1;
    else s->irq_total = 0;
    char resolved[PATH_MAX];
    if (!realpath("/sys/class/tty/ttyS0/device", resolved)) return -1;
    char *part = strstr(resolved, "/91400000.serial");
    if (!part || (part[16] && part[16] != '/')) return -1;
    part[16] = 0;
    if (strlen(resolved) + strlen("/power/runtime_status") >= sizeof resolved) return -1;
    strcat(resolved, "/power/runtime_status");
    strcpy(s->runtime, "unknown");
    if (!read_text(resolved, text, sizeof text)) {
        text[strcspn(text, "\n")] = 0;
        if (!strcmp(text, "active") || !strcmp(text, "suspended")) strcpy(s->runtime, text);
    }
    return 0;
}
/* Isolate every potentially blocking guard/getter; no D-state recovery claim. */
typedef int (*operation)(void *, void *);
struct guard_arg { struct context c; int renewed; };
static int guard_operation(void *arg, void *out) {
    struct guard_arg *g = arg;
    if (live_guard(&g->c, g->renewed)) return -1;
    memcpy(out, g->c.boot, sizeof g->c.boot); return 0;
}
static int sample_operation(void *arg, void *out) { (void)arg; return take_sample(out); }
static int bounded(operation fn, void *arg, void *out, size_t size, int ms) {
    int64_t start = now_ms();
    if (start < 0) return -1;
    int fds[2];
    if (pipe2(fds, O_CLOEXEC | O_NONBLOCK)) return -1;
    pid_t pid = fork();
    if (pid == 0) {
        close(fds[0]);
        if (setpgid(0, 0)) _exit(127);
        unsigned char *result = calloc(1, size);
        if (!result || fn(arg, result)) _exit(1);
        ssize_t n = write(fds[1], result, size);
        _exit(n == (ssize_t)size ? 0 : 1);
    }
    close(fds[1]);
    if (pid < 0) { close(fds[0]); return -1; }
    (void)setpgid(pid, pid);
    int status = 0, done = 0, eof = 0, bad = 0; size_t used = 0;
    int64_t end = start + ms;
    while (!(done && eof)) {
        int64_t now = now_ms();
        if (now < 0) { bad = 1; break; }
        if (now >= end) break;
        struct pollfd p = {.fd=fds[0], .events=POLLIN|POLLHUP};
        int n = poll(&p, 1, 20);
        if (n < 0 && errno != EINTR) { bad = 1; break; }
        if (n > 0) {
            unsigned char buf[1024]; ssize_t got = read(fds[0], buf, sizeof buf);
            if (!got) eof = 1;
            else if (got > 0) {
                if (used + (size_t)got > size) { bad = 1; break; }
                memcpy((char *)out + used, buf, (size_t)got); used += (size_t)got;
            } else if (errno != EAGAIN && errno != EINTR) { bad = 1; break; }
        }
        pid_t got = done ? 0 : waitpid(pid, &status, WNOHANG);
        if (got == pid) done = 1;
        else if (got < 0 && errno != EINTR) { bad = 1; break; }
    }
    close(fds[0]);
    if (bad || !done || !eof || used != size) {
        kill(-pid, SIGKILL);
        if (!done) (void)reap_bounded(pid, &status, 500);
        return -1;
    }
    return WIFEXITED(status) && WEXITSTATUS(status) == 0 ? 0 : -1;
}
static int guarded(struct context *c, int renewed) {
    struct guard_arg arg = {.c=*c, .renewed=renewed};
    char boot[37];
    if (bounded(guard_operation, &arg, boot, sizeof boot, GUARD_MS)) return -1;
    memcpy(c->boot, boot, sizeof boot); return 0;
}
static uint32_t crc32(const unsigned char *bytes, size_t len) {
    uint32_t crc = UINT32_MAX;
    for (size_t i = 0; i < len; i++) {
        crc ^= bytes[i];
        for (int j = 0; j < 8; j++) crc = (crc >> 1) ^ ((crc & 1) ? 0xedb88320u : 0);
    }
    return crc ^ UINT32_MAX;
}
static int emit(int fd, const char *nonce, unsigned seq, const char *stage, const char *payload) {
    size_t len = strlen(payload);
    if (!lower_hex(nonce, 32) || len > PAYLOAD_MAX) return -1;
    char hex[PAYLOAD_MAX * 2 + 1], frame[FRAME_MAX];
    for (size_t i = 0; i < len; i++) snprintf(hex + 2*i, 3, "%02x", (unsigned char)payload[i]);
    hex[2*len] = 0;
    int n = snprintf(frame, sizeof frame, "<6>\nK230_UOBS_V1 %s %u %s %zu %08" PRIx32 " %s\n",
        nonce, seq, stage, len, crc32((const unsigned char *)payload, len), hex);
    if (n < 0 || (size_t)n >= sizeof frame) return -1;
    /* One nonblocking record write: no partial retry or claimed truncation. */
    return write(fd, frame, (size_t)n) == n ? 0 : -1;
}
static int fail(int fd, struct context *c, unsigned seq, const char *phase, const char *reason) {
    char payload[96];
    int n = snprintf(payload, sizeof payload, "phase=%s\nreason=%s\n", phase, reason);
    if (n < 0 || (size_t)n >= sizeof payload) return -1;
    return emit(fd, c->nonce, seq, "failed", payload);
}
static int sample_payload(struct sample *s, const char *which, char *out, size_t size) {
    int n = snprintf(out, size,
        "sample=%s\niflag=%08x\noflag=%08x\ncflag=%08x\nlflag=%08x\nispeed_code=%u\nospeed_code=%u\n"
        "ldisc=%d\nrx=%u\ntx=%u\nframe=%u\noverrun=%u\nparity=%u\nbrk=%u\nbuf_overrun=%u\n"
        "irq=%d\nirq_available=%d\nirq_total=%" PRIu64 "\nruntime=%s\n",
        which, (unsigned)s->term.c_iflag, (unsigned)s->term.c_oflag, (unsigned)s->term.c_cflag,
        (unsigned)s->term.c_lflag, (unsigned)cfgetispeed(&s->term), (unsigned)cfgetospeed(&s->term),
        s->ldisc, (unsigned)s->count.rx, (unsigned)s->count.tx, (unsigned)s->count.frame,
        (unsigned)s->count.overrun, (unsigned)s->count.parity, (unsigned)s->count.brk,
        (unsigned)s->count.buf_overrun, s->irq, s->irq_available, s->irq_total, s->runtime);
    return n >= 0 && (size_t)n < size && n <= PAYLOAD_MAX ? 0 : -1;
}
struct observer_ops {
    int (*snapshot)(struct sample *);
    int (*guard)(struct context *, int);
    int (*reboot)(void);
};
static int snapshot_bounded(struct sample *s) {
    return bounded(sample_operation, NULL, s, sizeof *s, GUARD_MS);
}
static int request_reboot(void) {
    /* Kernel-log ack is already retained. Do not depend on buffered TTY TX
     * or let the reboot utility consume the sole controlled receipt. */
    int nullfd = open("/dev/null", O_RDWR | O_CLOEXEC);
    if (nullfd < 0) return -1;
    for (int fd = 0; fd < 3; fd++) {
        if (dup2(nullfd, fd) < 0) {close(nullfd);return -1;}
    }
    if (nullfd > 2) close(nullfd);
    char *args[] = {"/bin/reboot", "-ff", NULL};
    execv(args[0], args);
    return -1;
}
static int observer_with(int output, struct context c, struct sample before, const struct observer_ops *ops) {
    char payload[PAYLOAD_MAX + 1];
    int n = snprintf(payload, sizeof payload, "boot_id=%s\nshell_pid=%ld\nguards=1\nwindow_ms=%d\n",
        c.boot, (long)c.main_pid, WINDOW_MS);
    if (n < 0 || (size_t)n >= sizeof payload || emit(output, c.nonce, 0, "ready", payload)) return 1;
    if (sample_payload(&before, "before", payload, sizeof payload) || emit(output, c.nonce, 1, "before", payload)) return 1;
    if (wait_ms(WINDOW_MS)) { (void)fail(output, &c, 2, "observe", "clock"); return 1; }
    struct sample after;
    if (ops->snapshot(&after)) { (void)fail(output, &c, 2, "observe", "snapshot"); return 1; }
    if (sample_payload(&after, "after", payload, sizeof payload) || emit(output, c.nonce, 2, "after", payload)) return 1;
    if (getppid() != c.main_pid || ops->guard(&c, 1)) { (void)fail(output, &c, 3, "renew", "guard"); return 1; }
    n = snprintf(payload, sizeof payload, "boot_id=%s\nshell_pid=%ld\nguards=1\nreboot=1\n", c.boot, (long)c.main_pid);
    if (n < 0 || (size_t)n >= sizeof payload || emit(output, c.nonce, 3, "return", payload)) return 1;
    /* Ack means an attempted exec, not guaranteed restart. No duplicate frame. */
    (void)ops->reboot();
    return 1;
}
static int observer(int output, struct context c, struct sample before) {
    const struct observer_ops ops = {snapshot_bounded, guarded, request_reboot};
    return observer_with(output, c, before, &ops);
}
int main(int argc, char **argv) {
    if (argc != 1) return 2;
    struct context c = {0}; char text[TEXT_MAX];
    c.main_pid = getpid();
    if (read_text("/proc/cmdline", text, sizeof text) || parse_context(text, &c) ||
        !realpath(argv[0], c.helper) || !realpath("/bin/sh", c.shell)) return 2;
    int output = open("/dev/kmsg", O_WRONLY | O_NONBLOCK | O_CLOEXEC);
    if (output < 0) return 2;
    if (guarded(&c, 0)) { (void)fail(output, &c, 0, "initial", "guard"); close(output); return 2; }
    struct sample before;
    if (bounded(sample_operation, NULL, &before, sizeof before, GUARD_MS)) {
        (void)fail(output, &c, 0, "initial", "snapshot"); close(output); return 2;
    }
    pid_t child = fork();
    if (child < 0) { (void)fail(output, &c, 0, "initial", "fork"); close(output); return 2; }
    if (child == 0) _exit(observer(output, c, before));
    char *args[] = {"/bin/sh", NULL};
    execv(args[0], args);
    /* Observer will fail renewed ownership if shell exec fails or parent exits. */
    close(output); return 127;
}
