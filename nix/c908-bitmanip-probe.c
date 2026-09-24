/* Diagnostic userspace probe only. Build startup with -march=rv64gc.
 * Each extension instruction is isolated in a never-inlined helper and runs
 * in a bounded child. Neither DT nor cpuinfo is an execution gate. */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <inttypes.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

enum family { ZBA, ZBB, ZBC, ZBS };
struct vector { enum family family; uint64_t a, b, expected; };
#ifdef __riscv
static const char *names[] = {"zba", "zbb", "zbc", "zbs"};
#endif
static const struct vector vectors[] = {
    {ZBA, 0, 0, 0}, {ZBA, 1, 1, 3},
    {ZBA, UINT64_MAX, 7, 5},
    {ZBA, UINT64_C(0x123456789abcdef0), UINT64_C(0xfedcba9876543210), UINT64_C(0x23456789abcdeff0)},
    {ZBB, 0, 0, 0}, {ZBB, UINT64_MAX, 0, UINT64_MAX},
    {ZBB, UINT64_C(0xaaaaaaaaaaaaaaaa), UINT64_C(0x0f0f0f0f0f0f0f0f), UINT64_C(0xa0a0a0a0a0a0a0a0)},
    {ZBB, UINT64_C(0x123456789abcdef0), UINT64_MAX, 0},
    {ZBC, 0, 0, 0}, {ZBC, 1, UINT64_MAX, UINT64_MAX},
    {ZBC, UINT64_MAX, 2, UINT64_C(0xfffffffffffffffe)},
    {ZBC, UINT64_C(0x123456789abcdef0), UINT64_C(0x13579bdf2468ace0), UINT64_C(0x80f7047112695a00)},
    {ZBS, 0, 0, 1}, {ZBS, 0, 63, UINT64_C(0x8000000000000000)},
    {ZBS, UINT64_MAX, 7, UINT64_MAX},
    {ZBS, UINT64_C(0x123456789abcdef0), 64, UINT64_C(0x123456789abcdef1)},
};

static uint64_t reference(enum family family, uint64_t a, uint64_t b) {
    switch (family) {
    case ZBA: return b + (a << 1);
    case ZBB: return a & ~b;
    case ZBC: {
        uint64_t result = 0;
        for (unsigned i = 0; i < 64; ++i)
            if ((b >> i) & 1) result ^= a << i;
        return result;
    }
    case ZBS: return a | (UINT64_C(1) << (b & 63));
    }
    abort();
}

#ifdef __riscv
__attribute__((noinline)) static uint64_t zba(uint64_t a, uint64_t b) {
    uint64_t out;
    __asm__ volatile (".option push\n.option arch,+zba\nsh1add %0,%1,%2\n.option pop"
                      : "=r"(out) : "r"(a), "r"(b));
    return out;
}
__attribute__((noinline)) static uint64_t zbb(uint64_t a, uint64_t b) {
    uint64_t out;
    __asm__ volatile (".option push\n.option arch,+zbb\nandn %0,%1,%2\n.option pop"
                      : "=r"(out) : "r"(a), "r"(b));
    return out;
}
__attribute__((noinline)) static uint64_t zbc(uint64_t a, uint64_t b) {
    uint64_t out;
    __asm__ volatile (".option push\n.option arch,+zbc\nclmul %0,%1,%2\n.option pop"
                      : "=r"(out) : "r"(a), "r"(b));
    return out;
}
__attribute__((noinline)) static uint64_t zbs(uint64_t a, uint64_t b) {
    uint64_t out;
    __asm__ volatile (".option push\n.option arch,+zbs\nbset %0,%1,%2\n.option pop"
                      : "=r"(out) : "r"(a), "r"(b));
    return out;
}
static uint64_t extension(enum family family, uint64_t a, uint64_t b) {
    switch (family) {
    case ZBA: return zba(a, b);
    case ZBB: return zbb(a, b);
    case ZBC: return zbc(a, b);
    case ZBS: return zbs(a, b);
    }
    abort();
}
#endif

static int64_t now_ms(void) {
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t)) { perror("clock_gettime"); exit(2); }
    return (int64_t)t.tv_sec * 1000 + t.tv_nsec / 1000000;
}

