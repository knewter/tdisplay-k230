# Latest U-Boot feasibility for the T-Display K230

**Research date:** 2026-09-22  
**Scope:** source and repository inspection only. No U-Boot build, image
generation, card write, serial session, or board boot was performed for this
note.

## Verdict

**Feasible, with medium confidence for a deliberately narrow U-Boot-proper
pilot; not safe as a routine version bump.**  Upstream now contains a
maintained K230 CanMV port and explicitly documents the same useful boundary:
keep a vendor SPL for DDR initialisation and replace the U-Boot image at the
2 MiB card offset. That gives this board a much smaller migration surface than
a fresh BootROM/SPL port.

The stable pilot should use **U-Boot v2026.07**, retaining this project's
known-good SPL, both SPL slots, environments, OpenSBI, raw layout, and UMS
recovery path.  `v2026.10-rc5` is useful as the current-development inspection
point, but is a release candidate and is not an appropriate first pin.

The confidence does *not* extend to a drop-in replacement for the present
T-Display behaviour. Upstream's K230 port is for the generic CanMV board. It
does not contain this project's `k230_canmv_v3` board description, UMS gadget
configuration, two-controller coexistence repair, RM69A10 logo path, splash
loader, or the project boot/runtime handoff. Those are migration work, not
evidence that an upgrade already works.

## Upstream status, verified from official sources

The official release-cycle page records `v2026.07` as released on 2026-07-06
and the next quarterly release as `v2026.10`. The official source instructions
name the canonical repository and tag convention. On 2026-09-22, a direct
read-only `ls-remote` and source checkout from that repository found:

| item | observed official revision/date | conclusion |
| --- | --- | --- |
| latest stable | signed annotated `v2026.07` resolves to immutable commit `ece349ade2973e220f524ce59e59711cc919263f`, 2026-07-06T17:50:43-06:00 | recommended first upstream base |
| current development | annotated `v2026.10-rc5`, commit `a06e89ab05eaa2b8344d521319399333cd760ae5`, 2026-09-21T16:12:01-06:00 | inspected only; release candidate |
| licence | `Licenses/README` in the inspected upstream tree starts `SPDX-License-Identifier: GPL-2.0` | retain per-file SPDX accounting when carrying patches |

Official sources:

- <https://docs.u-boot.org/en/latest/develop/release_cycle.html>
- <https://docs.u-boot.org/en/latest/build/source.html>
- <https://source.denx.de/u-boot/u-boot.git>
- <https://docs.u-boot.org/en/v2026.07/board/canaan/k230_canmv.html>

Source inspection of both `v2026.07` and `v2026.10-rc5` found the following
upstream paths:

```
arch/riscv/cpu/k230/{Kconfig,Makefile,cpu.c,dram.c}
arch/riscv/dts/{k230.dtsi,k230-canmv.dts,k230-u-boot.dtsi}
board/canaan/k230_canmv/{Kconfig,Makefile,board.c,MAINTAINERS}
configs/k230_canmv_defconfig
doc/board/canaan/k230_canmv.rst
```

The upstream defconfig enables NS16550, DWC2 host USB, RTL8152 Ethernet, and
the K230 target. Its board document says it relies on a **vendor U-Boot SPL**
to initialise DDR and load U-Boot, then directs users to write a
vendor-header-wrapped U-Boot image at 2 MiB. That is direct source evidence
for retaining our SPL during a U-Boot-proper experiment.

The upstream device tree enables UART and the onboard RTL8152 at `usb1`; it
leaves `usb0` disabled. Upstream has no `k230_canmv_v3` file or T-Display
RM69A10 logo implementation. Its K230 `binman` description produces a normal
gzip U-Boot firmware image; it does not establish compatibility with this
project's K230 header plus gzip-CM-`0x09` hardware-decompression convention.

## What the current boot chain owns

