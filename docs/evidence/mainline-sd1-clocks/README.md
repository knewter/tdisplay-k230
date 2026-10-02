# Optional mainline DRM SD1 clock consumers

Host source/build evidence on 2026-10-02 uses branch `mainline-drm-sd1-clocks`,
worktree `/home/jadams/tmp/k230-mainline-drm-sd1-clocks`, base
`9cd4a3f870a62c01d63abae60dc07b309e054c52`. Owned paths are the optional DRM
kernel derivation, its DTS, the separate SDHCI clock patch and this evidence
folder. The sole build slot uses `/tmp/k230-nix-build.lock`, `--max-jobs 1
--cores 16`. No board, serial or physical trial was performed by this work.

The coordinator's same-bundle volatile clock comparison returned automatically
to protected normal, while its ordinary-clock shutdown had not returned. See
[physical clock comparison](../mainline-restart/physical-clock-comparison-2026-10-02/README.md)
and the independently reviewed [five-clock source audit](../../research/mainline-sd1-clock-consumers-2026-10-02.md).
That comparison grounds a cleanup dependency; it does not identify a specific
clock or prove this targeted correction. Physical ownership, automatic restart
with this candidate and usable root remain **UNVERIFIED**. Task 5b.5 remains
open; the previous conditional recovery proof is a separate evidence class.

## Scope and source grounding

The pinned Linux binding (`Documentation/devicetree/bindings/mmc/snps,dwcmshc-sdhci.yaml:115–130`)
requires the K230 names `core`, `bus`, `axi`, `block`, `timer`. The exact
upstream host reference (`drivers/mmc/host/sdhci-of-dwcmshc.c:1947–1977`)
acquires block/timer/axi as bulk clocks and balances them through host lifecycle.
These reads use Linux `72d3fcf802c45d00b300f25b848a93c3a2bd7c7e`.
Vendor clock roles and the exact upstream gate IDs ground the card-gate to
`block` translation; they do not supply per-gate physical attribution.
The legacy `canaan,k230-dw-mshc` compatible is retained: five names do not
make the whole node conform to the upstream schema, whose upstream K230
compatible also requires different USB-PHY/regmap integration.

Only [the DRM DTS](../../../nix/dts/k230-tdisplay-mainline-drm.dts) overrides SD1
clocks to BASE 31, AHB 13, AXI 29, CARD 26 and TIMER 35, with the five names
above. BASE remains `core`, preserving the existing max-clock source. No
clock rates, dividers, MMIO writes, IRQ, reset, DMA or PHY choice are changed.

Only [the DRM derivation](../../../nix/kernel-mainline-drm.nix) applies
[the clock patch](../../../nix/patches/mainline/k230-sdhci-clocks.patch) to the
already-copied Kendryte host driver. Core, bus and the three bulk extras are
mandatory: missing/deferred resources fail probe. Enabling proceeds core,
bus, extras. Failed bulk enable self-unwinds; the helper then releases bus
and core. Later probe failure releases extras, bus, core and the existing
HS mapping. Remove drains the host first; successful suspend stops the host
first; failed suspend retains clocks. Resume enables all clocks before host
resume and unwinds all on host-resume failure. No shutdown callback disables
clocks: card shutdown needs the host clocks. The original shared driver and
console DTS are not edited; no global clock-ignore policy is introduced.

## Narrow host proof

Source and DTB build completed successfully by `2026-10-02T20:06:13Z`:

```sh
flock /tmp/k230-nix-build.lock nix build .#kernelMainlineDrm.src .#deviceTreeMainlineDrm \
  --no-link --print-out-paths --max-jobs 1 --cores 16
```

[source-dtb-build.log](source-dtb-build.log) records exit-zero outputs.
[source-patch.log](source-patch.log) records application of the restart and
SDHCI clock patches. The source is
`/nix/store/l0j3rf11mr65wl5x88a9zzma45ciz687-linux-mainline-k230-drm-src`;
the driver is byte-identical to the reviewed staged C and hashes to
`e226cc359e9277d9ddc53d68647be1a8fd52431662d6f3e842dfa7fb7f611b8e`.

