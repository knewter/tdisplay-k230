## Why

To change the keyboard, a person has to open the notification shade, enter
Settings and find the right row. No Settings option makes text larger or raises
contrast; the only accessibility setting shortens motion. The shade's
"Dismiss all" target is 74 logical px tall, about 36dp at this panel's
density, so it is easy to miss.

`the-shell-behaves-as-one-coherent-system` planned these as slices B and C,
plus a shade tap-target requirement that no task tracked. That change's slices A
(webOS-fan overview) and E (bottom-edge overlay escape) are implemented and
have host/QEMU proof. B and C have no code yet. This **scope-split successor**
keeps every B and C requirement and task, so the parent can close once its A
and E board gates pass.

**Status: staged, not authorized.** The parent's task D.3 requires explicit
coordinator/user authorization for this split. Until it is given, the parent
still owns these requirements. When the split is authorized, remove the parent's
slice B/C requirements and tasks in the same commit that makes this change
active, so neither change is archived with the other's requirements.

## What Changes

- **Shade quick toggles** (parent slice B): add a keyboard show/hide toggle to
  the notification shade. Its state and request come from Settings'
  `ControlState`/`ServiceRequest`, and an unavailable state looks the same as in
  Settings. The brightness half of the original requirement is now met by the
  shade's brightness slider from `the-brightness-control-is-a-slider`
  (`nix/rust-shell-client/src/service_ui.rs` `SHADE_SLIDER_TOP`). This
  change keeps that scenario but does not add a second brightness control. Its
  on-glass proof stays with that change's own task 6.2.
- **Shade tap-target floor** (parent `notification-center` requirement with no
  task): every shade tap target, including "Dismiss all", gets a
  48dp-equivalent (about 99 logical px) hit region.
- **Vision accessibility option** (parent slice C): Settings offers a
  text-scale step and a high-contrast palette. The choice persists like the
  theme choice and applies to both the Rust surfaces and the C card headers
  through the shared theme-token path.

## Non-goals

- Anything in the parent's slices A and E, and the general side-edge
  contextual Back gesture (`the-handheld-presents-a-coherent-shell` tasks
  2.2/4.4).
- The gesture-discovery accessibility aid (large labeled route controls),
  which is `the-handheld-presents-a-coherent-shell` task 1.5.
- A second brightness control in the shade, or changing the slider's
  behavior.
- Screen-reader support, per-app scaling and battery/haptics.

## Board need

The host work (Rust unit tests, `nix build .#card-shell`, host renders) needs
no board. Reachability, legibility and persistence across a reboot on the real
panel each need a reserved board and a real finger (tasks B.4, C.4).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. The requirements are `ADDED` to `runtime/notification-center` and
`runtime/device-settings`, which `the-handheld-presents-a-coherent-shell`
introduces and which do not yet exist under `openspec/specs/`. The parent
used the same additive pattern.

## Impact

Userspace only: `nix/rust-shell-client/src/{render.rs,service_ui.rs,service_data.rs}`,
the theme-token path shared with `nix/card-shell/render.c`, and persisted
Settings state. There are no kernel, device-tree, stage-1 or radio changes.
