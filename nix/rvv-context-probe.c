#define _GNU_SOURCE
#include <asm/hwprobe.h>
#include <errno.h>
#include <inttypes.h>
#include <sched.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/syscall.h>
#include <sys/resource.h>
#include <sys/time.h>
#include <sys/wait.h>
#include <unistd.h>

/* This translation unit is compiled for RV64GC. The assembly entrypoints are
 * unreachable unless the kernel advertises usable standard V through hwprobe. */
extern long rvv_roundtrip(uint32_t *, size_t, uint32_t, volatile sig_atomic_t *);
extern void rvv_clobber(void);
static volatile sig_atomic_t signals;
static unsigned completed;
static long involuntary_switches;

static void handler(int signo) {
    (void)signo;
    rvv_clobber();
    signals++;
}

static int exercise(uint32_t salt) {
    uint32_t output[64];
    int result = 0;
    struct itimerval timer = { .it_interval = {0, 1000}, .it_value = {0, 1000} };
    if (setitimer(ITIMER_REAL, &timer, NULL)) return 5;
    for (uint32_t i = 0; i < 2000; i++) {
        const uint32_t seed = salt + i * 101;
        long n = rvv_roundtrip(output, 64, seed, &signals);
        if (n < 0) { result = 100 - (int)n; break; }
        if (n == 0 || n > 64) { result = 1; break; }
        for (long j = 0; j < n; j++)
            if (output[j] != seed + (uint32_t)j) { result = 2; break; }
        if (result) break;
        completed++;
    }
    timer = (struct itimerval){0};
    if (setitimer(ITIMER_REAL, &timer, NULL)) return 6;
    if (result) return result;
    struct rusage usage;
    if (getrusage(RUSAGE_SELF, &usage)) return 7;
    involuntary_switches = usage.ru_nivcsw;
    return signals >= 2000 && usage.ru_nivcsw > 0 ? 0 : 8;
}

int main(void) {
    struct riscv_hwprobe pair = { RISCV_HWPROBE_KEY_IMA_EXT_0, 0 };
    long result = syscall(SYS_riscv_hwprobe, &pair, 1, 0, NULL, 0);
    if (result < 0 || pair.key != RISCV_HWPROBE_KEY_IMA_EXT_0 ||
            !(pair.value & RISCV_HWPROBE_IMA_V)) {
        printf("{\"status\":\"SKIP\",\"hwprobe_result\":%ld,"
               "\"errno\":%d,\"features\":%" PRIu64 "}\n",
               result, result < 0 ? errno : 0, (uint64_t)pair.value);
        return 77;
    }
    struct sigaction action = { .sa_handler = handler };
    sigemptyset(&action.sa_mask);
    if (sigaction(SIGALRM, &action, NULL)) return 3;
    /* Both processes compete on one allowed CPU; no system affinity changes. */
    cpu_set_t allowed, selected;
    if (sched_getaffinity(0, sizeof allowed, &allowed)) return 9;
    CPU_ZERO(&selected);
    for (int cpu = 0; cpu < CPU_SETSIZE; cpu++)
        if (CPU_ISSET(cpu, &allowed)) { CPU_SET(cpu, &selected); break; }
    if (sched_setaffinity(0, sizeof selected, &selected)) return 10;
    pid_t child = fork();
    if (child < 0) return 4;
    if (!child) _exit(exercise(0x12345678));
    int parent = exercise(0x87654321), status = 0;
    pid_t waited;
    do { waited = waitpid(child, &status, 0); } while (waited < 0 && errno == EINTR);
    int good = parent == 0 && waited == child && WIFEXITED(status) &&
               WEXITSTATUS(status) == 0;
    printf("{\"status\":\"%s\",\"processes\":2,"
           "\"required_iterations_per_process\":2000,\"parent_iterations\":%u,"
           "\"parent_signals\":%d,\"parent_involuntary_switches\":%ld,"
           "\"parent_result\":%d,\"child_wait_status\":%d}\n",
           good ? "PASS" : "FAIL", completed, signals, involuntary_switches, parent, status);
    return good ? 0 : 1;
}
