# Optional mainline K230 restart source and host evidence

## Latest physical result

The [2026-10-02 clock comparison](physical-clock-comparison-2026-10-02/README.md)
passed automatic candidate kernel restart → SPL → protected normal recovery
with a temporary `clk_ignore_unused` diagnostic argument. Task 5d.4 is
proved for that boot; the baseline still stalls. Usable mainline root and
deliberate touch remain UNVERIFIED, and a proper clock-consumer fix remains.
The host-only records below retain their original limits.


On 2026-10-02, the optional DRM candidate's K230 reset object compiled
successfully against headers prepared from the exact pinned candidate
source. Nix also built the patched source derivation. These are host source
and object checks; automatic restart on this board remains **UNVERIFIED**.
After the recorded GCC correction, the complete kernel and its matching
trial bundle build/inspection also passed; those separate host results are
recorded below. None is physical restart evidence.
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
clears GCC plugin/debug/Rust requests unnecessary to this object check,
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

## Complete corrected kernel and matching trial bundle

The corrected complete kernel invocation exited zero:

```sh
flock /tmp/k230-nix-build.lock nix build .#kernelMainlineDrm \
  --no-link --print-out-paths --max-jobs 1 --cores 16 --log-format raw
```

[kernel-build-invocation.log](kernel-build-invocation.log) names output
`/nix/store/4wkhxf55y1abg1kg2xd0acsfjqr64j0h-linux-riscv64-unknown-linux-gnu-7.3.0-rc5`.
[kernel-build.log](kernel-build.log) preserves the full corrected in-tree
GCC build, including `drivers/reset/reset-k230.o`, final kernel link and
installation; ANSI/OSC escapes and trailing spaces were removed for
readability and repository whitespace checks. The log
contains existing prototype/unused-variable warnings in Canaan DRM, RTC and
SD/MMC files; no reset-driver warning or final-link error remains. Storage
waiting dominated link/install time; the extra cores did not remove that
limit. No kernel source, build flags or configuration were changed to work
around storage wait.

[kernel-artifact-inspection.log](kernel-artifact-inspection.log) records UTC
`2026-10-02T16:48:07Z`, the 38,530,560-byte Image, reset source identity and
`System.map` linkage. Image SHA-256 is
`70a81b2172710c64463b53693e2e505a4d82ae2f7b644b2fc93cee9016b05330`.
The completed dev output is
`/nix/store/5wfn6k1lm9fvbwny2qk52admhwm5q4rm-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-dev`;
its installed `.config` SHA-256 is
`c5c128ed8b9701f78a0b8bd4f18dacd0d2407ae90eda79a35bba2d9f5ffbeae7`.
[config-inspection.log](config-inspection.log) confirms built-in
`RESET_K230`, `RESET_CONTROLLER`, `RISCV_SBI` and `POWER_RESET`.
The kernel derivation's source is the corrected `jvz4v73...` output above;
its reset file matches the pinned GCC object check. The prepared dev output
retains the headers/build inputs needed by external modules rather than every
driver `.c` file, so reset source identity is checked in the derivation's
actual source output. `System.map` contains `k230_rst_restart` and
`devm_register_sys_off_handler`; linkage does not prove probe-time handler
registration or a physical reset.

The matching bundle invocation and inspector both exited zero:

```sh
flock /tmp/k230-nix-build.lock nix build .#kernelMainlineDrmTrialBootFiles \
  --no-link --print-out-paths --max-jobs 1 --cores 16 --log-format raw
nix shell --inputs-from . nixpkgs#dtc --command \
  python3 tools/mainline-drm-trial-inspect.py \
  /nix/store/asj7l4zj5jrjkgng4nrcx3y72p7jf7aa-k230-mainline-drm-trial-boot-files
```

[bundle-build.log](bundle-build.log) and
[bundle-inspection.log](bundle-inspection.log) preserve the exact results:

| Artifact | Store path |
| --- | --- |
| Bundle | `/nix/store/asj7l4zj5jrjkgng4nrcx3y72p7jf7aa-k230-mainline-drm-trial-boot-files` |
| System | `/nix/store/v9qc1sf0iz53s3x6g6vwfyaxghkfpnyk-nixos-system-nixos-26.11.20260919.20b1ddd` |
| Kernel | `/nix/store/4wkhxf55y1abg1kg2xd0acsfjqr64j0h-linux-riscv64-unknown-linux-gnu-7.3.0-rc5` |
| Base DRM DTB | `/nix/store/nxbrd4smrcmknipjn4hjk32n87p4g9k6-k230-tdisplay-mainline-drm.dtb` |

The bundle DTB embeds the new system's exact `init=` path, while its base DTB
input is unchanged. The inspector verifies Image identity, DTB/environment
bootargs, U-Boot header/payload CRCs, the exact system initrd payload and all
629 closure paths. [bundle-hashes.log](bundle-hashes.log) records the four
boot artifacts' SHA-256 values; the initrd wrapper hash is
`2a4cc196d510bde579498c69758c9e3c52e0a23d6dda8d3297fd16280413d80e`.
The kernel, dev output and bundle are protected by host GC roots under this
worktree's ignored `.scratch/mainline-restart-{kernel,kernel-dev,bundle}`.
This is host artifact preservation, not board staging or deployment.

