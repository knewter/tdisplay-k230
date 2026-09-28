/* K230 physical CPU0 M-mode probe. Never part of the normal boot image.
 * U-Boot loads the binary at 0x07000000, then boot_baremetal 0 releases CPU0.
 * The output is in three untouched scratch pages at 0x07002000,
 * 0x07003000 and 0x07004000. Read each page only once from U-Boot, since
 * the two physical cores do not have a proven coherent-cache contract.
 */
    .option norvc
    .option norelax
    .section .text, "ax"
    .globl _start
_start:
    lla t0, heartbeat_output
    csrr t1, mhartid
    sd t1, 8(t0)
    csrr t1, misa
    sd t1, 16(t0)
    li t1, 0
1:
    addi t1, t1, 1
    sd t1, 0(t0)
    li t3, 0x07003000
    sd t1, 0(t3)
    li t3, 0x07004000
    sd t1, 0(t3)
    fence rw, rw
    /* Pinned U-Boot cache.c uses this encoding for l2cache.ciall.
     * Separate L2s mean a plain fence cannot publish a CPU0 cache line. */
    .word 0x0170000b
    li t2, 8000000
2:
    addi t2, t2, -1
    bnez t2, 2b
    j 1b
