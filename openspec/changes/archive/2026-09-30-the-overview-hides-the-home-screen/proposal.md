## Why

A person on real glass (568x1232 K230, installed system, master `db5b0584`)
reported: "in webos/card overview mode i see black / glitching". The
coordinator's native capture of the card overview (`swaymsg card_shell
enter`, Monitor focused, Terminal open) confirmed a real defect: the Rust
Home screen's always-mapped `Layer::Bottom` surface
(`the-shell-presents-a-pinned-home-screen`) painted through the overview.
The overview's own deck canvas is deliberately transparent so a person sees
their wallpaper behind the cards (`nix/card-shell/adapter.c`'s
`shell.canvas`, in `root->layers.shell_overlay`, above every output layer);
before Home existed that transparency only ever revealed the plain
wallpaper. With Home now sitting in `Layer::Bottom` -- directly above the
wallpaper and below the overview -- the same transparency reveals Home's
grid tile and dock instead: the "Video" tile sat beside the Monitor card,
and the dock covered "Swipe up for apps".

IPC-driven `card_shell enter`/`back` alone did not reproduce dark or
glitching frames on their own account (a 30fps webcam recording of three
toggles showed none), so the coordinator asked for the animated,
finger-driven paths (bottom-edge swipe-up entry, drag/throw, swipe-up
close, tap-to-expand) to be reproduced under QEMU with per-frame capture
and root-caused. That investigation (this change's `design.md`) found that
the touch-first two-axis entry gesture (`cs_begin_entry` in
`nix/card-shell-policy/card-shell-policy.c`) folds `cs_enter`'s `CS_SHRINK`
action into its own result and only afterwards overwrites the policy mode to
`CS_ENTERING`, so `shell.active` -- and therefore the deck's transparent
canvas -- is already showing at the very first touch-down, well before any
visible drag distance. The Home bleed-through was therefore present for the
whole entry gesture and the whole settled overview, not only the single
steady-state frame the native capture happened to show, which is consistent
with a person describing it as "glitching": Home's grid and dock appearing
and disappearing as the deck animates in and out on top of it.

## What Changes

- Hide the compositor's `Layer::Bottom` scene layer (Home's only occupant)
  whenever the card overview is active, and restore it exactly when the
  overview hands the screen back — at the same two points
  (`nix/card-shell/adapter.c`'s `CS_SHRINK` handling and `restore()`) that
  already toggle `ordinary_backdrop` for the same reason, so there is no
  frame in between where both the deck and Home are visible.
- Extend the existing `card_shell debug-scene` diagnostic with a
  `home_enabled` field so this invariant can be asserted directly, not only
  inferred from pixels.
- Add a QEMU regression test (`tests/test_card_shell_home_bleed.py`, a new
  native `Layer::Bottom` fixture `tests/card_shell_home_layer.c`) that maps
  a distinctly-colored stand-in for Home, drives the real touch-first
  two-axis entry/drag/quick-switch/close gesture sequence, sweeps every
  captured frame for that colour, and confirms Home is hidden throughout the
  gesture and the settled overview, restored once a card is refocused, and
  genuinely re-shown once every card closes (so the fix cannot pass by
  permanently disabling Home).

## What does not change

- No gesture recognizer, threshold, or state machine in
  `nix/card-shell-policy/` changes; `tests/test_card_shell_state.py`'s 29
  cases pass unmodified.
- The Home surface's own Rust rendering, layout, persistence and input
  handling (`nix/rust-shell-client/src/home_*.rs`) are untouched; this is a
  compositor-side scene-visibility fix only.
- This does not claim the coordinator's other suspected black-frame sources
  (a not-yet-drawn scaled-cache mirror texture, bare-cards plate/pad
  interpolation, a newly launched app's first frame) are ruled out; the
  frame-capture sweep in this change's evidence did not find a black frame
  from any of those in the exercised sequence, but it is not an exhaustive
  proof for every gesture the coordinator listed. See `design.md`'s closing
  note.

## Evidence class

Headless-QEMU-injected-input only, via the real cross-built
`nix/card-shell` compositor and a native touch device
(`SWAY_K230_CARD_TEST_INPUT=1`), not physical touch or panel proof. A board
re-check (the same native capture the coordinator used to confirm the
original bug) remains the outstanding evidence gate; see `tasks.md`.
