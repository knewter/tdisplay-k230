## 1. Kernel: DSI-command backlight

- [x] 1.1 Add `struct backlight_device *bl`, `bool prepared`,
      `u32 default_brightness`, `u32 max_brightness`, `bool
      dsi_command_backlight` to `struct canaan_panel`; parse
      `canaan,dsi-command-backlight` (bool), `default-brightness` and
      `max-brightness` (u32, defaulting 254/255) in
      `canaan_panel_parse_dt()`. Prove with
      `nix build .#kernel --max-jobs 1 --cores 6` (build proof only — DT
      parsing itself is exercised only once loaded on hardware).
- [x] 1.2 Implement `canaan_panel_bl_update_status()`/register the backlight
      with `devm_backlight_device_register()` when
      `dsi_command_backlight` is set, using `MIPI_DCS_WRITE_CONTROL_DISPLAY`
      (0x53, value `0x24`) then `mipi_dsi_dcs_set_display_brightness()`
      (0x51); assign `ctx->panel.backlight` so `drm_panel_enable`/
      `drm_panel_disable` drive it automatically across a modeset or DPMS
      cycle. Guard every write on `p->prepared`. Prove with
      `nix build .#kernel --max-jobs 1 --cores 6` (build proof only).
- [x] 1.3 Confirm the existing reset-pulse fix in `canaan_panel_prepare()`
      (already landed in `nix/kernel.nix`'s postPatch history) runs before
      the init sequence on every prepare, so brightness code added in 1.2
      never races an unreset panel. No new patch — a citation check against
      the current `nix/kernel.nix`, recorded in design.md.

## 2. Device tree

- [x] 2.1 Add `canaan,dsi-command-backlight;`, `default-brightness =
      <254>;`, `max-brightness = <255>;` to the `lcd: panel@0` node in
      `nix/dts/display-rm69a10-568x1232.dtsi` (not touched by
      `feat/speaker`, so no merge risk with the concurrent audio DT work).
      Prove with `nix build .#deviceTree --max-jobs 1 --cores 6` (build
      proof only).

## 3. NixOS: shell write access

- [x] 3.1 Add a `services.udev.extraRules` entry in `nix/k230.nix`
      granting the `shell` group write access to
      `/sys/class/backlight/*/brightness` (chgrp/chmod on device add).
      Prove with
      `nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel --max-jobs 1 --cores 6 --no-link --print-out-paths`
      (build proof only — no board to exercise the rule yet).

## 4. Rust shell: boundary test

- [x] 4.1 Add a unit test in `nix/rust-shell-client/src/service_ui.rs`
      covering the brightness stepper's 0% and 100% clamps (previously
      untested because no real backend existed for the clamp to matter
      against). Prove with
      `cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml`
      and `cargo clippy --offline --manifest-path nix/rust-shell-client/Cargo.toml -- -D warnings`
      (host proof only).

## 5. Physical acceptance

- [ ] 5.1 Install the built kernel/DTB to `/boot` and reboot (a kernel and
      DT change, not just activation). Under the reserved board lock,
      confirm `ls /sys/class/backlight` shows exactly one device, then
      write brightness at 10%, 50% and 100% and camera-observe the panel
      changing. Commit evidence under `docs/evidence/backlight/`
      (hardware proof only).
- [ ] 5.2 Cycle a modeset or DPMS off/on (see the combined board test plan
      for the exact command) and confirm the previously set brightness is
      still in effect afterward, not the fixed default. Commit evidence
      under `docs/evidence/backlight/` (hardware proof only).
