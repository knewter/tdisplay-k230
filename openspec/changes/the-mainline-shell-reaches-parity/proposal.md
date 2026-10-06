## Why

The full coherent shell now boots on the mainline kernel and draws Home on the
panel, but it is not yet a system someone could use in place of the vendor
kernel: the firewall unit fails, the side button does nothing, there is no
sound and no Wi-Fi, touch has only been proven from `evtest` on the console
image (never inside sway), and two clock-table defects remain that could bite
the next driver. The console-only mainline kernel also still lacks the clock
fixes that made the DRM kernel boot. Closing these gaps is what stands between
"mainline boots" and "mainline could become the default".

## What Changes

- The mainline kernel carries the same firewall kernel configuration as the
  vendor kernel, so `firewall.service` starts on the mainline shell.
- The side power button works under mainline: the vendored PMU power-key
  driver is forward-ported with a PMU device-tree node, and the shell's
  existing power-key behaviour (power sheet) responds to a physical press.
- Sound plays through the speaker under mainline: the K230 I2S/codec path
  (vendor `sound/soc/canaan`, with the external I2S switch patch) is
  forward-ported and PipeWire plays a test tone that a microphone or person hears.
- Wi-Fi associates under mainline: `mmc_sd0` (SDIO) is enabled with owned
  clocks, and the RTL8189FTV out-of-tree driver is built against the mainline
  kernel (or the trial records exactly why it cannot be, as a successor).
- Touch inside the full shell is proven: a deliberate finger tap/drag moves
  something in sway (camera + input log), not only raw `evtest` events.
- Thermal, ADC and crypto: each vendor driver is inventoried against the
  pinned mainline tree; thermal is forward-ported (it guards the SoC), ADC and
  crypto are ported only if a shipped service uses them, otherwise recorded as
  explicit non-goals with the reason.
- Clock table: model the missing display `clkext` gate (sysctl 0x74 bit 5) and
  resolve the `usb_480m`/`usb_100m` gates aliased on 0x100 bit 0 using the
  vendor tree, with a physical USB re-check.
- The console (non-DRM) mainline kernel gets the `spi2axi` and `vpu_ddrcp2`
  critical-clock fixes it currently lacks.
- The system-trial controller's touch retrieval no longer times out on long
  captures (bounded event summary on the board instead of a raw transcript).

Non-goals: making mainline the default boot, upstream submission, GPU/VGLite,
the second core, NPU/KPU, LoRa, Bluetooth, camera/ISP, and any change to the
protected normal (vendor-kernel) system or its boot selection.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `system/kernel`: mainline variants carry the clock fixes and firewall config;
  thermal is forward-ported; ADC/crypto disposition is recorded; clock-table
  defects (clkext, usb_480m/usb_100m alias) are corrected.
- `system/nixos-config`: the mainline full-shell variant starts every unit the
  vendor-kernel system starts, except recorded non-goals.
- `system/audio`: audio plays under the mainline kernel.
- `radio/wifi`: Wi-Fi associates under the mainline kernel.
- `display/touch`: a deliberate finger interaction drives the sway shell under
  the mainline kernel.
- `runtime/shell`: the power key reaches the shell under the mainline kernel.

## Impact

- Kernel: `nix/kernel-mainline.nix`, `nix/kernel-mainline-drm.nix`, new
  forward-ported drivers under `nix/patches/mainline/` (pwrkey, audio, thermal),
  clock patches against `drivers/clk/clk-k230.c`, DT in
  `nix/dts/k230-tdisplay-mainline{,-drm}.dts`.
- Nix: `flake.nix` mainline variants; the RTL8189FTV module derivation in
  `nix/hardware.nix` built against the mainline kernel.
- Tooling: `tools/mainline-drm-system-trial.py` touch retrieval.
- Board: every item except the controller change and source inventory needs the
  physical board (guarded staging, volatile U-Boot selection, camera; audio
  needs a listener or microphone; Wi-Fi needs a reachable AP whose credentials
  stay in the protected configuration path). Kernel builds take 30–70 minutes
  each on the shared host.
- The protected normal system, its boot files and selection are not modified.
