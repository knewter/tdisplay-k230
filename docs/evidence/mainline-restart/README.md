# Optional mainline K230 restart source and host evidence

On 2026-10-02, the optional DRM candidate's K230 reset object compiled
successfully against headers prepared from the exact pinned candidate
source. Nix also built the patched source derivation. These are host source
and object checks; automatic restart on this board remains **UNVERIFIED**.
A complete kernel build and matching trial bundle are separate gates below.
No serial port, board staging, flash or reboot was used for these checks.

The change is on `mainline-restart-port`, in
`/home/jadams/tmp/k230-mainline-restart`, based on
`c5254075e531487af82841b3ae76582e5535f0fb`. The coordinator reserved the
single build slot; every compilation/build uses `/tmp/k230-nix-build.lock`.
The board remains reserved to the coordinator.

## Read source and boundary

The pinned vendor source is
[`drivers/reset/reset-k230.c`](https://github.com/ruyisdk/linux-xuantie-kernel/blob/7d4e1f444f461dbe3833bd99a4640e7b6c2cd529/drivers/reset/reset-k230.c#L309),
read from the local vendor source output. Its `k230_restart()` maps four
bytes at `0x91102000 + 0x60`, writes `(1 << 0) | (1 << 16)`, and waits
indefinitely. Its `k230_restart_register()` sets priority 128. The prior
[restart audit](../mainline-display/physical-2026-10-01/mainline-restart-source-audit-2026-10-02.md)
records the vendor normal restart reaching U-Boot SPL, absent advertised
SBI SRST in the mainline logs, mainline's peripheral-only reset controller,
and the distinct userspace refusal and operator recovery.

The mainline source remains
`72d3fcf802c45d00b300f25b848a93c3a2bd7c7e` (Linux 7.3-rc5).
[`include/linux/reboot.h`](https://github.com/torvalds/linux/blob/72d3fcf802c45d00b300f25b848a93c3a2bd7c7e/include/linux/reboot.h)
and [`kernel/reboot.c`](https://github.com/torvalds/linux/blob/72d3fcf802c45d00b300f25b848a93c3a2bd7c7e/kernel/reboot.c#L522)
provide `devm_register_sys_off_handler()`, a managed cleanup action and
priority selection. Its convenience restart wrapper uses priority zero;
the port instead preserves vendor priority 128. Non-default duplicate
priorities return `-EBUSY`, which the probe propagates.

`nix/patches/mainline/k230-restart.patch` adds restart support alongside the
mainline peripheral reset implementation. Only `nix/kernel-mainline-drm.nix`
applies it. The callback retains the vendor address, 32-bit write mask and
terminal wait (`cpu_relax()`); it performs no allocation or mapping.
Probe maps the vendor register with `devm_ioremap()`, checks failure,
registers the existing managed peripheral controller, and checks managed
restart registration. Release order unregisters the handler before either
mapping and the per-device allocation. The callback therefore has no stale
mapping after failed registration or removal. The driver already receives
the mainline `canaan,k230-rst` node; no device-tree change is needed. Its
peripheral resource at `0x91101000` is distinct from the boot-control
register, and the peripheral CPU0 reset ID is not used for restart.

This deliberately does not change stage 1/OpenSBI or write registers from
userspace. It retains the vendor's indefinite wait if the hardware reset
does not happen; an operator power cycle remains the recovery procedure
until physical reset is proved. It does not explain or claim to solve the
candidate's usable-root failure.

## Initial source derivation and LLVM object proof

Commands (both exited zero):

```sh
flock /tmp/k230-nix-build.lock nix build .#kernelMainlineDrm.src \
  --no-link --print-out-paths --max-jobs 1 --cores 4
flock /tmp/k230-nix-build.lock env \
  MAINLINE_RESTART_SRC=/nix/store/vnzm30w6v4na0ylpw8vclyn7dn9vvkf0-linux-mainline-k230-drm-src \
  bash docs/evidence/mainline-restart/object-check.sh
```

The first command produced
`/nix/store/vnzm30w6v4na0ylpw8vclyn7dn9vvkf0-linux-mainline-k230-drm-src`;
[source-build.log](source-build.log) records evaluation, source restoration
and patch application. The second prepared actual headers in an isolated
`.scratch/` build directory from that exact source with RISC-V defconfig,
using host LLVM/Clang 22.1.8, then compiled only `reset-k230.o` with `W=1`.
The former full candidate's dev output had been garbage-collected, so this
check regenerated pinned headers instead of borrowing a different kernel's
prepared headers. It is not the Nix GCC configuration or a full link.

[object-check.log](object-check.log) records UTC `2026-10-02T15:38:08Z`,
`CONFIG_64BIT/RISCV/OF/RESET_CONTROLLER/RESET_K230=y`, no compiler warning,
and the produced RISC-V relocatable object. The object contains
`k230_rst_restart` with the expected unresolved references to managed
mapping and sys-off registration (no modpost or full-kernel link claimed).

- Patched reset source SHA-256: `285e7198a1bd162a46cb8a3c1557c6a9724c0b6c9c0e8c75879659992ef46b80`.
- Pinned reboot header SHA-256: `48cf7704d93c9799a869759587736aa84dfaa671a8a7075ce750deb809598a85`.
- Object SHA-256: `357180aca45dab25c70a940df16d809d7c33afc03cd336e3c14f5ccd98a15aa2`.
- Object-check config SHA-256: `feae74c06f4924981806903df93e621a39413c2993fdff45ee32172bf3cc1140`.

## GCC failure, correction and pinned GCC object proof

The first complete Nix/GCC kernel invocation (four cores) failed in
`k230_rst_restart()` at `-Werror=return-type`. LLVM accepted the terminal
loop without an explicit return, but GCC 15.3 requires it here. The initial
port omitted the vendor's unreachable `return 0`; the correction restores
it as `return NOTIFY_DONE` after the unchanged terminal `cpu_relax()` wait.
The address, write mask and priority are unchanged. This failed run is kept
in [kernel-build-failure-invocation.log](kernel-build-failure-invocation.log)
and [kernel-build-failure.log](kernel-build-failure.log); the latter preserves
the complete build text with ANSI/OSC escapes removed for readability.
It is failed build evidence, not a complete kernel result.

The corrected source derivation build exited zero and produced
`/nix/store/jvz4v73g8a67pqwm06v079h6s1cpqr9s-linux-mainline-k230-drm-src`
([source-build-corrected.log](source-build-corrected.log)). The pinned GCC
15.3.0 object invocation also exited zero with `W=1` and no compiler warnings:

```sh
flock /tmp/k230-nix-build.lock env \
  MAINLINE_RESTART_SRC=/nix/store/jvz4v73g8a67pqwm06v079h6s1cpqr9s-linux-mainline-k230-drm-src \
  MAINLINE_RESTART_CONFIG=/nix/store/7zp582356s9ss40wjjc0drgxh0vihhi9-linux-config-riscv64-unknown-linux-gnu-7.3.0-rc5 \
  MAINLINE_RESTART_CROSS_COMPILE=/nix/store/4j2mwxqjvnyr6da0925sp0bm4jaj5r5i-riscv64-unknown-linux-gnu-gcc-wrapper-15.3.0/bin/riscv64-unknown-linux-gnu- \
  bash docs/evidence/mainline-restart/object-check.sh
```

[gcc-object-check.log](gcc-object-check.log) starts at UTC
`2026-10-02T16:06:15Z`. The script copies the actual Nix candidate config,
disables GCC plugins/debug/Rust selections unnecessary to this object check,
and regenerates headers with the pinned GCC toolchain. The resulting config
and compiler are recorded rather than claimed byte-identical to the full
Nix build. This checks the same reset source with the compiler that named
the error; it still does not link a complete kernel or execute reset.

- Corrected reset source SHA-256: `9007d8e3b4de77149bcfaf37a9148a5d8b7bdeafbe2b66b8fcd02268ee849fd8`.
- GCC object SHA-256: `f6ccce5cc537e390514e3eae6e361a9f4fd07dff3f964439be6fb43d5932de46`.
- GCC object-check config SHA-256: `40fee52e7dc0d13cc9cd98c51925da55f99c0a4a85c74b390715c264d88cf758`.

The coordinator authorized `--max-jobs 1 --cores 16` for the corrected full
kernel retry and subsequent matching bundle, under the same single build
lock. The first four-core failed invocation is not overwritten.

## Remaining gates

Task 5d.2 still requires the complete `.#kernelMainlineDrm` Nix/GCC build.
Task 5d.3 requires the matching `.#kernelMainlineDrmTrialBootFiles`, durable
artifact inspection and default/console derivation identity comparison.
Task 5d.4 requires a reviewed, reserved operator trial and committed console
proof of a real kernel restart returning through stage 1 to the protected
normal system with a fresh boot ID and normal hashes/shell postflight. The
operator's serial capture command is:

```sh
flock /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=10
```

Record the exact controller invocation and matching bundle/hash beside that
capture. A systemd refusal or manual power cycle does not prove automatic
restart. Task 5b.5 remains open for usable mainline root and deliberate touch
as well as the other named physical observations. No archive is authorized
by these host results.
