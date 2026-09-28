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

Settings SHALL offer a person a choice of at least two text-scale steps
(the current default and one larger step) and a high-contrast palette
variant, independent of the theme currently active and independent of the
existing reduced-motion toggle. The chosen scale and contrast variant SHALL
apply consistently to both the Rust-rendered surfaces (Home, drawer, shade,
Settings) and the C-rendered card deck and its labels, using the same
shared theme-token mechanism that already carries per-theme colors across
that boundary, so a person does not get a larger Settings but an unchanged
card header. The choice SHALL persist across restarts the same way the
active theme choice already does.

#### Scenario: A person chooses the larger text scale

- **WHEN** a person selects the larger text-scale step in Settings
- **THEN** text on Home, the drawer, the shade, Settings, and card headers
  all render at the larger scale, not only the Settings screen itself

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
