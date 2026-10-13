## Scope preservation

Original HDMI tasks 5.1–5.4 are preserved below with their proof commands.
All implementation/physical gates remain unchecked. The operator authorized
this successor on 2026-10-09 and dropped the obsolete Settings reboot path.
Task 5.1 now selects landscape through the working automatic arrangement. Implement shared geometry
through the archived `the-shell-adapts-to-output-resolution` and reuse its
committed evidence,
while retaining this proposal's separate physical landscape gate.

## 5. Shell and card-shell landscape support


Coordinator cross-reference (2026-10-01):
[`the-shell-adapts-to-output-resolution`](../archive/2026-10-09-the-shell-adapts-to-output-resolution/tasks.md)
owns output configures, Drawer/Home column reflow, Settings transforms and matching
hit-testing. Its host implementation and paired fixtures are recorded there;
its completed tasks 6.1/6.2 record accepted portrait-HDMI fill and targets. This proposal’s
tasks 7.1–7.3 own density, Wi-Fi/theme geometry and dock follow-ups. Use that work for 5.2/5.3 below rather than implementing it twice.
These links do not complete this proposal's HDMI hardware or landscape gates.

- [ ] 5.1 Add a separately selected landscape `HDMI-A-1` qualification
      profile to the Sway configuration (supported EDID mode, for example
      `1280x720`, `transform normal`), preserving the accepted portrait default.
      Record the combined runtime's one-CRTC, mutually exclusive outputs in
      `design.md`; use automatic cable switching, without a reboot button.
      Verify the legacy rollback configuration with `nix build
      .#nixosConfigurations.k230.config.system.build.toplevel` and the shipping
      mainline profile with `nix build .#kernelMainlineDrmShellBootFiles`.
- [ ] 5.2 Parameterize `nix/rust-shell-client/src/lib.rs`'s
      `DESIGN_ASPECT` and the direct `568.0`/`1232.0` literals it and
      `render.rs`/`wifi_ui.rs` use for coordinate scaling, so they derive
      from the actual configured output geometry instead of a compiled-in
      constant, without changing the existing portrait behavior when the
      output really is `DSI-1` at `568x1232` (existing tests must keep
      passing unchanged). Verify with `cargo test` and
      `cargo clippy --all-targets` for `nix/rust-shell-client`.
- [ ] 5.3 Make the home grid/navigation chrome
      (`nix/rust-shell-client/src/home_grid.rs`, `navigation.rs`) not
      visually broken (overlapping, off-screen, or unreachable elements) at
      a landscape aspect ratio, without necessarily redesigning the layout
      for landscape — "usable," not "redesigned," is the bar for this
      change. Verify with new unit tests exercising the same functions at
      a landscape geometry (e.g. `1280x720`) alongside the existing
      `568x1232` cases, `cargo test`.
- [ ] 5.4 On the physical board with an HDMI monitor attached (requires
      a working HDMI boot), record the operator's observation of the home
      screen and Settings rendering on the external monitor without visibly
      broken layout. A monitor photograph is waived by the operator
      (2026-10-09). Commit the report and matching native captures under
      `docs/evidence/hdmi-hotplug/landscape/`.

## 6. Planning validation

- [x] 6.1 Run `openspec validate the-hdmi-shell-works-in-landscape --strict`;
      publish the reviewed successor without claiming implementation.

Planning validation passed 2026-10-09. Implementation and physical proof remain open.

## 7. Responsive-layout follow-ups transferred — 2026-10-09

The operator authorized moving the responsive proposal’s original tasks
6.3–6.5 here. These remain unperformed, with their requirements retained.

- [ ] 7.1 Design and implement a real icon/text density scale for the Home
      grid and the Drawer (the responsive proposal’s density non-goal):
      today only their column counts reflow with `crate::reflow_columns`;
      `ICON_SIZE`/`ROW_HEIGHT`/tile margins stay the panel's own native
      pixel size at every surface size, unlike Settings' content column.
- [ ] 7.2 Design and implement a real reflow (or a uniform, centered scale)
      for `paint_wifi`'s and the theme chooser's existing non-uniform
      `cr.scale(width/568.0, height/1232.0)`, which this change's Settings
      content transform deliberately excludes and leaves as-is.
- [ ] 7.3 Design whether/how Home's dock should reflow its own slot count
      (`DOCK_SLOTS`, deliberately left fixed at 4 by the responsive
      implementation) using the archived responsive 6.1/6.2 evidence and once this
      proposal’s landscape 5.4 evidence is in hand to verify against.

## 8. Panel landscape for the keyboard case — 2026-10-13

Operator, 2026-10-13, with the second board in its keyboard case on the bench:
"notice that in this configuration the board should really be rotated 90
degrees counterclockwise we already had the 'make that layout work' card we
should do it here (you can ignore hdmi i am sure it will be fine we can test
it at the end tho)". Tasks 5.2, 5.3 and 7.1–7.3 are the shared layout work;
complete them here against the panel's 1232×568 geometry as well as HDMI.