The current source base is `3cff765`. Its stage-1 implementation is
documented in [nix/uboot-k230.nix](../../nix/uboot-k230.nix) and
[nix/stage1.nix](../../nix/stage1.nix): upstream U-Boot 2022.10 is overlaid
from `kendryte/k230_linux_sdk` revision
`1104236db4d1e47873bd68924f912747b820228c`, then locally patched. The SDK
overlay is BSD-2-Clause according to
[nix/k230-sdk-src.nix](../../nix/k230-sdk-src.nix); it is an rsync overlay,
not a small patch queue.

The parts must be treated separately:

| layer | current responsibility | first experiment |
| --- | --- | --- |
| BootROM / SPL / DDR | BootROM loads `fn_u-boot-spl.bin` at 1 MiB and 1.5 MiB. The SPL includes Canaan's LPDDR4 PMU training data and has a 512 KiB `CONFIG_SPL_SIZE_LIMIT`. | preserve byte-for-byte; do not compile or replace it |
| U-Boot proper | `fn_ug_u-boot.bin` at 2 MiB is the replaceable monitor, including USB/UMS and board policy. | replace only this slot after source/build checks |
| raw environments | 8 KiB `env.env` copies at 3 MiB and 3.125 MiB select the present boot flow. | preserve byte-for-byte initially |
| OpenSBI | Canaan-overlay OpenSBI 1.4 `fw_jump.bin`, wrapped for the existing `blinux` flow. The overlay supplies the K230 MAEE workaround. | preserve; do not upgrade in the same experiment |
| rootfs / kernel | NixOS boot partition and current kernel. | preserve; this is not a kernel experiment |

The project packs U-Boot proper as gzip `-n -8`, changes the gzip CM byte from
`0x08` to `0x09`, makes a legacy U-Boot image, then adds Canaan's `K230`
integrity header. It repeats a Canaan header over SPL. See
[nix/stage1.nix](../../nix/stage1.nix) and the existing source-build evidence
in [docs/evidence/stage1-from-source.txt](../evidence/stage1-from-source.txt).
The 2 MiB U-Boot slot ends before the first environment slot at `0x300000`, so
the packaged replacement must stay within 1 MiB. `env.env` itself is exactly
`0x2000` (8 KiB) and is stored at `0x300000` and `0x320000` (the two raw
locations are 128 KiB apart). This packaging and size constraint are
independent of whether upstream itself can compile.

There is also a concrete boot-flow compatibility gap. The preserved
environment sets `bootcmd=run blinux`; `blinux` calls the vendor
`k230_set_dtb`, then `ext4load`s `bootargs.txt`, the wrapped OpenSBI
`fw_jump_add_uboot_head.bin`, kernel, DTB, and initrd before `bootm`. A source
search of upstream `v2026.07` finds neither `k230_set_dtb` nor `blinux`.
Consequently, retaining the environment is not enough: the pilot needs either
a reviewed port of that command and its semantics, or an explicitly recorded
transient boot command that loads the same artifacts and passes the FDT to the
existing OpenSBI handoff. That command path must be proved before claiming a
Linux handoff.

## Delta that must be carried or deliberately replaced

The current local patches are small but target vendor-tree APIs:

| family | current files | migration implication |
| --- | --- | --- |
| data-port UMS | `0001-k230_canmv_v3-enable-usbotg0-as-a-peripheral.patch` | reintroduce the T-Display USB0 peripheral node and the exact UMS identity/configuration |
| host/gadget coexistence | `0002-dwc2-udc-otg-refuse-host-mode-nodes-at-bind-usbotg1-is-host.patch`, `0003-k230-usbotg1-select-host-driver-before-gadget.patch` | rebase against current `drivers/usb/gadget/dwc2_udc_otg.c`, `drivers/usb/host/dwc2.c`, and current DM bind ordering; prove host RTL8152 and UMS together again |
| panel splash | `0004-rm69a10-logo-port.patch` | port the K230 display/DSI/VO implementation and the `k230_canmv_v3` panel DT, not merely generic upstream MIPI bindings |
| runtime handoff | incoming work outside `3cff765` | inventory it as a separate series before rebasing; it was not silently assumed compatible here |

