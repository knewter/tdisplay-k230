/* Read-only timing probe: no MMIO writes and no runtime-library dependency. */
unsigned long long k230_read_time(void) {
    unsigned long long value;
    __asm__ volatile ("rdtime %0" : "=r" (value) :: "memory");
    return value;
}
