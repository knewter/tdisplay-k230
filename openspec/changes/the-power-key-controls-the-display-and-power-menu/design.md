## Context

The replacement card boots the coherent NixOS image with Sway, the Rust shell and a writable root. The operator reports an immediate reset on a tap of the lower physical button; the exact switch identity is awaiting confirmation. The current kernel/device tree contains no K230 PMU input device (`docs/research/board-capability-inventory.md`, power-key section); the running board currently exposes only its touchscreen input. LILYGO's `0064-input-k230-pmu-pwrkey.patch` supplies an edge-driven Linux input driver and PMU DT node, but its 5-second `orderly_poweroff(true)` and PMU system-off callback do not implement the requested confirmation flow. Its upstream source is `k230_bsp/overlay/buildroot-overlay/linux/0064-input-k230-pmu-pwrkey.patch` in Xinyuan-LILYGO/T-Display-K230.

The existing backlight path has physical proof for `swaymsg output DSI-1 power off/on` and restoring brightness (`docs/evidence/backlight/runtime-recovery/README.md`). The Rust shell already owns the Settings power confirmation and has a bounded route socket. The image and known-good card recovery copy are available.

## Goals / Non-Goals

**Goals:** Let Linux receive both power-key edges, preserve a running session on tap, reuse the proven output power cycle, and show a global confirmation sheet on hold.

**Non-Goals:** Suspend, battery operation, firmware-level emergency cutoff, or changing a separate electrically wired RESET switch.

## Decisions

1. **Identify the physical switch before a kernel write.** Inspect the board marking/schematic and compare the operator's button to PMU INT0. Record the current reset observation separately from proven PMU input. If it is RESET, do not claim software interception; adjust the hardware objective in a reviewed change rather than flashing a misleading implementation.
2. **Port only the input portion of LILYGO's PMU driver first.** Build the DT/Kconfig/driver against the pinned kernel. Remove its automatic long-hold `orderly_poweroff` and system-off registration for this change; both bypass the requested sheet. Preserve edge routing, debounce and input reporting, but review every PMU register write against the vendor flow. Stage a candidate with a read-only serial/evdev probe, one deliberate short physical press and known-good card recovery available before enabling the user policy. If a short press still resets before a Linux release event, stop hardware claims and keep the existing image available.
3. **Make one owner of press duration.** A small system service reads only the identified named `K230 PMU Power Key` evdev device, handles `KEY_POWER` press/release, debounces repeats and uses a monotonic hold threshold (initially 700 ms). It ignores synthesized `EV_KEY` repeat values and disconnects cleanly. `logind` ignores this key so it cannot also execute its default shutdown policy. The helper sends a bounded route request to the Rust shell on hold, and a Sway output-power command on a completed short press. It verifies the active output and remembers whether it turned it off; restart state is reconciled from Sway rather than a stale file.
4. **Use a dedicated power route in the Rust shell.** `--surface power` opens a compact sheet over the current app using the existing layer and theme tokens. Tap targets for Cancel, Power off and Restart are at least 56 px high. Selection opens the existing confirmation state and uses the same limited system request path as Settings. Touch outside and the existing dismissal gesture close without action. A long hold that begins while dark wakes the panel before opening the sheet; release does not toggle it back off.
5. **Keep host and board evidence distinct.** Host unit tests cover bounce, repeats, release before/after threshold, duplicate sheet prevention, wake consumption and confirmation state. QEMU may show layout/route logic. The named physical proof is a serial event log plus camera recording of tap off, tap on, long-hold sheet, Cancel, and confirmation without execution. Actual Power off/Restart commands require their own deliberate physical trial after the non-destructive paths pass.

Rejected: copying the vendor patch unchanged (its hold powers off), mapping `KEY_POWER` directly to `systemctl` (no confirmation), and using zero backlight brightness as display sleep (the validated Sway output-power path preserves the chosen brightness).

## Risks / Trade-offs

- PMU programming can cut power or hang boot → keep the first port limited to input, boot the candidate with a working serial console and preserved current card image, and stop on any missing release/reset evidence.
- The lower switch may be RESET rather than PMU INT0 → identify it before claiming this interaction; software cannot intercept a direct reset line.
- A missing compositor or shell could leave the panel dark → wake handling must work without the shell route, and a service failure must default to leaving the display on.
- Input ownership can conflict with logind or Sway → ignore logind's power key policy and ensure only the named helper takes an action; prove one event gives one result.

## Migration Plan

Publish this proposal first. Build and inspect the input-only kernel candidate; then deploy to the reserved board using the repository's guarded `/boot` update or the saved-image flash path. Prove physical events before enabling policy. Deploy helper and shell route from the image, verify short/long behavior, then record actual glass and serial evidence. Restore the saved coherent image if PMU boot or display recovery fails. Archive only after every named physical gate passes.
