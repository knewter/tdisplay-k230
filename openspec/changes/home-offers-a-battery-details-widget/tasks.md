## 1. Implementation

- [x] 1.1 Add a details snapshot and `uevent` parser to `home_widgets::battery`,
      keeping `BatteryState`, `read_state` and `format` unchanged; add the
      `BatteryDetails` widget kind (4x2, new serialized tag), its picker entry,
      painting, and the 10 s / 30 s poll choice with change-gated repaint.
      Proof (host): `cd nix/rust-shell-client && cargo test`.

## 2. Host evidence

- [x] 2.1 Render charging, discharging and no-battery at 568x1232, 1232x568 and
      1280x800 to `docs/evidence/battery-details-widget/host/` with a README;
      inspect the images; register the PNGs in `docs/blob-inventory.md` and run
      `python3 tools/blob-scan.py --no-vendor`. Evidence class: host render.
- [ ] 2.2 Build the bundle: `nix build .#kernelMainlineDrmShellLandscapeHdmiBootFiles`.
      Evidence class: host build.

## 3. Board

- [ ] 3.1 The operator places the widget on Home on the board and confirms the
      displayed values against `/sys/class/power_supply`. Evidence class:
      board observation. Not performed; keep open until recorded.
