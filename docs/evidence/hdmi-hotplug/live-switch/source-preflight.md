# No-reboot switching: source preflight

Recorded 2026-10-09T14:53:11.176690+00:00. Evidence class: local
kernel source inspection only. No device tree was trial-booted and no physical
plug/unplug transition was observed. The accepted HDMI trial remains running.

The existing LT9611 driver cannot be made a standalone monitor merely by
adding its I2C node to the panel device tree:

- `lt9611_parse_dt()` requires a remote DSI node on input port 0 or 1,
  otherwise returning `-ENODEV` before revision detection.
- Its successful probe registers a DRM bridge and attaches a DSI device.
  Task 4.1 needs status monitoring while the panel keeps that host.
- HPD polling in `lt9611_bridge_detect()` reads register `0x825e` and uses
  bits 2 or 0. Existing polling belongs to an attached HDMI connector;
  it does not establish a standalone poller during the panel boot.
- `canaan_dsi_bind()` resolves its downstream panel or bridge from the
  device-tree graph at bind time. `canaan_dsi_attach()` stores one device,
  and detach clears its panel, device and bridge pointers. This is not a
  runtime display-selection API.

Task 4.1 therefore needs a monitoring path that avoids attaching a second
DSI consumer and leaves touch's shared reset/IRQ ownership intact. Its
physical proof remains open: the monitor must probe alongside the active
panel, and actual cable changes must be checked. The HPD register's behavior
in that mode is still UNVERIFIED. Do not enable the shared HDMI IRQ merely
because its electrical drive type remains unknown.

This does not establish that seamless switching is impossible. After a
successful task-4.1 board proof, task 4.2 requires explicit kernel design for
switching the DSI consumer and compositor-visible output. The optional
reboot-based Settings prototype is not a substitute for that result.

Source artifacts at inspection:

- `nix/patches/mainline/drm/lontium-lt9611-k230.c`, SHA256 `9efcaeffc8483725de6caccb0b5b7625df9a31db75ae76e0c5442f71ca54408c`.
- `nix/patches/mainline/drm/canaan_dsi.c`, SHA256 `6fec2adf9a154e09783c0892ff05fa3af3830094017f0444c2d6571bb3d38ac7`.

Inspection command:

```sh
rg -n 'parse_dt|probe|detect|attach_dsi' nix/patches/mainline/drm/lontium-lt9611-k230.c
rg -n 'find_panel|bridge|attach|detach|bind' nix/patches/mainline/drm/canaan_dsi.c
```

Task 4.1 is not complete; no hardware outcome is inferred from this reading.
