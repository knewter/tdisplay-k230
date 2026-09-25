## ADDED Requirements

### Requirement: A bottom-edge gesture reaches the overview from any transient surface

<!-- Grounded: nix/card-shell/adapter.c input_down (the drawer_mapped()
bottom-edge carve-out), nix/card-shell/route.c card_shell_launch_surface's
"hide" surface, nix/rust-shell-client/src/lib.rs Route::Hide (pre-existing).
Host command: `cargo test --manifest-path nix/rust-shell-client/Cargo.toml
--locked`. QEMU injected-touch command:
`python3 tests/test_rust_overlay_bottom_escape_runtime.py --sway <sway>
--rust <k230-shell-rust> --client <card-composition-probe-client> --output
<dir>`; see docs/evidence/coherent-shell/overlay-bottom-escape-qemu/. -->

`docs/design/shell-ux-critique.md` S1.1 found the exact cause of "swiping up
from the bottom of Settings does nothing": `nix/card-shell/adapter.c`'s
`input_down` ceded every touch to a mapped Drawer/Shade/Settings layer-shell
overlay (`drawer_mapped()`) before the compositor's own bottom-edge
recognizer (`cs_begin_entry`/`cs_edge_down`) ever ran, regardless of where on
the screen the touch started. This requirement is this change's fix for that
finding, and for `the-handheld-presents-a-coherent-shell`'s own "Home is the
live card deck" requirement's "from an app or transient surface" clause,
which this same defect left unimplemented for every transient surface.

While the Drawer, Shade, Settings, or any Settings sub-page (theme chooser,
Wi-Fi, password entry) is mapped, a touch that begins within the same
qualified bottom edge band an ordinary app already honors SHALL be claimed by
the compositor's existing bottom-edge recognizer instead of being forwarded
to the overlay, using the same thresholds and feel as from an app: a purely
upward release SHALL reach the card overview, and a qualified sideways
release (directly, or continued from an upward start without lifting) SHALL
switch directly to the adjacent running app, per `the-handheld-presents-a-
coherent-shell` design decision 11/12's already-approved two-axis mechanics,
which this requirement reuses unchanged. The overlay SHALL be dismissed as
part of claiming the gesture, so the person is never left with the overlay
still covering the destination it just navigated to. A touch that begins
outside that qualified band — including the overlay's own top-area controls
— SHALL continue to reach the overlay exactly as before.

Because this claims the gesture at the compositor's touch-routing layer
rather than inside the overlay's own page/route state, it applies uniformly
regardless of which Settings sub-page is showing, closing
`shell-ux-critique.md` S2's "dead ends three levels deep" finding (Shade →
Settings → Wi-Fi → password entry) without a separate per-page fix: the
bottom edge reaches the overview from any depth.

#### Scenario: Swipe up from Settings over a running app

- **WHEN** a person swipes up from the bottom edge while Settings (including
  a sub-page such as the theme chooser or Wi-Fi) is open over a running app
- **THEN** the app shrinks into the card overview exactly as an unmediated
  swipe up from that app would, and Settings is no longer covering the
  screen

#### Scenario: Swipe sideways from an overlay switches apps

- **WHEN** a person performs a qualified bottom-edge sideways swipe (direct,
  or curved from an upward start) while the Drawer, Shade, or Settings is
  mapped and two or more apps are running
- **THEN** the adjacent running app is focused and visibly raised, the same
  as the equivalent gesture performed directly on an app

#### Scenario: A deep sub-page still escapes to the overview

- **WHEN** a person has navigated from the shade into Settings and from
  there into a Wi-Fi network's password entry field
- **THEN** the same bottom-edge swipe up reaches the card overview in one
  gesture, without first backing out of the password entry and Wi-Fi list a
  level at a time

#### Scenario: A tap on the overlay's own controls is unaffected

- **WHEN** a person taps a control that is not within the qualified bottom
  edge band, such as Settings' own top-area Close control
- **THEN** the overlay's own touch handling receives the tap exactly as
  before, and no card-entry gesture is claimed by the compositor

### Requirement: Overlay dismiss gestures share one direction

<!-- Grounded: nix/rust-shell-client/src/service_ui.rs panel_intent
(Route::Shade and Route::Settings arms), OVERLAY_DISMISS_ZONE_Y/
OVERLAY_DISMISS_DY constants. Host command: `cargo test --manifest-path
nix/rust-shell-client/Cargo.toml --locked
service_ui::tests::shade_and_settings_share_one_upward_dismiss_direction`.
Drawer (nix/rust-shell-client/src/navigation.rs) is unchanged; see this
requirement's rationale for why. -->

`docs/design/shell-ux-critique.md` S2 found three overlay surfaces each
recognizing a different, independently hand-tuned local dismiss gesture —
Drawer on a downward drag, Shade on an upward drag, and Settings on a
downward drag despite opening from within the shade's own downward path —
with no single stated rule governing any of them.

Each top-anchored overlay sheet's own local dismiss gesture (distinct from
the bottom-edge escape above, and from a tap on an explicit close control)
SHALL retract the sheet back toward the edge it opened from. Shade and
Settings SHALL therefore share one identical rule: an upward drag starting
near the top of the sheet dismisses it, using the same start-position zone
and displacement threshold for both. The Drawer, which rises from the bottom
edge instead, correctly keeps its own reversed convention — a downward drag
once its content is scrolled to the top sends it back toward the bottom edge
it rose from, an overscroll-to-dismiss idiom that does not conflict with
scrolling the drawer's own content — and is unchanged by this requirement.

#### Scenario: Settings dismisses the same way Shade does

- **WHEN** a person drags upward from near the top of Settings, the same
  gesture that already dismisses the Shade
- **THEN** Settings is dismissed identically; a downward drag in the same
  zone no longer dismisses it

#### Scenario: The Drawer keeps its own bottom-anchored convention

- **WHEN** a person, with the Drawer's content already scrolled to the top,
  drags downward
- **THEN** the Drawer is dismissed back toward the bottom edge it rose from,
  unchanged by this requirement
