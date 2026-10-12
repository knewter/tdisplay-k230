# CPU0 start/stop binding decision for the mainline kernel (task 1.2)

**Evidence class: source and document reading, 2026-10-12. No board, no
build, no code.** Supersedes the vendor-tree binding text that
`openspec/changes/the-small-core-runs-as-a-coprocessor/design.md` and its
spec delta originally carried. Those cited the vendor 6.6 tree's
`canaan,k230-sysctl-reset` node and `K230_RESET_*` macros; the daily kernel is
mainline v7.3-rc5 (`nix/kernel-mainline-src.nix:30`, rev
`72d3fcf802c4...`; `nix/kernel-mainline.nix:153` version `7.3.0-rc5`;
`nix/kernel-mainline-drm.nix:54-56` adds the patched
`linux-mainline-k230-drm-src`), and none of the vendor names exist there. All
mainline citations below are in that patched source tree
(`/nix/store/4jrzy64mg619y75lgrlihz78darglas6-linux-mainline-k230-drm-src`),
relative paths shown.

## Decision

1. **Consumer binding**: `resets = <&rst RST_CPU0>;` with
   `#include <dt-bindings/reset/canaan,k230-rst.h>`. The controller is
   `rst: reset-controller@91101000`, `compatible = "canaan,k230-rst"`,
   `#reset-cells = <1>` (`arch/riscv/boot/dts/canaan/k230.dtsi:92-96`;
   schema `Documentation/devicetree/bindings/reset/canaan,k230-rst.yaml`
   requires exactly one cell). `RST_CPU0 = 0`, `RST_CPU1 = 1`
   (`include/dt-bindings/reset/canaan,k230-rst.h:9-10`). The vendor
   four-cell `<&sysctl_reset 0x4 0 12 0>` form is **not valid** on mainline.
2. **Only `.reset` works for CPU0.** `RST_CPU0` is `{ 0x4, RST_TYPE_CPU0,
   BIT(12), BIT(0) }` (`drivers/reset/reset-k230.c:74`). `k230_rst_assert`
   and `k230_rst_deassert` return `-EOPNOTSUPP` for `RST_TYPE_CPU0`
   (`:225-228`, `:256-259`). `k230_rst_reset` is the only CPU0 path: clear
   the done bit, set the reset request, wait for done, delay 10 us
   (`:280-290`); the ops table registers `.reset`, `.assert`, `.deassert`
   (`:326-330`). The consumer therefore calls `reset_control_reset()`. This
   is a **pulse**, not a hold/release pair.
3. **Start = vector write, then `reset_control_reset()`.** The vector goes
   to `0x91102100` first (the pinned `boot_baremetal 0` order,
   `arch/riscv/cpu/k230/cpu.c:125-160` in the vendor U-Boot overlay), then
   the pulse starts CPU0 at it. The register is not named in any mainline
   binding.
4. **Stop is not available through the reset framework, and the hardware
   offers no hold bit.** `reset_control_assert()` on `RST_CPU0` fails with
   `-EOPNOTSUPP`. The TRM's `CPU0_RST_CTL` (RMU offset `0x4`, i.e.
   `0x91101004`) bit 0 `cpu0_reset_req` is access type **W1T**: "write-only
   and self-clear", "1: request to reset cpu0 subsystem"; bit 12
   `cpu0_rst_done` is W1C (TRM RMU register description, PDF page 16 of the
   downloaded file; see the feasibility note for the file hash). That
   explains why mainline implements only `.reset`: there is no
   level-held reset to assert. A clean stop therefore cannot come from a
   reset-driver patch alone. Candidates for task 5.2, not decided here:
   a firmware-cooperative stop (CPU0 firmware parks in `wfi` on a request
   from Linux, and a later pulse restarts it); or the PWR block's CPU0
   power control (TRM section 2.3.4, not read for this note, with the NOC
   low-power handshake caveat in section 2.3.3). Do not have the
   remoteproc driver write `0x91101004` itself behind the reset driver.
   Task 5.2's "assert only" wording is superseded accordingly.
5. **The vector register gets a private mapping, not a syscon.** The
   `sysclk` node covers only `0x91102000`-`0x9110203f`
   (`k230.dtsi:103-110`, `reg = <0x0 0x91102000 0x0 0x40>`), so
   `0x91102100` is not claimed by any mainline driver or node. The reset
   driver maps `0x91102060` for its restart handler with a private
   `devm_ioremap` (`reset-k230.c:337-338`, `:369-371`; `K230_SYSCTL_BOOT_BASE`
   0x91102000 plus `K230_CPU0_RST_CTL` 0x60, written `BIT(0) | BIT(16)` at
   `:345`), which is the precedent. The remoteproc node therefore carries its
   own `reg = <0x0 0x91102100 0x0 0x4>` (disjoint from the `sysclk` window
   and from `0x91102060`) and the driver maps it with
   `devm_platform_ioremap_resource()`. There is no `sysctl_boot` node on
   mainline (the vendor tree has `sysctl_boot@91102000`, vendor
   `k230.dtsi:241-244`).
   The width and side effects of the write are only what `boot_baremetal`
   already does, which this project observed work on 2026-10-12.
6. **Hazard: never request `RST_CPU1`.** `RST_CPU1 = 1` is
   `{ 0xc, RST_TYPE_CPU1, ... }` (`reset-k230.c:75`) and resets the core
   Linux runs on (CPU1; see
   [heartbeat-physical-2026-10-12/README.md](heartbeat-physical-2026-10-12/README.md)
   and the stage-1 audit). The driver must hard-code `RST_CPU0` in the
   binding and refuse any other `resets` index. Also `RST_CPU0_FLUSH` (2)
   exists separately and is not needed.
7. **Interaction with the restart handler.** The same driver's restart
   path writes `sysctl_boot+0x60` (`:345`), a different register from
   `CPU0_RST_CTL` at `0x91101004`; a CPU0 pulse through `RST_CPU0` is
   what `boot_baremetal` already does and is not the system-restart write.

## Not yet in the kernel configuration

`CONFIG_REMOTEPROC` appears in none of the project's mainline Nix kernel
inputs (`grep -rn REMOTEPROC nix/` finds nothing), so a remoteproc driver
also needs that option, a Kconfig entry, and a DT node. No mailbox or
rproc driver exists for K230 in the tree (`ls drivers/remoteproc` has no
K230 file). Mailbox registers are recorded in
`docs/research/second-core-feasibility.md` ("TRM mailbox register map").

## What this note does not establish

- That a reset pulse on `RST_CPU0` alone leaves CPU1/Linux undisturbed
  while Linux runs; that is task 5.3.
- That the RMU "done" handshake in `k230_rst_reset` completes with CPU0
  running Linux-launched firmware (U-Boot's version of the sequence was
  proven on the board; the Linux driver's was not run).
- The vendor-tree names remain correct for the vendor kernel
  (`nix/kernel-src.nix`) that the shipped image boots; this decision is for
  the mainline path the project is moving to.
