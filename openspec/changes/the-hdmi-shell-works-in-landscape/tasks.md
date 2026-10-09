## Scope preservation

Original HDMI tasks 5.1–5.4 are copied below with all proof commands retained.
All remain unchecked. Split/archive approval is pending; the original proposal
still owns this scope until the operator approves. Implement shared geometry
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

- [ ] 5.1 Add an `HDMI-A-1` output stanza to `nix/shell.nix`'s Sway config
      (mode matching task 2.2's target, e.g. `1280x720`, `transform
      normal`), alongside the existing `DSI-1` stanza, and decide (record
      in `design.md` if it changes) whether both outputs are ever active
      in the same Sway session or whether the reboot-based switch means
      only one is ever present at a time in the near term. Verify with
      `nix build .#nixosConfigurations.k230.config.system.build.toplevel`.
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
