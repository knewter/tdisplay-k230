# Kernel vector compiler-probe correction: configuration verified, boot pending

The normal kernel reports `v` in the ISA string but omits V from the standard
hwprobe response; see [the read-only board probe](../pixman-rvv/README.md).
The running `/proc/config.gz` contains neither TOOLCHAIN_HAS_V nor RISCV_ISA_V.
The normal kernel's regenerated config reproduces that absence.

The pinned Xuantie `arch/riscv/Kconfig` tests `-march=rv64iv` / `rv32iv` to
detect vector-capable compilers. GCC 15.3 rejects those combinations because
its V implementation requires M. This makes the hidden TOOLCHAIN_HAS_V false,
which makes vector context support unavailable even though the processor's
ISA description contains V. The actual compiler probes are retained in
`compiler-probes.json`: both old checks fail, and adding M makes both pass.
This establishes the build/configuration defect; booting the correction is a
separate step.

`kernel-rvv-trial` patches the two checks to `rv64imv` and `rv32imv`, and
explicitly requests RISCV_ISA_V and RISCV_ISA_V_DEFAULT_ENABLE. It intercepts
the board kernel's buildLinux inputs so its internally-owned src/config are
actually changed. The normal kernel, DTB, image and package set are unchanged.

```sh
nix build .#kernel-rvv-trial.configfile --max-jobs 1 --cores 4 --no-link --print-out-paths
nix build .#kernel-rvv-trial --max-jobs 1 --cores 8 --no-link --print-out-paths
```

The configuration build passes. `config.diff` is the complete difference from
the regenerated normal config: TOOLCHAIN_HAS_V, RISCV_ISA_V,
RISCV_ISA_V_DEFAULT_ENABLE, DYNAMIC_SIGFRAME, and ERRATA_THEAD_VECTOR become y.
The latter two follow kernel dependencies/defaults; the trial does not select a
specific vendor instruction set unconditionally. The resulting source is
`/nix/store/l6jdpbzp53y5n24ky6602f41gzs6f6ik-linux-xuantie-k230-rvv-src` and config
`/nix/store/yp5qydyrl86li5bmx25l6vaykn6yfj64-linux-config-riscv64-unknown-linux-gnu-6.6.36-xuantie`.

The full kernel cross-build passes; `kernel-build.json` records the artifact,
SHA256, finish time and final built configuration. The first build client was
lost before producing a valid output; the resumed build completed successfully.
**No boot, vector execution, signal or context preservation on the physical
board, framebuffer correctness, speedup or image integration is verified.** The board remains on the previous normal image. Do not force RVV in
userspace while the running kernel omits its support.

Before integrating: build a matching system closure, including its external
Wi-Fi module, rather than swapping the kernel beneath old modules; use a
recoverable board trial; require hwprobe V, vector computation across scheduling/signals, normal
shell/touch/Wi-Fi recovery and pixel comparisons; then compare the same live
card workload with the corrected Pixman's RVV enabled and disabled. Preserve
all existing interaction and frame-cost budgets. A kernel build alone does not
close card task 4.2 or any physical acceptance gate.


The [context probe](context-probe/README.md) now has passing full Linux guest
checks at two vector lengths and a deliberate corruption control. The same
compiled probe safely skips on the unchanged physical board. These validate
the diagnostic and fallback; they do not verify the trial kernel on hardware.


`default-identity.json` verifies the trial branch's ordinary system derivation
still produces the exact `/run/current-system` store path observed on the
physical board. The vector additions are separate package outputs; the ordinary
image has not acquired either the trial kernel or the probe. This identity check
is not verification of the optional kernel's full build or boot.


## Matching system configuration

`nixosConfigurations.k230-rvv-trial` extends the ordinary board configuration
with the opt-in kernel and context probe. External modules and the initrd derive
from that same selected kernel. `trial-system-evaluation.json` records the exact
kernel, Wi-Fi module and system derivations: the selected kernel matches the
already-built standalone trial, the Wi-Fi module changes, the renderer remains
Pixman, and the ordinary system derivation stays unchanged.

The kernel helper is imported directly to preserve the returned kernel's
`override` API. Wrapping it in `callPackage` intercepted NixOS's kernel override
arguments and caused an evaluation error for `features`.

```sh
nix build .#nixosConfigurations.k230-rvv-trial.config.system.build.toplevel \
  --max-jobs 1 --cores 8 --no-link --print-out-paths
```

The matching system cross-build passes. `trial-system-build.json` records its
store path, boot-artifact links, rebuilt Wi-Fi module and context-probe closure
members, plus the installed service’s Pixman selection. The board trial still requires matching boot artifacts, a known recovery route,
and the checks above; no board boot is claimed.


`sdImage-rvv-trial` packages that trial configuration with its matching kernel
and initrd using the existing image layout and stage 1. The shared image helper
preserves the ordinary `sdImage` derivation exactly; before/after evaluation is
recorded in `trial-image-evaluation.json`.

```sh
nix build .#sdImage-rvv-trial --max-jobs 1 --cores 8 --no-link --print-out-paths
```

The trial image build passes. `trial-image-build.json` records the image hash
and a host inspection of its boot partition: Image matches the trial kernel,
the wrapped initrd matches the trial system and has valid U-Boot CRCs, and
bootargs selects that same system. No card has been flashed or rebooted with it.
Preserve the known ordinary image as the recovery artifact before a trial.


## Trial on the expanded root

The storage-capacity change is now archived after two successful physical boots.
The normal system is now the growth-enabled system recorded in
`docs/evidence/storage-capacity/board-repeat.json`. The earlier ordinary-system
identity comparisons above describe their original checkpoint.

[The next trial artifacts](board-trial/artifacts.json) rebuild the complete RVV
system and image on master `648eab07`, retaining the same trial kernel and its
matching modules/initrd while including the verified root-growth service.
Actual host boot-partition inspection passes again. This does not establish
physical vector execution or improve any card performance acceptance result.