- [x] 8.1 Add a `k230.shell.panelTransform` option (`normal`, default, or
      `270`) driving the `output DSI-1` line, and a landscape panel system
      plus its boot files and SD image as separate flake outputs. The default
      system's toplevel derivation SHALL be unchanged. Verify with `nix eval`
      of the default toplevel drvPath against `master` and `nix build` of the
      landscape boot files.
      Done 2026-10-13 in `0804c0aa`: the default toplevel drv was
      `lhdphdj84vyngfcflhvkpdxny2dxljz5…` on both `master` and the change, and
      `.#kernelMainlineDrmShellLandscapeBootFiles` and `.#sdImage-landscape`
      built. Later shell and device-tree fixes on this branch change the
      default system deliberately.
- [ ] 8.2 Make `shell-ui` accept a whole-output configure whose output size
      is learned late or changes at runtime (rotation), instead of rejecting
      it and drawing nothing, while still rejecting a keyboard exclusive-zone
      squish. Verify with new unit tests and `cargo test`.
      Partial 2026-10-13: `frame_bytes` now accepts a 568 px tall frame (the
      board logged `home-configure-rejected` before), with
      `frame_bytes_accepts_the_landscape_panel`. Open: a size change at runtime
      (`update_output` is still empty).
- [ ] 8.3 Lay out wallpaper, Home and dock, Drawer, shade, Settings
      (including Wi-Fi and the theme chooser), notifications, the power sheet
      and the on-screen keyboard at 1232×568 without overlapping, off-screen or
      unreachable controls, with hit-testing matching. Add 1232×568 to the
      responsive host renders. The native 568×1232 renders SHALL stay
      byte-identical. Verify with `cargo test`, `cargo clippy --all-targets`
      and reviewed 1232×568 host renders.
      Partial 2026-10-13: Home (two compact rows, so 2-row widgets fit; also
      fixed the unbounded page growth that OOM-killed `shell-ui`), Shade
      (the sheet keeps one notification row) and Help (two columns). Host
      renders add 1232×568 plus Shade, Power and Help; every portrait and HDMI
      render is byte-identical to `0804c0aa`. `cargo test` 473 passed; clippy
      reports 65 warnings, the same as the base. Reviewed: Home, Drawer,
      Settings, Shade, Power, Help, keyboard. Open: Wi-Fi pages, the theme
      chooser, the folder overlay, and notifications with real items.
- [x] 8.4 Make touch and the edge gestures (drawer, shade, overview) follow
      the rotated panel edges. Verify on the board with injected touch events
      (evidence class: injected) and record which gestures were exercised.
      Done 2026-10-13 (injected, non-persistent trial system; see
      `docs/evidence/panel-landscape/README.md`). Exercised: bottom-edge
      swipe on Home → Drawer, bottom-edge swipe from the Drawer → card
      overview, top-edge pull → Shade, taps on the drawer search field and the
      landscape keyboard. This needed `cs_fit_card`: the card shell never
      started at 1232×568. The operator's finger then showed the
      GT9895's X range is 1080, not 1024 (`touch-range.md`). The device-tree
      correction is committed; its booted proof belongs to 8.5.
- [ ] 8.5 Boot the landscape profile on the second board. Record native
      `grim` captures of each surface in 8.3 and a camera photograph from the
      keyboard side under `docs/evidence/panel-landscape/` (physical: native
      capture plus camera).
      Partial 2026-10-13: native captures and one camera frame are committed,
      but from a `switch-to-configuration test` trial, not a booted landscape
      image, and without the new device tree. Installed and booted at 09:40
      CDT: device tree 1080, no calibration matrix, services active, native
      Home capture (`board/installed-home.png`). Open: the per-surface native
      captures and camera frame again on the installed image, after the
      operator's glass pass.
      Drawer/shade jank on the installed image was the compositor's
      per-layer software rotation (3.5 fps vs portrait's 10.4 fps); the
      landscape profile now uses the rotate-once renderer (8.7 fps) and is
      reinstalled (`rotation-performance.md`; operator: "plenty fast now").
- [ ] 8.6 Operator real-glass check in the keyboard case: open Drawer, shade,
      Settings and an app, type on the keyboard, return Home. Record the
      operator's observation (physical: real glass). Hardware gate.
      Partial 2026-10-13: the operator's finger opened the Drawer and Shade
      from Home and, after the live X calibration, the card overview ("it
      works now"). Settings, an app, typing and the return to Home have not
      been reported yet.
- [ ] 8.7 With the landscape profile, connect HDMI and confirm the existing
      HDMI behavior (output, transform, touchpad relay) is unchanged. Record
      the observation and a native capture (physical). Hardware gate; may run
      last, per the operator.

The stage-1 boot splash logo stays portrait in this change (U-Boot draws it
before any compositor); a landscape splash image is out of scope unless the
operator asks for it.

Host implementation proof: `cargo test --offline --manifest-path
nix/rust-shell-client/Cargo.toml` and `cargo clippy --all-targets --manifest-path
nix/rust-shell-client/Cargo.toml`, plus reviewed native-portrait and HDMI host
render fixtures. Physical layout/hit-target acceptance remains task 5.4.
Planning proof: `openspec validate the-hdmi-shell-works-in-landscape --strict`.
