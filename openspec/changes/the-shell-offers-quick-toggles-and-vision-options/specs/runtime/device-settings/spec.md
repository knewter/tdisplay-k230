## ADDED Requirements

### Requirement: Settings offers a vision-accessibility text scale and high-contrast option

<!-- UNVERIFIED: planning only; no implementation, host render, or board
observation exists yet. Grounding for the gap being closed: a search of
nix/rust-shell-client/src/*.rs for "accessib", "a11y", "contrast",
"large_text", and "screen reader" against origin/master 80817e3d returns no
hits; the only related mechanism found is a single boolean
reduced_motion flag (main.rs:3344-3345, K230_SETTINGS_REDUCED_MOTION),
which shortens animation durations and does not affect text size or
contrast. the-handheld-presents-a-coherent-shell/design.md decision 2 plans
a separate "accessibility aid" (task 1.5) that is explicitly large labeled
route controls as a swipe-gesture alternative, not a text-scale or contrast
accommodation; this requirement is additive to, not a restatement of, that
one. -->

*Grounding (2026-10-16): the first implementation offered one larger step
(1.25x). On the panel (568x1232 at 4.1", about 331 ppi, 2.07 px per dp) the
default body text is 17-18 px (about 8.5 sp) and drawer labels are 14 px
(about 6.8 sp), roughly half of common phone defaults. The 1.25x step left the
drawer illegible to the operator: "the drawer is not particularly legible at
'large' text", with labels ellipsized ("Same G…") over a translucent drawer
that shows the Home clock and wallpaper through it
(`docs/evidence/coherent-shell/accessibility-scale/board/11-panel-drawer.png`).*

Settings SHALL offer a person four text-size steps, 100%, 130%, 160% and 200%
of the shell's design size, and a high-contrast palette variant. Both choices
are independent of the theme currently active and of the existing
reduced-motion toggle. The 200% step follows WCAG 1.4.4 (resize text). At
every step, text SHALL reflow rather than be cut off: drawer labels wrap to
at most two lines and the drawer uses fewer columns, and Settings and Shade
cards grow to fit their text. A label is ellipsized only when it would
exceed two lines at the chosen size. With any vision option other than the
defaults, the drawer and Shade SHALL draw their text over an opaque surface,
not a translucent one that shows Home through it, and app icons and their
tap targets SHALL grow with the step up to at least 48 dp (99 px on this
panel).

The chosen scale and contrast variant SHALL apply consistently to both the
Rust-rendered surfaces (Home, drawer, shade, Settings) and the C-rendered card
deck and its labels, using the same shared theme-token mechanism that already
carries per-theme colors across that boundary, so a person does not get a
larger Settings but an unchanged card header. The choice SHALL persist across
restarts the same way the active theme choice already does.

#### Scenario: A person chooses a larger text size

- **WHEN** a person selects the 130%, 160% or 200% text-size step in Settings
- **THEN** text on Home, the drawer, the shade, Settings, and card headers
  all render at that size, not only the Settings screen itself

#### Scenario: The largest step keeps every drawer label readable

- **WHEN** the 200% step is active and the drawer is open on the panel in
  either orientation
- **THEN** every app label is shown whole on at most two lines over an opaque
  surface, with no label crossing a neighbouring tile and no icon or tap
  target smaller than 99 px

#### Scenario: A person chooses the high-contrast variant

- **WHEN** a person selects the high-contrast variant
- **THEN** the active theme's colors are overridden by the high-contrast
  palette consistently across both renderers, and the choice survives a
  reboot the same way an active theme choice does

#### Scenario: The choice is independent of other accessibility controls

- **WHEN** a person has reduced motion enabled, disabled, or has opened the
  separately planned gesture-discovery accessibility aid
- **THEN** the text-scale and high-contrast choice is unaffected by, and
  does not affect, either of those settings
