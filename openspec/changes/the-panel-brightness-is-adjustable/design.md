## Context

See proposal.md. Grounding for this design, per `.skills/k230-spec-change/SKILL.md`'s
ordering:

- **Vendor source read directly**, from the pinned tree's own unpacked copy
  (`/nix/store/bjgv1xn5b66gbz2kxv2aqzr1szp7dk7c-linux-xuantie-k230-src` at
  the time of writing — the same tree `nix/kernel-src.nix` pins):
  `drivers/gpu/drm/panel/panel-canaan-universal.c` registers no backlight
  device today; `ctx->power_on` (DT property `backlight_gpio`) is only an
  enable *gate* (GPIO25, driven high once at probe and low at unprepare),
  not a brightness control. `MIPI_DCS_SET_DISPLAY_BRIGHTNESS = 0x51` and
  `MIPI_DCS_WRITE_CONTROL_DISPLAY = 0x53` are both already defined in the
  pinned tree's `include/video/mipi_display.h`. `DRM_PANEL_CANAAN_UNIVERSAL`
  already `depends on BACKLIGHT_CLASS_DEVICE`, and
  `CONFIG_BACKLIGHT_CLASS_DEVICE=y` is already set in
  `arch/riscv/configs/k230_defconfig` — so no new Kconfig symbol is needed,
  only the driver code and DT properties.
- **A real mainline reference pattern**, not a from-scratch design: this
  pinned tree's own `drivers/gpu/drm/panel/panel-samsung-s6d7aa0.c`
  (`s6d7aa0_bl_update_status`/`s6d7aa0_create_backlight`,
  lines 184–226) is the exact shape being adapted — a DSI-command backlight
  registered with `devm_backlight_device_register`, driven by
  `mipi_dsi_dcs_set_display_brightness()`. `drivers/gpu/drm/drm_panel.c`
  (`drm_panel_enable`/`drm_panel_disable`) calls `backlight_enable()`/
  `backlight_disable()` automatically whenever `panel->backlight` is set —
  which is how this design gets DPMS-cycle persistence for free by
  assigning `ctx->panel.backlight` instead of inventing a second code path.
- LILYGO's own patch, `0049-drm-panel-canaan-universal-add-rm69a10-dsi-backlight.patch`
  (cited, not fetched — see the inventory's provenance discussion of why a
  LILYGO `k230_bsp` citation counts as tier-2 grounding here), independently
  confirms the same three DT property names
  (`canaan,dsi-command-backlight`, `default-brightness`, `max-brightness`)
  and the same DCS command. This design's C differs in structure (adapted
  to this driver's current shape, using the mainline
  `devm_backlight_device_register` idiom above) but the DT contract and the
  wire command match.

## Goals / Non-Goals

**Goals:** a real `/sys/class/backlight/<dev>` with a correct
`max_brightness`; writing `brightness` changes what the panel shows;
brightness set once survives a later modeset or DPMS cycle; the existing
Settings stepper drives it end to end; the default at boot matches today's
fixed value so a plain image looks unchanged.

**Non-Goals:** redesigning the stepper into a slider (explicitly deferred by
the design review already on file); PWM or GPIO-based backlight dimming
(this panel's backlight gate is a hard on/off enable line, not a PWM —
brightness is purely a DSI command to the panel controller itself);
ambient-light auto-brightness; ramping/animation on brightness changes.

## Decisions

1. **A DSI-command backlight, not a GPIO/PWM one.** GPIO25
   (`backlight_gpio`) stays exactly what it is today — an enable gate driven
   once at probe/unprepare. Brightness itself is a DCS write to the RM69A10
   controller, which is what the fixed `0xFE` in `panel-init-sequence`
   already proves works. Rejected: adding a `pwm-backlight` node — nothing
   on this board's schematic wires the backlight gate to a PWM channel
   (`docs/dts-evidence.md`; only `GPIO25`, plain on/off), and the inventory
   found no PWM consumer for this panel at all.
2. **The backlight is created only when `canaan,dsi-command-backlight` is
   present in the device tree**, defaulting to disabled. This keeps a board
   `.dts` that does not opt in — including, hypothetically, some other
   `canaan,universal` panel this driver might later serve — on exactly
   today's fixed-brightness behavior. Our own `display-rm69a10-568x1232.dtsi`
   sets the property, since this is the one and only panel this repository
   drives.
3. **`default-brightness` defaults to `0xFE` (254) and `max-brightness` to
   255**, matching the fixed value already baked into
   `panel-init-sequence` and the DCS command's 8-bit range. A fresh image
   therefore reports ~100% and looks identical to before this change; the
   first person to move the stepper is the first brightness change that
   has ever happened on this board.