`python3 docs/evidence/mainline-restart/compare-identities.py` exited zero:
[unchanged-identities.log](unchanged-identities.log) compares nine exact
vendor/default/console-only derivation identities to base `c5254075...`,
including Image-only and full console boot-files collectors. All match.
This isolates this change against its base; other agents' later changes to
master are outside that comparison. [flake-check.log](flake-check.log)
records corrected-source `nix flake check --no-build` passing. Strict
OpenSpec validation also passes. Task 5d.2/5d.3 host gates are complete;
5d.4 and 5b.5 remain open.

## Remaining gates

Task 5d.4 requires a reviewed, reserved operator trial and committed console
proof of a real kernel restart returning through stage 1 to the protected
normal system with a fresh boot ID and normal hashes/shell postflight. The
operator's serial capture command is:

```sh
flock /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=10
```

The coordinator's reviewed controller at `48c83245` accepts the exact bundle
and protected private manifest/report explicitly. Use that controller (the
older controller at this worktree's base has no `--bundle` argument), without
changing global defaults:

```sh
python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal \
  --bundle /nix/store/asj7l4zj5jrjkgng4nrcx3y72p7jf7aa-k230-mainline-drm-trial-boot-files \
  --manifest "$HOME/tmp/k230-mainline-restart-board/candidate-manifest.json" \
  --normal-report "$HOME/tmp/k230-mainline-restart-board/normal-report.json" \
  --log "$HOME/tmp/k230-mainline-restart-board/minimal-uart.log" \
  --result "$HOME/tmp/k230-mainline-restart-board/minimal-result.json"
```

Those are private paths, not committed secret-bearing contents. The protected
report must come from the operator's live preflight; a host-prepared report is
not board-state evidence. The controller's own reserved serial capture must
be retained; do not open the standalone console concurrently. Record the
actual controller source revision, invocation and matching bundle/hash beside
that capture. A systemd refusal or manual power cycle does not prove automatic
restart. Task 5b.5 remains open for usable mainline root and deliberate touch
as well as the other named physical observations. No archive is authorized
by these host results.

## Later physical minimal trial and manual recovery

The coordinator subsequently ran the inspected bundle with controller
`f9759f43` and obtained physical receipt, `/bin/true`, proc setup and uptime
passes. The candidate printed `Rebooting.`, but automatic return was not
observed before the operator intervention disconnected serial. Neither
callback execution nor the completed normal-return deadline is proved.
Independent manual recovery then passed protected serial postflight with
fresh boot ID `08f9455a-1044-4d72-b7ae-bc70d611a8e2`, and a reviewed webcam
photo shows normal Home.

[Physical observation and recovery](physical-minimal-2026-10-02/README.md)
retain exact source/artifacts, fixed console excerpt, normal postflight and
photo provenance. [Dispatch source audit](restart-dispatch-audit-2026-10-02.md)
separates userspace request, kernel preparation and callback execution.
Its pending-recovery statement records the audit boundary; the later protected
recovery is recorded separately above. Tasks 5d.4 and 5b.5 remain open.

## Verbose trial and bounded readiness correction

The [verbose physical trial](physical-shutdown-debug-2026-10-02/README.md)
started Linux 7.3 and successfully probed the reset controller, but stopped
before diagnostic receipt. It requested no candidate reboot. Reviewed camera
frames show boot text; subsequent 15- and 90-second receive-only captures got
no output. Subsequent user power-cycle recovery passed protected serial
postflight and reviewed webcam Home, separately recorded for this trial.

The [host correction](shutdown-debug-host-preparation-2026-10-02.md)
waits read-only for the pinned candidate shell-init entry before receipt
attempts and persists a structured unknown result on minimal readiness or
protocol failure. All 76 host tests pass; this source correction does not prove
that a longer wait completes the physical boot. No new physical trial has
been run with the correction. Tasks 5d.4 and 5b.5 remain open.

The [runtime tracing source note](runtime-shutdown-trace-feasibility-2026-10-02.md)
identifies a writable runtime parameter that can enable shutdown tracing after
nondebug shell readiness. Guarded sysfs/write/readback stages are now implemented and pass 87 host
tests. The [quiet physical attempt](physical-runtime-trace-2026-10-02/README.md)
reached Bash but returned no reception token after corrupted early input and
a continuation prompt. No runtime stage or candidate reboot was attempted.
The ordinary-mode shell-init readiness correction is the next host step.
Source feasibility and host simulations
are not returned board proof. It also records why host serial reopening cannot establish a target
kernel stop.

## Quiet tracing after the common readiness correction

The [new physical trial](physical-runtime-ready-2026-10-02/README.md) passed
fresh shell readiness, reception, minimal prerequisites and all six runtime
trace gates. A real reboot request produced seven device-shutdown entry
checkpoints, ending at `mmcblk mmc1:59b4`, then the complete 180-second
normal-return deadline expired. The entry narrows the source boundary but
does not prove which callback/next-device lock or PM barrier blocked. No
kernel restart announcement, SPL or normal login was observed; 5d.4 and
5b.5 remain open. Prior reset-button recovery is separately proved in the
preceding attempt's record; recovery from this latest trial is pending.