[dtb-check.json](dtb-check.json) records the actual built SD1 node's exact
names and IDs, a single provider phandle, unchanged legacy compatible,
10,840-byte DTB and SHA-256
`9c1e22d1b3305a4e42cda96cea9217a2e064a8dd1b88a86d5c4d3c198e6132a8`.
This is compiled DT structure proof, not schema or physical clock proof.

[identities.json](identities.json) compares evaluated output identities with
the exact base revision. Default kernel `03zyl0mjsxbjyisb3lhjaxswpxm71ap6`,
console kernel `xw38bf25mrd5mkjc2gg5qdkglbkl8b7v` and console DTB
`rr14di4rihw97dvcnjrd1f54p05bmqpm` are unchanged. The candidate full kernel
identity is evaluated only until its separate full-build proof is added.
The first baseline evaluation used a short `rev=` and was rejected by Nix;
it was corrected to the full Git SHA before comparison.

```sh
python3 docs/evidence/mainline-sd1-clocks/lifecycle-check.py \
  /nix/store/l0j3rf11mr65wl5x88a9zzma45ciz687-linux-mainline-k230-drm-src/drivers/mmc/host/sdhci-of-kendryte.c
```

[lifecycle-check.log](lifecycle-check.log) records successful host compilation
and execution of the actual patched enable/disable/suspend/resume function
bodies with clock/host stubs. Each of five injected enable failures and the
host-resume failure leaves zero references. A failed host suspend keeps all
five references; successful suspend and normal disable release them exactly
once. Bulk-failure stubs model the kernel API's own unwind. This does not
execute the real kernel clock provider or hardware PM callbacks.

The exact candidate Nix config was built, then GCC 15.3.0 prepared pinned
headers and compiled only `sdhci-of-kendryte.o` with `W=1`, exiting zero
([gcc-object-check.log](gcc-object-check.log), started `2026-10-02T20:08:39Z`):

```sh
flock /tmp/k230-nix-build.lock nix build .#kernelMainlineDrm.configfile \
  --no-link --print-out-paths --max-jobs 1 --cores 16
flock /tmp/k230-nix-build.lock env \
  MAINLINE_SD1_SRC=/nix/store/l0j3rf11mr65wl5x88a9zzma45ciz687-linux-mainline-k230-drm-src \
  MAINLINE_SD1_CONFIG=/nix/store/7vxby0h1nz78r9qzbqfjjs9vw4x7gpl0-linux-config-riscv64-unknown-linux-gnu-7.3.0-rc5 \
  MAINLINE_SD1_CROSS_COMPILE=/nix/store/4j2mwxqjvnyr6da0925sp0bm4jaj5r5i-riscv64-unknown-linux-gnu-gcc-wrapper-15.3.0/bin/riscv64-unknown-linux-gnu- \
  bash docs/evidence/mainline-sd1-clocks/object-check.sh
```

The RISC-V object contains probe/remove/suspend/resume and references the
bulk get/prepare/enable/disable/unprepare APIs. Object SHA-256 is
`aa73d4c13d860a7f5a7d4150625a81a593610ed8bba5971c557dce06de8b3576`;
prepared config SHA-256 is
`40fee52e7dc0d13cc9cd98c51925da55f99c0a4a85c74b390715c264d88cf758`.
RISCV, MMC, SDHCI, SDHCI_PLTFM, the Kendryte driver and PM_SLEEP are enabled.
The full Nix config is byte-identical to the previous candidate config:
SHA-256 `94e3ab32c17d5ee6f51fcfa0d410bc10927f591db750aafffbd71c7407ef4da8`.
Only for this object check, GCC plugins, debug-info/BTF and Rust requests
unnecessary to this target were cleared before header preparation. This
is exact-header/API proof, not a full Nix kernel link or real PM execution.
`W=1` reports the preexisting exported `plat_sdio_rescan()` missing-prototype
warning. That function and its global slot bookkeeping were not changed.

