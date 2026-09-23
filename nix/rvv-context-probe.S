/* Standard calling convention: only caller-saved scalar/vector registers.
 * Keep live vectors across asynchronous signals and preemption, without calls
 * or syscalls (Linux permits syscalls to clobber them). The handler changes VL
 * and VTYPE as well as the live vector data. */
.text
.global rvv_roundtrip
.type rvv_roundtrip, @function
rvv_roundtrip:
    mv t3, a0
    vsetvli t0, a1, e32, m1, ta, ma
    csrr t1, vtype
    vid.v v9
    vadd.vx v8, v9, a2
    lw t4, (a3)
.Lwait_signal:
    lw t5, (a3)
    beq t5, t4, .Lwait_signal
    csrr t2, vtype
    bne t2, t1, .Lvtype_failed
    csrr t2, vl
    bne t2, t0, .Lvl_failed
#ifdef K230_RVV_TEST_CORRUPT
    vmv.v.i v8, 0 /* Negative-control build only. */
#endif
    vse32.v v8, (t3)
    mv a0, t0
    ret
.Lvtype_failed:
    li a0, -3
    ret
.Lvl_failed:
    li a0, -4
    ret
.size rvv_roundtrip, .-rvv_roundtrip

.global rvv_clobber
.type rvv_clobber, @function
rvv_clobber:
    vsetvli t0, zero, e32, m1, ta, ma
    vmv.v.i v8, -1
    vmv.v.i v9, -1
    vsetivli zero, 1, e8, m1, ta, ma
    ret
.size rvv_clobber, .-rvv_clobber
.section .note.GNU-stack,"",@progbits
