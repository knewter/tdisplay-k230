## Why

The handheld's Editor currently opens Nano in a terminal. The user wants
Omawrite as the writing/editing app accessible from Home and All apps.

## What Changes

- Package pinned upstream Omawrite from source for the RISC-V image.
- Make the existing Editor desktop-entry identity launch Omawrite, with its
  icon and text/Markdown file associations, preserving existing Home pins.
- Adapt the desktop minimum width and file dialogs to the portrait panel;
  select Qt Quick software rendering on Wayland for this app.
- Verify launch, typing, save/reopen, keyboard and window navigation on the
  physical board before selecting the new image persistently.

Non-goals: replacing the Rust shell with Qt/Quickshell, claiming general Qt
performance acceptance, GPU enablement, print setup, or removing the CLI
recovery editor. No kernel, device-tree or bootloader change is intended.

## Capabilities

### New Capabilities

- `runtime/editor`: the image's graphical editor opens Omawrite and supports
  local text/Markdown editing on the handheld.

### Modified Capabilities

None.

## Impact

Nix package and shell desktop/MIME configuration, bounded portrait/dialog
adaptations to pinned upstream source, focused launch/edit validation, and
committed evidence. A reserved board is required for device acceptance;
source/package preparation can proceed without it. The separate general
Qt Quick/Quickshell evaluation proposal remains open.