Full kernel, matching bundle and physical baseline proof are separate gates.
Strict OpenSpec validation passes. Actual changed C
and nonpatch files pass whitespace checks; unified-patch context retains its
required leading space before original tabs/blank lines, which generic new-file
`git diff --check` reports. Cached work-status was run at start and will be run
again before handoff. Whole-flake `nix flake check --no-build` also exited
zero, ending `all checks passed!` ([flake-check.log](flake-check.log)).
No task checkbox or canonical spec is changed here.

## Full Nix build failed at installation: store capacity

The next exact optional kernel invocation started `2026-10-02T20:13:13Z`:

```sh
flock /tmp/k230-nix-build.lock nix build .#kernelMainlineDrm \
  --no-link --print-out-paths --max-jobs 1 --cores 16 --keep-failed -L
```

It exited **1**, observed at `2026-10-02T21:10:58Z`. All compilation, kernel
links, BTF, Image and module generation finished; `buildPhase` took 54 minutes
55 seconds. Installation then failed creating the kernel output directory:
`No space left on device`. This is a **failed full Nix build**, not a realized
kernel or matching bundle. [Invocation](kernel-build-failure-invocation.log),
[full failure log](kernel-build-failure.log), [capacity](disk-failure-capacity.log)
and [structured failure](full-build-failure.json) preserve the command and limits.
The `/nix` NVMe volume has zero available bytes, 100% usage, and only 10% inode
usage. Linkers spent long intervals in D/storage wait. An authorized attempt
to improve this job's linker I/O priority failed `Operation not permitted`;
no process priority or unrelated workload was changed.

`--keep-failed` retained this job's 13 GB build at
`/nix/var/nix/builds/nix-2288231-62236773/build`. It is owned by `nixbld`, with
a root-owned parent. Noninteractive administrative access requires a password,
so no cleanup, garbage collection or unrelated deletion was performed.
Host storage recovery belongs to the coordinator/administrator. A diagnostic
copy of the compiled Image and config is preserved under
`~/tmp/k230-mainline-sd1-failed-artifacts/`; the structured failure records its
hash/size. It is explicitly **not** a valid Nix output and was not staged.

The first diagnostic copy looked for the Image in the source root; this
derivation actually uses its nested `build/` directory. The corrected copy
uses `build/arch/riscv/boot/Image`. No image was accepted from the failed lookup.

Kernel `9vdk79pa4pm38mlmbflkqh4i4sc9kha0`, matching bundle
`5yqilsfyj35jzrcqjjqilkr6sd47qlms` and system
`9gdmsrh2igqla1qz0ll97czfw2x42icw` remain **evaluated predictions only**.
The dependent bundle/inspector were not run after the failed kernel build.
Once store capacity is restored, retry the named kernel command, then build
`.#kernelMainlineDrmTrialBootFiles` sequentially under the same lock and
inspect that exact realized bundle with `tools/mainline-drm-trial-inspect.py`.
Source/object/DTB proof remains valid independently of this storage failure.

## Remaining gate

After the separate reviewed full kernel and matching trial-bundle build,
the sole board operator must validate/stage that exact bundle and run quiet
minimal runtime tracing with explicit candidate selection, **without**
`--ignore-unused-clocks`. Require readiness, receipt/true/proc/uptime, runtime
readback `Y`, ordinary unused-clock cleanup, reboot, SPL and fresh protected
normal postflight within 180 seconds. Missing/unknown results stop input and
preserve recovery. Only then proceed separately to returned label and
`ro,noload` root diagnostics. Ordinary `/init` and deliberate touch remain
unproved. Root owns staging, board reservation, physical evidence and all
planning/dashboard updates.
