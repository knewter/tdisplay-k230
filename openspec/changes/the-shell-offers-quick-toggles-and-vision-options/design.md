## Context

This is a scope split of `the-shell-behaves-as-one-coherent-system`. Its
decisions 2 and 3 and the open question below are carried over unchanged.
The implementation layer is userspace: the Rust shell client and the
card-shell C renderer. The Nix layer changes only if a new persisted default
is needed.

Current code, read on `master` `38c264e4`:

- The `Route::Shade` render (`nix/rust-shell-client/src/render.rs`, from about
  line 1717) paints notifications, "Dismiss all", the Settings entry and a
  brightness slider. It has no keyboard control. The `Route::Shade` arm of
  `panel_intent` (`service_ui.rs`, about lines 652-693) hit-tests scroll,
  item actions, "Dismiss all" (`116.0..190.0`, 74 px) and Settings.
- `KeyboardToggle` is sent only from `Route::Settings`
  (`service_ui.rs`, about lines 733-737).
- Nothing under `nix/` matches `text_scale`, `high_contrast` or
  `accessibility`. `settings.motion` (reduced motion) is a separate control.

## Decisions

1. **Shade toggles reuse existing request types** (parent decision 2). The
   shade sends the same `ServiceRequest::KeyboardToggle` that Settings sends
   and gates on the same `ControlState`. A shade-only state model was rejected
   because it would duplicate the unavailable/read-only/pending semantics.
2. **The existing slider provides brightness.** The shade slider from
   `the-brightness-control-is-a-slider` already sends the brightness request
   under the same `ControlState`. A second stepper control was rejected
   because it would duplicate one control in one sheet.
3. **The tap floor applies to hit regions, not glyphs.** Labels may stay
   visually small. Only hit regions grow, and they must not overlap. If the
   slider band, "Dismiss all" and the new toggle cannot all get 99 px regions
   without overlap, the shade layout moves down rather than shrinking any
   region.
4. **Scale and contrast use the existing theme-token path** (parent decision
   3), so that card headers follow as well as Rust surfaces. A Rust-only
   mechanism was rejected because it would repeat the font divergence recorded
   in `docs/design/webos-polish-review.md` P1-1.

## Risks

- Moving shade regions can break tests that assume the current layout. Rerun
  the full `cargo test` suite.
- High contrast may conflict with community theme colors. The override has to
  apply after the active theme's tokens are loaded.

## Open Questions

- Should the text scale have more than two steps? The requirement says "at
  least two", and a wider range needs no spec change.
