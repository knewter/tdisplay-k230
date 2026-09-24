## Why

A person cannot currently clone an Omarchy theme and use its complete appearance on the handheld. Hardcoded colors and independently styled clients would make the proposed card shell inconsistent and force theme authors to maintain a second format.

## What Changes

- Select an unchanged theme checkout directly: either a community repository root or a member of Omarchy's built-in `themes/` collection. No conversion, fork, manifest injection, or edits inside the checkout are required.
- Reuse pinned upstream palette, template, and terminal color helpers and the established theme-swap interface, adding a small Nix/Sway shell adapter instead of creating a competing theme format or resolver.
- Read the current Quattro palette, legacy aliases, derived colors, full shell and section overrides, gradients, alpha, borders, control states, typography, spacing, icon-theme choice, and background assets through a shared compatibility layer.
- Apply one theme generation across cards, drawer, Settings, notifications, keyboard, and installed app appearance adapters. Preserve the handheld's webOS-inspired navigation and touch target constraints.
- Offer touch previews and selection for themes and all their background choices; remember each theme's wallpaper, support user background overlays, and retain a recoverable default. Include bounded video-background playback as a separately measured implementation group.
- Keep source repositories read-only. Generate adapters and caches elsewhere, refresh after upstream updates, and package pinned defaults declaratively in Nix for fresh homes.
- Report every consumed, adapted, unavailable, or unknown setting. Full support for our corresponding surfaces is the acceptance target; a palette-only importer or silent omission does not satisfy it.

**Non-goals:** Installing Omarchy/Arch, replacing Sway with Hyprland/Quickshell, executing theme scripts or Lua, adopting Omarchy's desktop navigation, adding a lock screen, RGB keyboard hardware or haptics, promising themes for apps we do not ship, or claiming every arbitrary video codec runs smoothly on this board. Absent surfaces and hardware remain explicit in the compatibility report, with their data preserved.

## Capabilities

### New Capabilities

- `runtime/shell-themes`: unchanged Omarchy theme sources, complete appearance resolution, coordinated activation, background selection, reproducible defaults, and honest compatibility reporting.

### Modified Capabilities

None. This adds appearance behavior without changing the existing shell navigation or sibling card/design contracts.

## Impact

Userspace theme loader and adapters, launcher icon resolution, card renderer tokens, settings/notification clients, keyboard/app configuration, wallpaper lifecycle, Nix defaults, and later feature evidence. The pinned upstream survey is in `docs/research/omarchy-quattro-theme-compatibility.md`. Parser, fixture, rendering, and failure tests can run on the host; cross-builds use the existing sole build slot. Readability, touch selection, motion cost, reboot persistence, and recovery require the reserved physical board. This proposal ships no theme implementation and proves no board behavior.
