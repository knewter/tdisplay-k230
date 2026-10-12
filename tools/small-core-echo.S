/* K230 physical CPU0 M-mode echo/ping payload. Never part of the normal boot
 * image. Sibling of tools/small-core-heartbeat.S: scalar RV64, no runtime, no
 * stack, no MMIO other than DRAM. Load with U-Boot, then boot_baremetal 0.
 *
 * Slot page (echo_page = PAYLOAD_BASE + 0x2000, see small-core-echo.ld).
 * All fields are little-endian; 32-bit fields are single aligned 32-bit
 * stores so U-Boot mw.l / md.l and a 32-bit Linux accessor see whole values.
 * Each region sits in its own 64-byte line.
 *
 *   +0x000  REQUEST line, written by the other side (CPU1 / Linux)
 *           +0x00 u32 req_seq     any value other than the one last served;
 *                                 write it LAST, after req_value
 *           +0x04 u32 req_value
 *   +0x040  STATUS line, written by CPU0
 *           +0x40 u64 heartbeat   slow counter, ~every 2^19 polls
 *           +0x48 u64 mhartid
 *           +0x50 u64 misa
 *           +0x58 u32 magic       0x4f484345 ("ECHO" little-endian)
 *           +0x5c u32 served      number of requests answered
 *           +0x60 u32 last_seq    most recent req_seq answered
 *   +0x100 + 0x40*(req_seq & 7)   RESPONSE line for that request
 *           +0x00 u32 rsp_seq     == req_seq; written LAST (fence w,w first)
 *           +0x04 u32 rsp_value   == req_value + 1 (wraps at 32 bits)
 *           +0x08 u32 rsp_inv     == ~req_value
 *           +0x0c u32 rsp_served  value of served after this answer
 *
 * Response lines are indexed by req_seq & 7 so a reader on a core that caches
 * the page reads each line for the first time only after it was written.
 * At start CPU0 zeroes the REQUEST line and the eight RESPONSE seq words, so
 * the first request must use a nonzero req_seq.
 *
 * Cache handling matches the heartbeat: a fence plus the pinned
 * l2cache.ciall (0x0170000b, U-Boot cache.c:158-161) after every write CPU0
 * wants the other core to see, and again BEFORE every read of the request
 * line so CPU0 never serves a stale copy of its own cache. The cost of ciall
 * per poll is not measured here; with CPU0 running uncached (consistent with
 * the heartbeat's ~2.5 s per 8M-iteration loop) a poll is ~10 instructions,
 * so response latency should be on the order of microseconds, not the
 * heartbeat's seconds. Limits: no coherence with the other core is assumed
 * or provided; polling only, no interrupts, no mailbox hardware.
 */
    .option norvc
    .option norelax
    .section .text, "ax"
    .globl _start
_start:
    lla s0, echo_page
    csrr t1, mhartid
    sd t1, 0x48(s0)
    csrr t1, misa
    sd t1, 0x50(s0)
    li t1, 0x4f484345
    sw t1, 0x58(s0)
    sw zero, 0x5c(s0)
    sw zero, 0x60(s0)
    sd zero, 0x40(s0)
    sd zero, 0(s0)
    /* zero the rsp_seq word of all eight response lines */
    addi t0, s0, 0x100
    li t1, 8
1:
    sw zero, 0(t0)
    addi t0, t0, 0x40
    addi t1, t1, -1
    bnez t1, 1b
    li s1, 0                    /* last served req_seq */
    li s2, 0                    /* served count */
    li s3, 0                    /* heartbeat value */
    li s4, 1 << 19              /* polls until the next heartbeat publish */
    fence rw, rw
    .word 0x0170000b            /* l2cache.ciall: publish the zeroed page */
poll:
    fence rw, rw
    .word 0x0170000b            /* l2cache.ciall before reading the request */
    lwu t1, 0(s0)               /* req_seq */
    bne t1, s1, serve
    addi s4, s4, -1
    bnez s4, poll
    /* slow heartbeat, separate from the request path */
    addi s3, s3, 1
    sd s3, 0x40(s0)
    li s4, 1 << 19
    fence rw, rw
    .word 0x0170000b
    j poll
serve:
    lw t2, 4(s0)                /* req_value */
    andi t3, t1, 7
    slli t3, t3, 6
    add t3, t3, s0
    addi t3, t3, 0x100          /* response line */
    addi s2, s2, 1
    addiw t4, t2, 1
    sw t4, 4(t3)
    not t4, t2
    sw t4, 8(t3)
    sw s2, 12(t3)
    sw s2, 0x5c(s0)
    sw t1, 0x60(s0)
    fence w, w                  /* payload before the sequence word */
    sw t1, 0(t3)
    mv s1, t1
    fence rw, rw
    .word 0x0170000b            /* l2cache.ciall: publish the response */
    j poll
