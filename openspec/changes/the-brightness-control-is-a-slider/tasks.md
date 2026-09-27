## 1. Shared slider component

- [x] 1.1 Add `nix/rust-shell-client/src/slider.rs`: value↔x mapping
      (`value_at_x`/`x_at_value`), `clamp_percent` (3% floor), the
      ~20-30/s live-write throttle (`Drag::should_write`), and the armed
      `Drag` struct, with unit tests for the mapping, the clamp, and the
      throttle. Proven: `cargo test --lib` (236 passed, 0 failed,
      including `slider::tests::*`).
- [x] 1.2 Reuse one `paint_slider`/`paint_sun` in `render.rs` for both the
      Settings row and the Shade header, replacing the Settings `−`/`+`
      stepper text. Proven: `cargo test --lib` (render's own pixel-sampled
      shade/preview tests updated and passing after the layout shift this
      needed).

## 2. Touch dispatch and gesture disambiguation

- [x] 2.1 Add `service_ui::slider_band` (gated on
      `ControlState::Writable`) and fold it into
      `shade_panel_close_zone`'s existing carve-out, alongside the
      existing notification-list exclusion. Remove the old release-only
      stepper hit-test from `panel_intent`. Unit tests cover both the
      Settings row band and the Shade band, including the
      gesture-disambiguation case (a touch that starts on the slider band
      is excluded from close-drag candidacy regardless of direction; a
      touch starting elsewhere still engages the close drag exactly as
      before). Proven: `cargo test --lib`
      (`service_ui::tests::slider_band_owns_its_row_and_is_excluded_from_the_close_drag_candidacy`
      and the existing close-drag suite, all passing).
- [x] 2.2 Arm/track/finalize the slider drag in `main.rs`'s
      `down`/`motion`/`up`/`cancel` touch handlers, as a new sibling
      branch ahead of the existing route-specific dispatch (never editing
      the theme/wifi dispatch those already own). Proven:
      `cargo test --bin k230-shell-rust` (19 passed) and
      `cargo clippy --all-targets` report no warning attributable to
      these files.

## 3. Live writes without a subprocess

- [x] 3.1 Add `ServiceRequest::BrightnessLive(u8)` and
      `service_data::write_backlight_live`, writing the backlight sysfs
      `brightness` attribute directly (mirroring
      `tools/device_settings.py`'s own backlight lookup), and swallow its
      reply in `main.rs::service_reply` (fire-and-forget; the release
      that follows always sends the authoritative `Brightness` request).
      Proven: `cargo test --test service_data_module` (11 passed,
      including `live_backlight_write_scales_percent_by_the_real_max_
      brightness`, `live_backlight_write_rejects_out_of_range_percent_
      and_missing_device`, and
      `worker_rejects_an_out_of_range_live_brightness_write_without_
      shelling_out`).
- [x] 3.2 Reflect the real value on open: `ShellClient::refresh_route`
      now also submits `RefreshSettings` when the Shade opens (previously
      only `RefreshNotifications`), so an external brightness change
      shows in either sheet. Proven: same test run as 3.1 (the existing
      worker/reply fixtures cover `RefreshSettings`'s path unchanged).

## 4. Build proof

- [x] 4.1 `cargo test` for `nix/rust-shell-client` (lib, the `k230-shell-
      rust` bin's own tests, and the `service_data_module`/
      `appearance_module`/`background_decode_module` integration tests) —
      all pass. `cargo clippy --all-targets` reports no warning
      attributable to this change's files; a pre-existing
      `crate::runtime_trace` unresolved-import failure in
      `tests/theme_catalog_module.rs` (added by a prior, unrelated commit,
      `ad752b1d`, to a file this change does not touch) blocks a single
      combined `cargo test`/`cargo clippy --all-targets` invocation and is
      not this change's to fix — a separate, concurrent session owns the
      theme picker files.
- [x] 4.2 `nix build .#handheld-shell-rust --max-jobs 1 --cores 6`.
      Proven: exit 0, `/nix/store/...` (see the report for the exact
      path).
- [x] 4.3 `nix build
      .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel
      --max-jobs 1 --cores 6 --no-link --print-out-paths`. Proven: exit
      0, `/nix/store/...-nixos-system-...` (see the report for the exact
      path).

## 5. QEMU host evidence

- [ ] 5.1 If a Rust-client QEMU capture harness exists
      (`tests/*qemu*.py`), take host screenshots of Settings and the
      Shade showing the slider, under `docs/evidence/brightness-slider/`
      with blob-inventory rows, and confirm `python3 tools/blob-scan.py`
      exits 0. Left open by this worktree; see the report for what was
      found.

## 6. Physical acceptance (board, open)

- [ ] 6.1 Real-finger drag and tap-to-jump on the Settings slider,
      confirming the panel's actual brightness follows the finger live
      and clamps at 3%, not 0%, at the low end. **Not done in this
      worktree** — AGENTS.md and this task's own instructions keep board
      access and real-finger acceptance out of scope here.
- [ ] 6.2 Real-finger drag on the Shade's slider, confirming the shade
      does not begin closing on a horizontal drag there, and that a drag
      starting elsewhere on the sheet still closes it. **Not done in this
      worktree.**
- [ ] 6.3 Confirm on hardware that opening Settings or the Shade after an
      external brightness change (e.g. the other sheet's own drag) shows
      the real current value, not a stale one. **Not done in this
      worktree.**