4. **Persistence is `ctx->panel.backlight`, not a second manual reapply
   path.** Setting the panel's `backlight` field makes `drm_panel_enable()`/
   `drm_panel_disable()` — already called by `canaan_dsi.c`'s encoder
   enable/disable path on every modeset — call `backlight_enable()`/
   `backlight_disable()` automatically, which calls back into this driver's
   `update_status` with the last brightness core state (`.brightness` field
   held on the `backlight_device`, independent of DRM). Because `enable()`
   runs after `prepare()` (which re-runs the full DCS init sequence,
   including the hardcoded `0xFE`), the automatic post-enable
   `update_status` call is what overwrites that fixed value back to
   whatever was actually requested — this is the mechanism that closes the
   inventory's "must survive a modeset" gap, not a bespoke one. Rejected: a
   hand-rolled reapply inside `canaan_panel_prepare()` itself, which would
   duplicate logic `drm_panel.c` already provides and run before the panel
   is confirmed enabled.
5. **`update_status` no-ops while the panel is not `prepared`.** A
   `bool prepared` field, set at the tail of `prepare()` and cleared at the
   head of `unprepare()`, guards every DSI write from the backlight path.
   Without it, a brightness write arriving while the panel is mid-reset (or
   before the first modeset) would attempt a DSI transaction against a
   controller not currently listening — exactly the class of hang this
   kernel's postPatch history (bounded PHY waits, bounded thermal loop) has
   already had to fix elsewhere. Rejected: writing unconditionally and
   trusting DSI transaction timeouts — this driver's own DSI writes already
   log `-110` (ETIMEDOUT) in the unpowered-domain case recorded in
   `nix/kernel.nix`; a guard is cheaper than another timeout.
6. **Brightness is read back from the cached class-device value, not a DCS
   read.** `get_brightness` is left unset (the backlight core then returns
   `bl->props.brightness` directly) rather than issuing
   `mipi_dsi_dcs_get_display_brightness()` (0x52). This DCS-read path is
   new and unproven on this panel — only RDDID (0x04) and RDDPM (0x0A) have
   been read back successfully so far (`docs/evidence/panel-dark.md`) — and
   a shadow value the driver itself wrote is already authoritative for this
   single-writer device. Rejected: trusting a fresh 0x52 read, which would
   add an unverified DSI transaction to every `cat brightness`.
7. **Shell write access is a udev rule, the cheapest of the three options
   the working agreement names (a udev rule, a group, or a helper-daemon
   broker).** `tools/device_settings.py` already runs as the unprivileged
   `shell` user (spawned directly by the Rust shell client, no `sudo`) and
   already implements the full sysfs read/write path generically
   (`Settings.backlight()`/`Settings.change_brightness()` in
   `tools/device_settings.py`, unchanged by this proposal) — the only gap is
   that `/sys/class/backlight/*/brightness` is root-only by default. A
   udev rule (`SUBSYSTEM=="backlight"`, chgrp/chmod to the existing `shell`
   group already defined in `nix/shell.nix`) is the narrowest fix. Rejected:
   a new broker daemon (`vglite-access/broker.py`'s pattern) — that
   machinery exists because a private GPU descriptor must go to exactly one
   compositor `MainPID` under a security policy; a world-readable brightness
   percentage on a single-user handheld has no comparable secret or
   contention to broker.

## Risks / Trade-offs

- [A brightness write while the panel is unprepared silently does nothing]
  → guarded, logged (`dev_err`) rather than silently dropped, and the
  cached class-device value is reapplied at the next real `enable()`
  regardless — no user-visible action is lost, only deferred.
- [The `0x24` `WRITE_CONTROL_DISPLAY` value (BCTRL|DD|BL) is a mainline
  convention borrowed from other MIPI panels, not confirmed against this
  exact controller's application note] → this is exactly the class of
  "measured, not assumed" risk `docs/dts-evidence.md`'s history warns about;
  the physical board test at 10/50/100% is the actual gate, and if the
  panel does not respond as expected the fallback is the existing fixed
  `0xFE` behavior (this change is purely additive to the init sequence, not
  a replacement of it).
- [Reset-pulse prerequisite touches the same `canaan_panel_prepare()`
  function already carrying several UNVERIFIED bring-up hypotheses in
  `nix/kernel.nix`] → the reset block already exists in `prepare()` (see
  `nix/kernel.nix`'s already-landed reset-pulse postPatch, applied for the
  DSI-hang bring-up work); this change does not need to add it again, only
  confirm it is present before adding backlight code after it, so the
  panel is not mid-reset when the init sequence (and the brightness
  override that follows it) runs.

## Migration Plan

Add the backlight class device, DT properties and udev rule; no existing
behavior changes for a boot that does not touch the stepper. Cross-build
the kernel and the full system closure in the foreground. A board install
(`/boot` update, not just activation — this is a kernel and DT change) and
reboot are required before any board proof. Rollback is reverting this
commit; the fixed `0xFE` brightness is the starting point either way.
