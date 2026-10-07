## Context

See proposal.md - Why. State on 2026-10-06 (archived
`2026-10-06-the-board-runs-a-mainline-kernel`): the DRM mainline kernel
(`kernelMainlineDrm`, 7.3.0-rc5) boots the full coherent shell
(`k230-mainline-drm-shell`) to the Home UI with ordinary unused-clock cleanup.
That required display/RTC/GPIO clock ownership, `spi2axi` and `vpu_ddrcp2`
`CLK_IS_CRITICAL`, and `FOP_UNSIGNED_OFFSET` in the canaan DRM fops. Those
critical-clock patches are wired only into `nix/kernel-mainline-drm.nix`; the
console kernel (`nix/kernel-mainline.nix`) still builds without them.
Observed gaps on the full-shell boot: `firewall.service` failed; no PMU
power-key input, sound card, thermal zone or Wi-Fi interface exists; touch was
proven only via `evtest` on the console image. The controller's touch phase
timed out reading back ~240 KB of `evtest` text.

Every physical step uses the established pattern: guarded staging from the
protected normal system, volatile U-Boot selection, controller `begin`, camera
on the panel, then `reboot` from the candidate (or an operator reset on
failure) and the reviewed recovery checker. Display/console boots no longer
need operator resets when they pass.

## Goals / Non-Goals

**Goals:**
- Each gap closes with physical evidence of its own class (UART, camera,
  real finger, audible tone, network reachability), or becomes an explicit
  successor with the exact blocker.
- Shared kernel fixes move to the base mainline kernel so every variant gets them.

**Non-Goals:**
- Switching the default boot, upstreaming, GPU, second core, NPU, LoRa,
  Bluetooth, ISP; any protected normal system change.

## Decisions

1. **Move the clock patches to the base mainline kernel (kernel layer).**
   `k230-clk-spi2axi-critical.patch` and `k230-clk-vpu-ddrcp2-dphy.patch` move
   from `kernel-mainline-drm.nix` to `kernel-mainline.nix`'s patch list so the
   console kernel inherits them. Rejected: duplicating the list in both files
   (drifts); `clk_ignore_unused` on the command line (hides future ownership bugs,
   and the bisection already identified the specific gates).

2. **Firewall: reuse `nix/kernel-firewall.config` (kernel config layer).** The
   vendor kernel appends this fragment; mainline gets the same fragment applied
   through its structured config. Rejected: disabling the firewall unit on the
   mainline variant (a silent security regression).

3. **Power key: forward-port the vendored `k230-pmu-pwrkey.c` with a PMU DT node
   (kernel + DT).** The driver is ours already (LILYGO-vendored); port it
   against 7.3 APIs and add the node from the vendor DT, claiming the PMU APB
   gate the RTC fix already exposed. Rejected: a userspace GPIO poller (the key
   is a PMU interrupt, not a GPIO).

4. **Audio: forward-port `sound/soc/canaan` (kernel + DT), then verify through
   the existing PipeWire session (userspace).** Port the I2S/codec driver with
   the external-I2S-switch patch and owned clocks (`ls_audio_*`, `ls_codec_*`
   gates are currently unclaimed). Acceptance needs a heard tone; a USB
   microphone recording on the host is acceptable evidence if the operator is
   away. Rejected: claiming audio from a registered ALSA card alone.

5. **Wi-Fi: enable `mmc_sd0` SDIO with owned clocks (DT), then build the
   existing RTL8189FTV out-of-tree module against the mainline kernel (Nix).**
   If the 6.6-era module does not compile against 7.3, record the first error
   set and either patch minimally (API renames) or stop with a successor;
   rejected: replacing it with the staging `rtl8189fs` fork of unknown
   provenance without review. Secrets only via the protected path.

6. **Touch in shell: camera-recorded deliberate tap on a Home target (userspace
   evidence)**, compared with the same tap under the vendor kernel. The
   controller's touch retrieval switches to a bounded board-side summary
   (counts of down/up/positions/SYN) printed as one framed line, keeping the
   raw `evtest` log on the board for optional retrieval. Rejected: raising the
   timeout (still scales with touch length).

7. **Clock table (documentation, no kernel change).** The vendor tree gates
   `usb_clk480` and `usb_clk100` on the same 0x100 bit 0, so mainline's shared
   bit is faithful hardware, not an alias to fix. Mainline leaves the vendor
   `disp_clkext` gate (0x74 bit 5) unmodelled; Linux never writes it, U-Boot's
   setting stands and the panel works. Rejected: adding a `display_clkext`
   gate (with no consumer it would be gated by unused-clock cleanup, the bug
   class this work removed) and splitting the USB bits (would model hardware
   that does not exist). Commit the comparison table with these reasons.

8. **Thermal (kernel + DT):** forward-port `canaan_thermal.c` with the vendor
   bounded-read-loop fix. ADC/PWM/crypto: inventory first; port only if a shipped
   unit consumes them, else record non-goal.

## Risks / Trade-offs

- [Out-of-tree Wi-Fi driver may not build on 7.3] → bounded attempt, then an
  explicit successor with the failure log.
- [Audio clocks or reset lines differ from vendor] → reuse the clock-ownership
  method (live `clk_summary`, hold/bisect) proven on the display.
- [Each kernel change costs a 30–70 minute build on a shared host] → batch
  kernel changes per build where they are independent; DT-only changes rebuild
  in minutes.
- [Operator presence needed for touch-in-shell, power key and audio] → schedule
  those boots together; display/console boots self-recover.
- [Moving clock patches changes every mainline derivation hash] → expected;
  record new identities in evidence.
