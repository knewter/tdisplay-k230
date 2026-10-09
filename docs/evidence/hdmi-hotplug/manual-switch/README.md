# One-shot HDMI switch

Continuation worktree `/home/jadams/tmp/k230-hdmi-continue`, branch
`codex/hdmi-mainline-continue`, original base
`edd74d1626d03770e08e328320b18118ece24508`. The operator's accepted group-7
HDMI trial is recorded separately in `../../hdmi-mainline/README.md`.
Owned implementation: `tools/display_switch.py`, `tools/device_settings.py`,
`nix/display-switch.nix`, `nix/sd-image.nix`, mainline profile wiring in
`flake.nix`, the Settings service/render/hit paths and their fixtures in
`nix/rust-shell-client`, narrow Python tests and the Settings CI step.
The change's planning/evidence and binary-inventory rows accompany them.

This uninstalled prototype wires one controller and the existing relay
for both display choices. Fresh `sdImage` adds the alternate HDMI DTB while
`force_dtb` still selects the panel. The controller checks the installed
kernel, panel DTB and system bootargs, leaves the panel payload intact,
fsyncs its restore marker before atomically selecting HDMI, remounts boot
read-only, then requests a reboot. Failed writes or a denied reboot restore
the panel selector. Linux's early restore unit restores the selector before
Sway starts and removes the marker. It cannot repair an unbootable
kernel/initrd before that unit; serial baseline recovery remains necessary
for that class of failure.

## Host checks

```sh
python3 tests/test_display_switch.py
python3 tests/test_device_settings.py
cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml --quiet
cargo clippy --offline --manifest-path nix/rust-shell-client/Cargo.toml --all-targets --message-format=short
cargo test --offline --manifest-path nix/touch-trackpad/Cargo.toml mode:: --quiet
```

Eleven boot-selector checks cover successful selection/restoration,
interruption after marker/selector writes, a denied reboot, unmatched
kernel/panel/system, missing output state, failed DTB/mount/payload writes,
invalid recovery state, and symlink rejection. Eleven Settings checks
include single-use HDMI confirmation/cancellation and bounded status parsing.
The Rust suite passes 497 cases, with one existing ignored case; the new
checks exercise typed display controls, the confirmation protocol and real
scaled hit regions at 568×1232, 800×1280 and 1920×1080. Clippy exits zero
with pre-existing warnings. Five relay mode fixtures retain direct touch
on the panel and trackpad selection on connected HDMI. These are host tests,
not physical taps or kernel boot proof.

[Render recipe](host-render.rs) uses the production `RendererCache` with
synthetic controls and the default palette. [Render metadata](host-render.json)
records its commands, dimensions, hashes and limits. Settings and confirmation
are rendered at all three sizes; no Wayland connection or board is involved.

| Size | Settings | Confirmation |
| --- | --- | --- |
| 568×1232 | [paint](host-settings-568x1232.png) | [paint](host-confirm-568x1232.png) |
| 800×1280 | [paint](host-settings-800x1280.png) | [paint](host-confirm-800x1280.png) |
| 1920×1080 | [paint](host-settings-1920x1080.png) | [paint](host-confirm-1920x1080.png) |

The extra row is optional in the protocol. Systems without the controller
retain the existing Settings layout, including the four native-size pixel
identity checks. The modal confirmation's paint and hit-test geometry share
the same output-size clamp.

## Build and board gates

The matching mainline cross-build was interrupted during uncached toolchain
dependencies when the operator questioned continuing this optional feature.
Its command and log hash are recorded in `host-checks.json`; this is not a
successful build. The real-DTB host recipe, standalone Rust Nix build, vendor
rollback regression build and board sequence have not run. Tasks 3.1–3.3
remain unchecked. This branch checkpoint is not an installed feature.
A host-rendered image is not installation or deployment evidence.

The operator has accepted the existing HDMI trial and waived a monitor
photograph. This optional prototype does not reopen that acceptance gate.
Task 3.3 stays open until its separate Settings-driven forward HDMI boot,
ordinary panel return, physical panel touch and operator observation are
recorded, if this feature is continued. Operator path: **Settings → Display → Confirm**, then an
ordinary `systemctl reboot` (or power cycle after the HDMI restore service
has run) to return to the panel. The candidate must first pass the protected
installer's matching, real-finger qualification; do not manufacture that
report from host tests or injected Sway commands.
