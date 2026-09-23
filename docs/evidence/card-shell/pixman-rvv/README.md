# Pixman RVV build fix; board kernel capability gate remains closed

The pinned Pixman 0.46.4 baseline reports its RISC-V Vector Intrinsic Support
check as **NO**, despite GCC 15.3 supporting the required intrinsics. Recompiling
the exact Meson check with the cross compiler fails on an implicit declaration
of `sys_riscv_hwprobe`. That name is not provided by the pinned glibc headers.

The opt-in `pixman-rvv` derivation replaces both the Meson feature check and the
runtime detector call with `syscall(SYS_riscv_hwprobe, ...)`. It requires RVV at
build time so silent omission cannot look like success. Runtime detection still
requires the kernel's `RISCV_HWPROBE_IMA_V` bit: missing syscalls, errors and
absent capability retain Pixman's fallback. No default package set or image
uses this derivation.

```sh
PIXMAN_SOURCE_TAR=/nix/store/s2cifkjf074cwcim1p9lij646fi3p3zy-pixman-0.46.4.tar.gz \
  python3 tests/test_pixman_rvv_probe.py
nix build .#pixman-rvv --max-jobs 1 --cores 4 --no-link --print-out-paths
```

The test applies the actual patch to the pinned source and runs its detector
under ASan/UBSan with ENOSYS, EINVAL, EPERM, missing V and present V responses.
The cross build passes; `build-checks.txt` records the feature check changing
from NO to YES and compilation of `pixman-rvv.c`. Result:
`/nix/store/brhzfimak2r3c23lmn80y1g6ww6nmb1r-pixman-riscv64-unknown-linux-gnu-0.46.4`.
Cross compilation is not execution or a speed measurement.

## Physical board read-only capability check

On 2026-09-23, after restoring the normal image's shell, `kernel-probe.py` made
the standard scalar syscall on the physical board. Kernel 6.6.36 returned
success, key 4 and value 59 (`0x3b`), which does **not** include V bit 4. The
exact response is in `kernel-probe.json`. The script executes no vector
instructions and changes no kernel or process vector policy.

Therefore the patched Pixman would still select its fallback on this kernel.
The previously recorded `v` in `/proc/cpuinfo` does not establish usable RVV
through this API. Do not force RVV based on that text. The pinned Xuantie source
checks `has_vector() && !has_xtheadvector()` in
`arch/riscv/kernel/sys_riscv.c`; the [kernel configuration investigation](../kernel-rvv/README.md) now identifies
a failing compiler probe and verifies the corrected configuration. A boot is
still needed to verify the resulting capability. No vector-enabled compositor trial,
board pixel comparison, speedup, kernel replacement or reboot is claimed.

Next: finish and boot-test the isolated kernel trial; only after it truthfully
advertises usable RVV, compare actual Pixman
pixels and the same instrumented card workload with RVV enabled/disabled.
Retain scalar fallback and all existing cost/interaction gates. Card task 4.2
and image/physical acceptance remain open.