The Canaan overlay supplies much more than the four local patches: K230 CPU
and DDR code, board/DTS/defconfig material, vendor commands and display code,
and the packaging helper. Upstream now supplies a minimal K230 CPU, CanMV DT,
UART, and DWC2 host baseline, but that does not make the overlay mechanically
applicable. Expected porting pressure points are Kconfig symbol changes,
Driver Model bind/probe and `ofnode` APIs, DWC2 gadget/host internals, modern
DT schema/build rules, and the vendor display/command interfaces. These are
source-based risk predictions; no compilation was performed here.

The present 2022.10 overlay also needs
`KCFLAGS=-Wno-error=int-conversion` with GCC 15 for its USB PHY address code.
New upstream may improve compiler compatibility, but any retained vendor code
must be compiled with the target Nix toolchain and evaluated anew. Do not
carry the warning suppression as an assumption; require a clean, reviewed
diagnostic decision.

## Minimal-risk experiment

1. Before writing a new U-Boot slot, prove a physical recovery route for this
   board: a working card reader plus BootROM fallback, or a separately tested
   RAM-chainload/rollback procedure. A raw backup alone is not remote recovery
   unless a proven writer can reach the card after a failed U-Boot boot. The
   BootROM fallback and RAM chainload have not been tested in this work.
2. Keep a GC-rooted known-good whole-card image and raw hashes of both SPL
   copies, both environment copies, the OpenSBI payload, and the existing
   packaged U-Boot slot.
3. Create a separate, explicitly pinned `v2026.07` source derivation from
   immutable commit `ece349ade2973e220f524ce59e59711cc919263f`, with the
   official release tarball hash recorded when the derivation is introduced.
   Do not switch the normal `ubootK230` input.
4. Start from upstream `k230_canmv_defconfig`; add only enough local
   configuration and DTS to reach serial output and the existing boot flow.
   A physically recoverable, local serial pilot may keep panel splash and UMS
   out of the first boot-to-prompt attempt. A remote-only pilot cannot: it
   must carry and prove UMS in its first functional candidate, since a failed
   replacement cannot run the old UMS helper.
5. Package only the resulting `u-boot.bin` through the current, verified
   gzip-CM/K230-header procedure. Use the *existing* `fn_u-boot-spl.bin` and
   current environments. Assert K230 magic, checksum, load/entry address,
   and packaged U-Boot size at or below 1 MiB before any card operation.
6. First physical proof is a one-slot reversible write with exact direct-I/O
   readback and the already-proved recovery route. It must demonstrate: vendor
   SPL reaches new U-Boot; serial prompt works; MMC and the ported or transient
   OpenSBI/Linux handoff work; and a rollback returns the known image.
7. Reintroduce features one family at a time: UMS on USB0 with the exact
   VID/PID/capacity safeguard; USB1 RTL8152 plus UMS coexistence; the T-Display
   DT and panel splash; then runtime handoff. Each needs a fresh packaged-slot
   size/readback check and board evidence.

Only after that sequence should a full image be considered. A full-image flash
would add SPL, environment, OpenSBI, rootfs, and U-Boot variables when the
upstream documentation already supports testing the 2 MiB U-Boot-proper
boundary alone. A RAM-chainload trial is not proposed as an assumed shortcut:
its compatibility with this BootROM/SPL path is unverified.

## Evidence boundary and remaining unknowns

**Verified by source inspection:** upstream stable and development revisions;
upstream K230/CanMV path existence; its vendor-SPL/2 MiB deployment model;
its host USB/RTL8152 configuration; and the absence of this project's v3
panel/UMS/splash implementation from those paths.

**Already verified elsewhere on this project, but not re-tested here:** the
current source-built 2022.10 stage 1 booted; its UMS and repaired USB host
coexistence have hardware evidence in the cited evidence files.

**Not proven:** a `v2026.07` Nix cross-build; compatibility of the current
K230 header and CM-byte convention with that image; SPL loading a newer
payload; modern U-Boot execution on this T-Display; the `blinux` replacement,
panel output, UMS, RTL8152 coexistence, OpenSBI handoff, Linux boot, BootROM
fallback, or RAM chainload. Those require the staged build and physical proof
above.
