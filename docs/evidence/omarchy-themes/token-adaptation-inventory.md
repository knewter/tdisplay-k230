# Generated Omarchy shell-field inventory

Host source audit; this is not panel or touch acceptance. The source is
the checked-in pinned upstream template `nix/omarchy-theme-tools/upstream/default/themed/shell.toml.tpl`.
Upstream revision: `omacom/omarchy@28ceaae70ebac3a0edcc21f2faa77a90dc6d404c`.
Template SHA-256: `bdc8e76a5a9a700adaca0d2fa44a2a340584892fd507e3fcbd4f9a4843765242`.
It contains 102 active fields across 13 sections. Every active field appears below.
Commented example overrides are not active fields; themes may still add them and they remain preserved.

| Generated field | Classification | Current owner / adaptation |
| --- | --- | --- |
| `bar.background` | unavailable | No persistent bar surface exists. |
| `bar.background-alpha` | unavailable | No persistent bar surface exists. |
| `bar.text` | unavailable | No persistent bar surface exists. |
| `bar.active` | unavailable | No persistent bar surface exists. |
| `bar.scale-with-font` | unavailable | No persistent bar surface exists. |
| `bar.size-horizontal` | unavailable | No persistent bar surface exists. |
| `bar.size-vertical` | unavailable | No persistent bar surface exists. |
| `hyprland.active-border` | unavailable | Hyprland is not the handheld compositor; these tokens are retained only. |
| `hyprland.active-border-foreground` | unavailable | Hyprland is not the handheld compositor; these tokens are retained only. |
| `controls.normal-color` | adapted | Rust Settings labels use the first color stop; fills retain full brushes. |
| `controls.normal-fill-alpha` | applied | Rust control-card renderer; selected outline alpha is folded into its brush. |
| `controls.normal-border` | unavailable | Ordinary row rims are deliberately omitted. |
| `controls.normal-border-width` | unavailable | Ordinary row rims are deliberately omitted. |
| `controls.normal-border-alpha` | unavailable | Ordinary row rims are deliberately omitted. |
| `controls.hover-cursor-color` | unavailable | No distinct hover/cursor state is owned by these touch controls. |
| `controls.hover-cursor-fill-alpha` | unavailable | No distinct hover/cursor state is owned by these touch controls. |
| `controls.hover-cursor-border` | unavailable | No distinct hover/cursor state is owned by these touch controls. |
| `controls.hover-cursor-border-width` | unavailable | No distinct hover/cursor state is owned by these touch controls. |
| `controls.hover-cursor-border-alpha` | unavailable | No distinct hover/cursor state is owned by these touch controls. |
| `controls.focus-color` | unavailable | No keyboard-focus paint state is implemented for these rows. |
| `controls.focus-fill-alpha` | unavailable | No keyboard-focus paint state is implemented for these rows. |
| `controls.focus-border` | unavailable | No keyboard-focus paint state is implemented for these rows. |
| `controls.focus-border-width` | unavailable | No keyboard-focus paint state is implemented for these rows. |
| `controls.focus-border-alpha` | unavailable | No keyboard-focus paint state is implemented for these rows. |
| `controls.selected-color` | applied | Rust control-card renderer; selected outline alpha is folded into its brush. |
| `controls.selected-fill-alpha` | applied | Rust control-card renderer; selected outline alpha is folded into its brush. |
| `controls.selected-border` | applied | Rust control-card renderer; selected outline alpha is folded into its brush. |
| `controls.selected-border-width` | applied | Rust control-card renderer; selected outline alpha is folded into its brush. |
| `controls.selected-border-alpha` | applied | Rust control-card renderer; selected outline alpha is folded into its brush. |
| `controls.pressed-fill-alpha` | applied | Rust Home icon/folder transient press uses this fill without persistent selection. |
| `controls.selection-fill-alpha` | unavailable | Text-selection paint belongs to the input client, not these cards. |
| `spacing.scale` | adapted | Settings row text inset uses the scale, clamped to 12–36px; row/tap geometry stays fixed. |
| `spacing.scale-with-font` | unavailable | Font-relative spacing is not implemented. |
| `font.base-size` | adapted | Rust Settings labels scale design sizes by base-size (defaults to 12), clamped per label to 11–24px. |
| `popups.background` | unavailable | No standalone popup renderer consumes this section. |
| `popups.background-alpha` | unavailable | No standalone popup renderer consumes this section. |
| `popups.text` | unavailable | No standalone popup renderer consumes this section. |
| `popups.border` | unavailable | No standalone popup renderer consumes this section. |
| `popups.border-alpha` | unavailable | No standalone popup renderer consumes this section. |
| `tooltip.background` | unavailable | The handheld has no hover-tooltip surface. |
| `tooltip.background-alpha` | unavailable | The handheld has no hover-tooltip surface. |
| `tooltip.text` | unavailable | The handheld has no hover-tooltip surface. |
| `tooltip.border` | unavailable | The handheld has no hover-tooltip surface. |
| `tooltip.border-alpha` | unavailable | The handheld has no hover-tooltip surface. |
| `notifications.background` | applied | Rust Shade panel background brush. |
| `notifications.background-alpha` | applied | Compiled into the Shade background brush alpha. |
| `notifications.text` | adapted | Rust Shade uses the first brush stop for solid glyph color. |
| `notifications.border` | unavailable | The Shade does not paint a notification outline. |
| `notifications.border-alpha` | unavailable | The Shade does not paint a notification outline. |
| `notifications.countdown` | adapted | Rust Shade uses the first brush stop for its progress indicator. |
| `launcher.background` | applied | Rust Home and drawer surface background brush. |
| `launcher.background-alpha` | applied | Compiled into consumed Home/drawer background brushes. |
| `launcher.text` | adapted | Rust Home/drawer glyphs use the first brush stop. |
| `launcher.border` | unavailable | Home/drawer surfaces do not paint ordinary outlines. |
| `launcher.border-alpha` | unavailable | Home/drawer surfaces do not paint ordinary outlines. |
| `launcher.scrim` | unavailable | No launcher scrim role is consumed. |
| `launcher.scrim-alpha` | unavailable | No launcher scrim role is consumed. |
| `launcher.selected-background` | unavailable | No persistent selected Home card is painted. |
| `launcher.selected-background-alpha` | unavailable | No persistent selected Home card is painted. |
| `launcher.selected-text` | adapted | Rust Home/drawer accent glyphs use the first brush stop. |
| `launcher.selected-border` | unavailable | No persistent selected Home card is painted. |
| `launcher.selected-border-alpha` | unavailable | No persistent selected Home card is painted. |
| `menu.background` | applied | Rust app-actions menu background brush and Settings fallback. |
| `menu.background-alpha` | applied | Compiled into the consumed menu background brush. |
| `menu.text` | adapted | Rust app-actions glyphs use the first brush stop. |
| `menu.border` | unavailable | App-actions menu does not paint an ordinary outline. |
| `menu.border-alpha` | unavailable | App-actions menu does not paint an ordinary outline. |
| `menu.scrim` | unavailable | App-actions scrim is a fixed client color. |
| `menu.scrim-alpha` | unavailable | App-actions scrim is a fixed client alpha. |
| `menu.selected-background` | unavailable | No selected app-action card is painted. |
| `menu.selected-background-alpha` | unavailable | No selected app-action card is painted. |
| `menu.selected-text` | adapted | Rust app-actions accent glyphs use the first brush stop. |
| `menu.selected-border` | unavailable | No selected app-action card is painted. |
| `menu.selected-border-alpha` | unavailable | No selected app-action card is painted. |
| `polkit.background` | unavailable | No in-shell polkit prompt is shipped. |
| `polkit.background-alpha` | unavailable | No in-shell polkit prompt is shipped. |
| `polkit.text` | unavailable | No in-shell polkit prompt is shipped. |
| `polkit.text-error` | unavailable | No in-shell polkit prompt is shipped. |
| `polkit.border` | unavailable | No in-shell polkit prompt is shipped. |
| `polkit.border-error` | unavailable | No in-shell polkit prompt is shipped. |
| `polkit.border-alpha` | unavailable | No in-shell polkit prompt is shipped. |
| `polkit.scrim` | unavailable | No in-shell polkit prompt is shipped. |
| `polkit.scrim-alpha` | unavailable | No in-shell polkit prompt is shipped. |
| `polkit.accent` | unavailable | No in-shell polkit prompt is shipped. |
| `lock.background` | unavailable | The image has no shell-owned lock surface. |
| `lock.background-alpha` | unavailable | The image has no shell-owned lock surface. |
| `lock.text` | unavailable | The image has no shell-owned lock surface. |
| `lock.placeholder` | unavailable | The image has no shell-owned lock surface. |
| `lock.text-error` | unavailable | The image has no shell-owned lock surface. |
| `lock.border` | unavailable | The image has no shell-owned lock surface. |
| `lock.border-active` | unavailable | The image has no shell-owned lock surface. |
| `lock.border-error` | unavailable | The image has no shell-owned lock surface. |
| `lock.border-alpha` | unavailable | The image has no shell-owned lock surface. |
| `lock.selection` | unavailable | The image has no shell-owned lock surface. |
| `lock.selection-alpha` | unavailable | The image has no shell-owned lock surface. |
| `image-picker.scrim` | unavailable | Chooser slice dimming uses the palette background. |
| `image-picker.scrim-alpha` | unavailable | Chooser slice dimming uses a fixed alpha. |
| `image-picker.text` | adapted | Chooser glyphs use the first brush stop. |
| `image-picker.selected-border` | unavailable | Chooser carousel does not paint selection outlines. |
| `image-picker.selected-border-alpha` | unavailable | Chooser carousel does not paint selection outlines. |
| `image-picker.unselected-border` | unavailable | Chooser carousel does not paint slice outlines. |
| `image-picker.unselected-border-alpha` | unavailable | Chooser carousel does not paint slice outlines. |

The test `python3 tests/test_handheld_theme_rendering.py` checks that the
inventory covers every active key and has no unknown classifications.
Renderer unit tests verify the actual Rust Cairo/Pango path for the
implemented font adaptation and Home's momentary pressed fill. Hover/focus
states, theme-driven spacing outside Settings row text insets, absent surfaces, and
physical readability remain open; classifications above do not claim them.
