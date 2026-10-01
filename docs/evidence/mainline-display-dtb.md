# Opt-in mainline display DTB source check

Follow-up: this evidence records the initial candidate before the local genpd
port. `docs/evidence/mainline-display-power-domain.md` records the subsequent
DRM-only provider, current DTB and matching boot bundle. The initial omission
below remains historical evidence; runtime power/panel/touch behavior is
still UNVERIFIED.

## Result

On 2026-09-29, the host C preprocessor and `dtc` compiled
`nix/dts/k230-tdisplay-mainline-drm.dts` against the pinned mainline source
output and round-tripped the resulting DTB. The complete stdout/stderr is in
`mainline-display-dtb.log`. The resulting blob is kept only in the ignored
`.scratch/mainline-display-dtb-check/` directory.

This proves DTS syntax, includes, phandle resolution, and serialized node
content for the host compiler invocation. The matching Nix derivation also
built successfully; its output and the paired boot-files output are recorded
in `mainline-display-nix-build.md`. Neither host check proves clock or reset
behavior on silicon, DT binding correctness at probe time, powered display
output, or touch input.
The non-MMIO `display-subsystem` sits outside the SoC `simple-bus`, so the
host compile emits no simple-bus register warning. The source does not claim
a working panel.

## Reproducible command

```sh
tools/mainline-display-dtb-check.sh
```

The script stages the pinned `k230.dtsi` includes plus this project's
mainline console DTS and RM69A10 panel DTSI under the checkout's ignored
`.scratch/`, preprocesses with the kernel's `scripts/dtc/include-prefixes`,
compiles with `dtc -@`, and decompiles for a round-trip check. It verified the
resolved Goodix I2C node, display subsystem, VO, DSI, and universal panel
compatibles. The host-check blob was 10,553 bytes, matching the built Nix derivation DTB.

## Grounding and known dependency

The node ranges and interrupts match the pinned vendor tree's
`arch/riscv/boot/dts/canaan/k230.dtsi`: I2C3 at `0x91408000`/IRQ 24, VO at
`0x90840000`/IRQ 133, and DSI at `0x90850000`. The panel GPIOs, timing, DSI
lane count, and touch address/IRQ/reset/size come from the board file and
panel DTSI already in this repository (`nix/dts/k230-tdisplay.dts`,
`nix/dts/display-rm69a10-568x1232.dtsi`). The pinned mainline source has
`K230_LS_I2C3_RATE` and `K230_LS_I2C3_APB_GATE` in
`include/dt-bindings/clock/canaan,k230-clk.h`, mapped by
`drivers/clk/clk-k230.c`; these are used for the new I2C3 node. The generic
DesignWare I2C driver obtains functional and optional `pclk` clocks but does
not acquire a reset controller, so the available `RST_I2C3` is not attached
as unused metadata.

The imported VO/DSI drivers do not call the clock or reset consumer APIs;
their current port writes its display/PHY registers directly. The DTB
therefore does not guess clock/reset phandles for these nodes. A separate,
material gap is display power control: unlike the vendor DTS, this candidate
omits `power-domains = <&sysctl_power K230_PM_DOMAIN_DISP>` because the exact
pinned mainline source has no `sysctl_power` provider or
`K230_PM_DOMAIN_DISP` implementation. Whether firmware leaves this domain
powered or a future mainline provider is required is UNVERIFIED; no physical
probe has been made.

`deviceTreeMainlineDrm` and `kernelMainlineDrmBootFiles` remain opt-in
outputs. The boot bundle pairs the candidate Image and DTB for manual U-Boot
loading only; it contains no initrd or root filesystem and is not boot proof.
