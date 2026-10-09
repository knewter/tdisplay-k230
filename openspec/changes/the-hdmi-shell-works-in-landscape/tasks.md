## Scope preservation

Original HDMI tasks 5.1–5.4 are preserved below with their proof commands.
All implementation/physical gates remain unchecked. The operator authorized
this successor on 2026-10-09 and dropped the obsolete Settings reboot path.
Task 5.1 now selects landscape through the working automatic arrangement. Implement shared geometry
through `the-shell-adapts-to-output-resolution` and record its actual evidence,
while retaining this proposal's separate physical landscape gate.

## 5. Shell and card-shell landscape support


Coordinator cross-reference (2026-10-01):
[`the-shell-adapts-to-output-resolution`](../the-shell-adapts-to-output-resolution/tasks.md)
owns output configures, Drawer/Home column reflow, Settings transforms and matching
hit-testing. Its host implementation and paired fixtures are recorded there;
its task group 6 retains physical tap/density, Wi-Fi/theme geometry and dock
follow-up. Use that work for 5.2/5.3 below rather than implementing it twice.
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
      grid and the Drawer (`design.md`'s "Non-goal, both passes" section):
      today only their column counts reflow with `crate::reflow_columns`;
      `ICON_SIZE`/`ROW_HEIGHT`/tile margins stay the panel's own native
      pixel size at every surface size, unlike Settings' content column.
- [ ] 7.2 Design and implement a real reflow (or a uniform, centered scale)
      for `paint_wifi`'s and the theme chooser's existing non-uniform
      `cr.scale(width/568.0, height/1232.0)`, which this change's Settings
      content transform deliberately excludes and leaves as-is.
- [ ] 7.3 Design whether/how Home's dock should reflow its own slot count
      (`DOCK_SLOTS`, deliberately left fixed at 4 by task group 7 --
      `design.md`'s audit table) once the responsive proposal’s physical 6.1/6.2 and this
      proposal’s landscape 5.4 evidence are in hand to verify against.

Host implementation proof: `cargo test --offline --manifest-path
nix/rust-shell-client/Cargo.toml` and `cargo clippy --all-targets --manifest-path
nix/rust-shell-client/Cargo.toml`, plus reviewed native-portrait and HDMI host
render fixtures. Physical layout/hit-target acceptance remains task 5.4.
Planning proof: `openspec validate the-hdmi-shell-works-in-landscape --strict`.
