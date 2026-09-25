## Why

The operator asked directly for a ruthless UX critique of this shell against
webOS and Android Material 3 Expressive, naming three examples: the card
switcher shows one card at a time, cards carry no icons, and swiping up from
the bottom of Settings does nothing. `docs/design/shell-ux-critique.md`
(this change's companion document) traces all three to exact code and finds
15 ranked findings in total.

Most of what that critique found is **not** new scope. Two of the user's
three examples — the Settings swipe-up dead end and the missing card icon —
are already fully specified by the open, unarchived
`the-handheld-presents-a-coherent-shell` change (`runtime/handheld-shell-design`
requirements "Shade and contextual Back preserve the task" and "Installed
application icons retain identity and privacy") with matching tasks (2.2,
4.4, and 1.4) still `[ ]` open. Several more findings duplicate
`docs/design/webos-polish-review.md`'s already-filed P0-1/P0-2/P0-4/P1-1/
P1-2/P1-4. This change does not repeat any of that spec text or re-open
those tasks; it names them and stops.

What is left over — confirmed by grep across every open change's
`proposal.md`/`design.md` (`shell-ux-critique.md` §5/§10 records the exact
searches) — is three findings that genuinely have no owner:

1. **The card overview's neighbor peek is too thin to identify what's
   open**, even once the switcher's icon and title bugs are fixed. The
   deck's own geometry (`card-shell-policy.c:31-32,192-210`) shows roughly
   8.7% of a card's width at each edge — a color swatch, not an identifiable
   neighbor. `the-handheld-presents-a-coherent-shell`'s "Bottom app switching
   follows both touch axes" requirement governs the *drag* gesture's feel
   ("a full or near-full app carousel"), a deliberate choice recorded in its
   `design.md` decision 11; it does not claim anything about the *released,
   idle* deck's legibility, and nothing else does either.
2. **The notification shade has no quick-toggle tiles.** Brightness and
   keyboard-visibility toggles exist only one full navigation hop away,
   inside Settings; the shade itself offers only notification actions,
   dismiss-all, and a Settings entry point. Neither webOS's tap-the-status-
   bar menu nor Android's Quick Settings requires that hop for its
   highest-frequency toggles.
3. **There is no vision-accessibility option** (adjustable text size or a
   high-contrast variant) anywhere in the shell — only a binary
   reduced-motion flag. The coherent-shell change's planned "accessibility
   aid" (task 1.5) is a different thing: large labeled buttons as an
   alternative to swipe gestures, not a reading/contrast accommodation.

This change turns those three, and only those three, into requirements.

## What Changes

- **Deck legibility**: widen the card overview's neighbor peek so an
  adjacent card's icon badge is identifiable without paging to it, replacing
  the current ~8.7%-of-card-width sliver. Independent of, and a prerequisite
  for maximum value from, `the-handheld-presents-a-coherent-shell` task 1.4
  (real card icons) — a legible icon needs enough peek width to show it.
- **Shade quick toggles**: add a small row of at-a-glance capability toggles
  (brightness step, keyboard show/hide, and any other Settings capability
  already exposed as a single-tap action) to the notification shade itself,
  reachable without opening Settings, following the existing
  `ServiceRequest`/`PanelIntent` plumbing already used for these same actions
  inside Settings.
- **Vision accessibility option**: add a Settings-level text-scale and
  high-contrast choice, applied through the existing theme-token pipeline
  (the same mechanism that already carries per-theme colors from Rust to the
  C compositor), distinct from and in addition to the already-planned
  gesture-discovery accessibility aid.

## Capabilities

### New Capabilities

None. All three requirements are `ADDED` to capabilities other open changes
already introduce (`runtime/card-shell`, `runtime/notification-center`,
`runtime/device-settings`); none of those capabilities is archived yet, so
each `ADDED` requirement here is additive to those changes' own deltas, the
same pattern `the-shell-loads-omarchy-themes` and
`the-shell-swaps-themes-without-a-python-stall` already use for
`runtime/shell-themes`.

### Modified Capabilities

None.

### Explicitly out of scope (routed elsewhere, not touched here)

- Settings/Drawer/Shade not responding to the shell's bottom-edge or a
  consistent Back gesture → `the-handheld-presents-a-coherent-shell` tasks
  2.2 and 4.4.
- Card headers/switcher not showing a real app icon → same change, task 1.4.
- Card header showing a raw, live-changing window title →
  `docs/design/webos-polish-review.md` P0-1 (not an OpenSpec change; a
  correction against currently shipped code with no open proposal of its
  own — a future change may be needed to formalize it, which is outside
  this proposal's scope).
- Full-height empty panels, uneven Settings row spacing, font
  inconsistency, permanent (not first-use-only) gesture hints, the
  "1 notifications" string → `docs/design/webos-polish-review.md`
  P0-2/P0-4/P1-1/P1-2/P1-4, same as above.
- Linear (non-spring) card expand/collapse motion, and the missing
  card-switcher/drawer/Settings frame-latency measurement → recorded as
  recommended follow-up tasks in `shell-ux-critique.md` §6/§11, routed to
  `the-handheld-presents-a-coherent-shell` task 4.5's existing scope; not
  new requirements here.
- Reopening the recorded "search remains deferred" decision
  (`the-handheld-presents-a-coherent-shell/design.md` decision 2) — flagged
  as a recommendation for the coordinator in `shell-ux-critique.md` §4, not
  acted on here without explicit authorization to reverse a recorded
  rejection.
- A distinct, deliberately-entered multi-card grid "Overview" mode
  (considered in `design.md` decision 1 as an alternative to widening the
  existing deck's peek, and set aside here as too large a single slice —
  illustrated only as one option in `docs/design/shell-ux-critique-switcher.svg`,
  not committed).

## Impact

Userspace only, split across the two existing shell processes:

- Deck legibility touches `nix/card-shell-policy/card-shell-policy.c`
  (`cs_default_config`, the deck layout math) and `nix/card-shell/adapter.c`/
  `render.c` (badge/label sizing at the new peek width). No device tree,
  kernel, boot, radio, or second-core change.
- Shade quick toggles touch `nix/rust-shell-client/src/service_ui.rs`
  (`panel_intent`'s `Route::Shade` arm) and `render.rs` (Shade painting) only;
  reuses the existing `ServiceRequest::Brightness`/`KeyboardToggle` request
  types already wired to `service_data.rs`, so no new IPC surface is needed.
- The accessibility option touches Settings' Rust rendering/state
  (`service_data.rs`, `render.rs`) and the theme-token pipeline shared with
  `nix/card-shell/render.c`, so both renderers pick up the chosen scale/
  contrast consistently — the same cross-renderer consistency gap
  `webos-polish-review.md` P1-1 already flags for fonts generally.

Host model tests (`cargo test --manifest-path nix/rust-shell-client/Cargo.toml
--locked`, the existing `tests/test_card_shell_state.py` /
`test_card_shell_gestures.py` C fixtures) and narrow `nix build` derivation
proofs can all proceed without the board, per each task group below. Real-
finger legibility (is the new peek width actually readable at arm's length;
does the new accessibility text scale actually help), touch-target size for
the new shade toggles, and on-glass contrast checking are physical
acceptance gates that remain open and unverified until a board reservation
records them, consistent with every sibling change's own evidence
discipline.

This proposal makes **no source changes**; it is planning only, produced
under `AGENTS.md`'s instruction that several other agents are concurrently
editing the compositor and the Rust shell. Implementation is a separate,
later, authorized step.
