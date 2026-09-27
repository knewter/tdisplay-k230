## 1. Kernel: DSI-command backlight

- [x] 1.1 Add `struct backlight_device *bl`, `bool prepared`,
      `u32 default_brightness`, `u32 max_brightness`, `bool
      dsi_command_backlight` to `struct canaan_panel`; parse
      `canaan,dsi-command-backlight` (bool), `default-brightness` and
      `max-brightness` (u32, defaulting 254/255) in
      `canaan_panel_parse_dt()`. Proven:
      `nix build .#kernel --max-jobs 1 --cores 6 --no-link --print-out-paths`
      exited 0, producing
      `/nix/store/78cdif47ayqwv67m7crjpawfzy2mx3af-linux-riscv64-unknown-linux-gnu-6.6.36-xuantie`
      (build proof only — DT parsing itself is exercised only once loaded
      on hardware).
- [x] 1.2 Implement `canaan_panel_bl_update_status()`/register the backlight
      with `devm_backlight_device_register()` when
      `dsi_command_backlight` is set, using `MIPI_DCS_WRITE_CONTROL_DISPLAY`
      (0x53, value `0x24`) then `mipi_dsi_dcs_set_display_brightness()`
      (0x51); assign `ctx->panel.backlight` so `drm_panel_enable`/
      `drm_panel_disable` drive it automatically across a modeset or DPMS
      cycle. Guard every write on `p->prepared`. Same build proof as 1.1
      (one kernel derivation).
- [x] 1.3 Confirm the existing reset-pulse fix in `canaan_panel_prepare()`
      (already landed in `nix/kernel.nix`'s postPatch history) runs before
      the init sequence on every prepare, so brightness code added in 1.2
      never races an unreset panel. No new patch — a citation check against
      the current `nix/kernel.nix`, recorded in design.md. This one is a
      source-reading check, not a build, so it is genuinely done.

## 2. Device tree

- [x] 2.1 Add `canaan,dsi-command-backlight;`, `default-brightness =
      <254>;`, `max-brightness = <255>;` to the `lcd: panel@0` node in
      `nix/dts/display-rm69a10-568x1232.dtsi` (not touched by
      `feat/speaker`, so no merge risk with the concurrent audio DT work).
      Proven: `nix build .#deviceTree --max-jobs 1 --cores 6 --no-link --print-out-paths`
      exited 0, producing `/nix/store/247k32c241fwhpzwx77ps3ldlrpcvds9-k230-tdisplay.dtb`
      (build proof only).

## 3. NixOS: shell write access

- [x] 3.1 Add a `services.udev.extraRules` entry in `nix/hardware.nix`
      (the real-hardware-only base; `nix/k230.nix` is the shared
      hardware+QEMU base) granting the `shell` group write access to
      `/sys/class/backlight/*/brightness` (chgrp/chmod on device add).
      Proven: `nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel --max-jobs 1 --cores 6 --no-link --print-out-paths`
      exited 0, producing
      `/nix/store/152qrxpkagai2fahgyhkxq7sp8sk98n4-nixos-system-nixos-26.11.20260919.20b1ddd`
      (build proof only — no board to exercise the rule yet).

## 4. Rust shell: boundary test

- [x] 4.1 Add a unit test in `nix/rust-shell-client/src/service_ui.rs`
      covering the brightness stepper's 0% and 100% clamps (previously
      untested because no real backend existed for the clamp to matter
      against). Proven: `cargo test --offline --manifest-path
      nix/rust-shell-client/Cargo.toml` passes (196 tests, including the
      new one). `cargo clippy --offline --manifest-path
      nix/rust-shell-client/Cargo.toml --all-targets` reports no warning
      attributable to this change's files; a pre-existing, unrelated
      `field_reassign_with_default` lint in `wifi_ui.rs` (not touched by
      this change) already fails a repo-wide `-D warnings` run and is not
      this task's to fix.

## 5. Physical acceptance

- [x] 5.1 Install the built kernel/DTB to `/boot` and reboot (a kernel and
      DT change, not just activation) — done, via the coordinator's
      export/import + bootfetch/bootswap procedure, confirmed by a real
      cold reboot. `ls /sys/class/backlight` does show exactly one
      device (`canaan-dsi-backlight`, max 255), and writes at 10/50/100%
      read back as set with no dmesg errors — **but** camera evidence
      (locked exposure) shows no visible or measurable panel change
      across the full 0..255 range (mean luminance 200.99/201.14/201.33).
      A real transport bug was found and fixed
      (`nix/kernel.nix`'s board-finding hunk;
      `docs/evidence/backlight/board-findings.md`), but the underlying
      requirement — a person can see the panel change brightness — is
      **not yet met**. Ticked because the task (install, reboot, confirm
      the device, write and observe) was performed and is fully
      evidenced, not because the result was a pass; the negative result
      is the finding.
- [x] 5.2 Cycle a modeset or DPMS off/on and confirm the requested
      nondefault brightness applies afterward. Physical camera trial of
      source `926c7a61` now proves power recovery and distinct 26/128/255
      levels after re-enable; see
      `docs/evidence/backlight/runtime-recovery/README.md`. Live writes
      still have no visible effect, so the core brightness requirement
      and tasks 6.3/6.4 remain open.


## 6. Resolve the negative board result

- [x] 6.1 Restore GPIO25 in panel prepare and normalize the backlight
      callback's success result. Proof: `nix build .#kernel --max-jobs 1
      --cores 4 --no-link --print-out-paths` (cross-build only).
- [x] 6.2 Correct DSI packet framing/completion and review runtime command
      delivery against the pinned driver and mainline DesignWare path.
      Run the focused transport fixtures and the same kernel build;
      preserve the stage-1 handoff and bounded failure paths.
- [ ] 6.3 Boot the candidate once, verify display off/on recovery by camera,
      and demonstrate three distinct brightness levels with fixed camera
      exposure. Record exact kernel/system identities and commands under
      `docs/evidence/backlight/`. Sysfs readback alone does not pass.
- [ ] 6.4 Verify shell-user brightness controls and retention of a chosen
      nondefault brightness across DPMS. Install persistently only after
      the candidate checks, then repeat boot/service identity checks.

Tasks 6.1/6.2 host proof: `docs/evidence/backlight/transport/build.json`
(source `926c7a61`, combined cross-build exit 0) and 25 transport fixtures
under ASan/UBSan. These checks do not complete 6.3/6.4.