/* Return 0 exact, 1 mismatch, 2 SIGILL, 3 timeout/other failure. */
static int guarded(const struct vector *v, int control) {
    int pipefd[2];
    if (pipe(pipefd)) return 3;
    pid_t child = fork();
    if (child < 0) { close(pipefd[0]); close(pipefd[1]); return 3; }
    if (child == 0) {
        close(pipefd[0]);
        signal(SIGILL, SIG_DFL);
        sigset_t unblocked;
        sigemptyset(&unblocked);
        sigaddset(&unblocked, SIGILL);
        sigprocmask(SIG_UNBLOCK, &unblocked, NULL);
        if (control == 1) raise(SIGILL);
        if (control == 2) for (;;) pause();
        uint64_t observed = 0;
        if (control == 3) observed = v->expected ^ 1;
#ifdef __riscv
        else observed = extension(v->family, v->a, v->b);
#else
        else observed = reference(v->family, v->a, v->b);
#endif
        ssize_t n = write(pipefd[1], &observed, sizeof observed);
        close(pipefd[1]);
        _exit(n == sizeof observed ? 0 : 2);
    }
    close(pipefd[1]);
    int status = 0;
    int64_t deadline = now_ms() + 1000;
    for (;;) {
        pid_t ended = waitpid(child, &status, WNOHANG);
        if (ended == child) break;
        if (ended < 0 && errno != EINTR) { close(pipefd[0]); return 3; }
        if (now_ms() >= deadline) {
            kill(child, SIGKILL);
            waitpid(child, &status, 0);
            close(pipefd[0]);
            return 3;
        }
        struct timespec delay = {.tv_sec = 0, .tv_nsec = 1000000};
        nanosleep(&delay, NULL);
    }
    if (WIFSIGNALED(status)) { close(pipefd[0]); return WTERMSIG(status) == SIGILL ? 2 : 3; }
    uint64_t observed = 0;
    ssize_t n = read(pipefd[0], &observed, sizeof observed);
    close(pipefd[0]);
    if (!WIFEXITED(status) || WEXITSTATUS(status) || n != sizeof observed) return 3;
    return observed == v->expected ? 0 : 1;
}

static int self_test(void) {
    unsigned checked = 0;
    for (size_t i = 0; i < sizeof vectors / sizeof vectors[0]; ++i) {
        if (reference(vectors[i].family, vectors[i].a, vectors[i].b) != vectors[i].expected) return 1;
        ++checked;
    }
    if (guarded(&vectors[0], 1) != 2 || guarded(&vectors[0], 2) != 3 || guarded(&vectors[0], 3) != 1)
        return 1;
    printf("K230_BITMANIP_SELF_TEST {\"status\":\"PASS\",\"evidence_class\":\"host-scalar-and-fault-harness\",\"vectors\":%u}\n", checked);
    return 0;
}

static int probe(void) {
#ifndef __riscv
    fputs("--probe requires a RISC-V build; native host checks use --self-test\n", stderr);
    return 2;
#else
    int failure = 0;
    printf("K230_BITMANIP_RESULT {\"evidence_class\":\"runtime-probe-unclassified\",\"startup_isa\":\"rv64gc\",\"families\":[");
    for (enum family family = ZBA; family <= ZBS; family = (enum family)(family + 1)) {
        unsigned passed = 0, unsupported = 0, wrong = 0, errors = 0;
        char cases[sizeof vectors / sizeof vectors[0] + 1] = {0};
        unsigned case_index = 0;
        for (size_t i = 0; i < sizeof vectors / sizeof vectors[0]; ++i) {
            if (vectors[i].family != family) continue;
            int result = guarded(&vectors[i], 0);
            if (result == 0) { ++passed; cases[case_index++] = 'P'; }
            else if (result == 1) { ++wrong; cases[case_index++] = 'F'; }
            else if (result == 2) { ++unsupported; cases[case_index++] = 'I'; }
            else { ++errors; cases[case_index++] = 'E'; }
        }
        if (family) putchar(',');
        const char *state = errors || (passed && unsupported) ? "ERROR" : wrong ? "FAIL" :
                            unsupported ? "UNSUPPORTED" : "PASS";
        if (errors || wrong || (passed && unsupported)) failure = 1;
        printf("{\"extension\":\"%s\",\"status\":\"%s\",\"cases\":\"%s\",\"passed\":%u,\"sigill\":%u,\"wrong\":%u,\"errors\":%u}",
               names[family], state, cases, passed, unsupported, wrong, errors);
    }
    puts("]}");
    return failure;
#endif
}

int main(int argc, char **argv) {
    if (argc != 2) { fputs("usage: c908-bitmanip-probe --self-test|--probe\n", stderr); return 2; }
    if (strcmp(argv[1], "--self-test") == 0) return self_test();
    if (strcmp(argv[1], "--probe") == 0) return probe();
    fputs("unknown option\n", stderr);
    return 2;
}
