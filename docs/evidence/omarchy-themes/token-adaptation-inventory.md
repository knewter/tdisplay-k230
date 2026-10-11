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
| `controls.normal-fill-alpha` | applied | Rust control-card renderer; state outlines retain gradients, alpha and per-side widths. |
| `controls.normal-border` | unavailable | Ordinary row rims are deliberately omitted. |
| `controls.normal-border-width` | unavailable | Ordinary row rims are deliberately omitted. |
| `controls.normal-border-alpha` | unavailable | Ordinary row rims are deliberately omitted. |
| `controls.hover-cursor-color` | applied | Mouse hover on existing Home/drawer/control chrome; it never activates a control. |
| `controls.hover-cursor-fill-alpha` | applied | Mouse hover on existing Home/drawer/control chrome; it never activates a control. |
| `controls.hover-cursor-border` | applied | Mouse hover on existing Home/drawer/control chrome; it never activates a control. |
| `controls.hover-cursor-border-width` | applied | Mouse hover on existing Home/drawer/control chrome; it never activates a control. |
| `controls.hover-cursor-border-alpha` | applied | Mouse hover on existing Home/drawer/control chrome; it never activates a control. |
| `controls.focus-color` | applied | Existing drawer search, Wi-Fi password and folder-rename fields own focused chrome. |
| `controls.focus-fill-alpha` | applied | Existing drawer search, Wi-Fi password and folder-rename fields own focused chrome. |
| `controls.focus-border` | applied | Existing drawer search, Wi-Fi password and folder-rename fields own focused chrome. |
| `controls.focus-border-width` | applied | Existing drawer search, Wi-Fi password and folder-rename fields own focused chrome. |
| `controls.focus-border-alpha` | applied | Existing drawer search, Wi-Fi password and folder-rename fields own focused chrome. |
| `controls.selected-color` | applied | Rust control-card renderer; state outlines retain gradients, alpha and per-side widths. |
| `controls.selected-fill-alpha` | applied | Rust control-card renderer; state outlines retain gradients, alpha and per-side widths. |
| `controls.selected-border` | applied | Rust control-card renderer; state outlines retain gradients, alpha and per-side widths. |
| `controls.selected-border-width` | applied | Rust control-card renderer; state outlines retain gradients, alpha and per-side widths. |
| `controls.selected-border-alpha` | applied | Rust control-card renderer; state outlines retain gradients, alpha and per-side widths. |
| `controls.pressed-fill-alpha` | applied | Rust Home icon/folder transient press uses this fill without persistent selection. |
| `controls.selection-fill-alpha` | unavailable | Text-selection paint belongs to the input client, not these cards. |
| `spacing.scale` | adapted | Shared visual text insets, Home/drawer label gaps, widget padding and C header icon gaps scale within 0.8–1.25; Settings padding is 12–36px. Hit/panel geometry stays fixed. |
| `spacing.scale-with-font` | adapted | When true (default), visual spacing multiplies scale by base-size/12 before the handheld bounds; false decouples font and spacing. |
| `font.base-size` | adapted | Rust shell labels and C deck headers scale by base-size/12, bounded to 0.8–1.25; Settings role overrides retain 11–24px bounds. |
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
| `launcher.scrim` | applied | Home folder and widget-picker scrim brush. |
| `launcher.scrim-alpha` | applied | Home folder and widget-picker scrim brush. |
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
| `menu.scrim` | applied | App-actions overlay scrim brush. |
| `menu.scrim-alpha` | applied | Compiled into the app-actions scrim brush. |
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
| `image-picker.scrim` | applied | Chooser slice dimming consumes the image-picker scrim brush. |
| `image-picker.scrim-alpha` | adapted | Authored scrim alpha is multiplied by the existing per-slice blend; a centered slice is undimmed. |
| `image-picker.text` | adapted | Chooser glyphs use the first brush stop. |
| `image-picker.selected-border` | unavailable | Chooser carousel does not paint selection outlines. |
| `image-picker.selected-border-alpha` | unavailable | Chooser carousel does not paint selection outlines. |
| `image-picker.unselected-border` | unavailable | Chooser carousel does not paint slice outlines. |
| `image-picker.unselected-border-alpha` | unavailable | Chooser carousel does not paint slice outlines. |

The test `python3 tests/test_handheld_theme_rendering.py` checks that the
inventory covers every active key and has no unknown classifications.
Renderer unit tests verify the actual Rust Cairo/Pango path for the
hover/focus state, bounded font/spacing adaptation and Home's momentary pressed fill.
Idle outlines, text selection and absent surfaces are explicitly unavailable; they
are not new surfaces or interaction modes introduced by appearance import.
New physical recordings and numerical measurements are waived by the operator;
specific unobserved glass/boot cases and unmeasured costs remain UNVERIFIED.
