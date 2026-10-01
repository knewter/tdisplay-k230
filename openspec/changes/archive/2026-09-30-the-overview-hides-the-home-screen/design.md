## Context

`the-shell-presents-a-pinned-home-screen` added an always-mapped
`Layer::Bottom` Home surface (`nix/rust-shell-client/src/main.rs`'s
`HomeSurface`) directly above `Layer::Background` (the wallpaper) and below
every ordinary toplevel and the drawer/shade/Settings `Layer::Overlay`
surface. That change's own decision 1 says a focused app or an open overlay
occludes Home "with no explicit 'is anything else showing' check in this
client at all" -- true for ordinary opaque stacking, but it did not account
for the card overview, which is a compositor-native scene
(`nix/card-shell/adapter.c`'s `shell.ui`/`shell.deck`/`shell.canvas`,
created under `root->layers.shell_overlay`) that sits *above*
`Layer::Bottom` and is not fully opaque everywhere. The coordinator's report
-- a person on real glass seeing "black / glitching" in the overview, and a
native capture confirming Home's grid and dock painting through the deck --
is that gap. Full root-cause detail, the exact scene layers involved, and
the reproduction/regression evidence are in
`docs/evidence/card-shell/overview-home-bleed-through/README.md`; this file
covers the decisions, not the mechanism twice.

## Decisions

### 1. Fix it in the compositor (`adapter.c`), not the Rust client

The design considered had the Rust client learn the overview's open/closed
state (over some new IPC or socket) and hide or repaint itself
transparently in response. Rejected: the Rust client today has zero
knowledge of card-shell state -- `main.rs` never references `shell.active`,
`card_shell`, or `Overview` -- and adding that coupling would mean a new
message contract, a new failure mode (client and compositor disagreeing
about who currently owns the screen), and a client-side unmap/remap or
buffer-content decision that costs a Wayland round trip and risks its own
black frame from a freshly reattached surface. The compositor already knows
`shell.active` authoritatively and already toggles a scene node
(`shell.ordinary_backdrop`) at exactly the two moments that matter for the
mirror-image reason (revealing the wallpaper only when nothing better-
informed, like the overview canvas, is deciding that already). Toggling
`output->layers.shell_bottom`'s `enabled` flag at those same two points is a
pure scene-graph mutation: no client round trip, no buffer churn, and (per
the evidence README) provably atomic with the deck's own enable/disable
calls, so no frame renders with both visible.

### 2. Hide the whole `Layer::Bottom` tree, not just paint over Home's bounds

Grepping `nix/rust-shell-client/src/main.rs` confirms Home is the only
client ever mapped on `Layer::Bottom` in this shell (`Layer::Bottom` appears
exactly once, in `HomeSurface`'s own mapping). Disabling the whole layer
tree is therefore equivalent to disabling Home specifically, and is simpler
and more future-proof than adding a card-shell-specific opaque rect sized to
match Home's bounds (which would need to track Home's geometry and would
still leave a second thing to keep in sync if a future change ever changed
Home's shape).

### 3. Toggle at the existing `CS_SHRINK`/`restore()` boundaries, not at
   `shell.active`'s read sites

`shell.active` is read in roughly twenty places in `adapter.c` but written
in exactly two (`handle_result`'s `CS_SHRINK` branch, and `restore()`).
Syncing `home_layer_sync` at the write sites, alongside the existing
`ordinary_backdrop_sync` calls, keeps the invariant obviously paired and
grep-able, rather than requiring a change everywhere `shell.active` might
newly matter. It also means the fix engages at the exact moment
`cs_begin_entry`'s folded `CS_SHRINK` result reaches `adapter.c` -- gesture
start, not gesture end -- which the evidence README's `entry-01-touch-
down.png` confirms directly.

### 4. Extend `debug-scene`, don't add a new IPC verb

`card_shell debug-scene` already exists precisely to make scene-graph state
assertable without inferring it from pixels (its own comment: "Self-evident
diagnosis for 'the wallpaper is not visible'"). Adding `home_enabled` to its
existing output is one field, reuses the same board (`journalctl`) and test
(`ipc()`/`assertIn`) paths every existing consumer already has, and needs no
new command parsing.

### 5. Regression coverage via a synthetic `Layer::Bottom` fixture, not the real Rust client

Running the actual `handheld-shell-rust` binary under this suite's headless
QEMU harness would need its full runtime environment (desktop-entry
catalog, `$XDG_STATE_HOME` layout persistence, its own Wayland globals) for
behavior this fix does not touch at all -- the bug and the fix are entirely
about compositor-side scene visibility, not Home's content. A tiny native
fixture (`tests/card_shell_home_layer.c`, modeled directly on the existing
`tests/card_shell_drawer_layer.c` pattern already used for the drawer's own
`Layer::Overlay` bleed testing) maps the exact same layer/anchor/size shape
with a single unmistakable colour, giving a fast, deterministic,
false-positive-resistant assertion surface without any Rust/cross-build
dependency in the test itself.

## What was investigated and not changed

The coordinator's other suspected black-frame sources -- a scaled-cache or
bare-cards mirror texture that has not drawn yet, a newly launched app's
first frame -- were not found in the exercised two-axis entry/drag/quick-
switch/close/settle sequence (`assert_no_black_flash` in
`tests/card_shell_runtime.py`, applied to every frame that sequence
captures). This is evidence against those sources in that specific
sequence, not an exhaustive sweep of every gesture the coordinator listed
(see the evidence README's "Limits" section). No change was made to
`nix/card-shell/scaled-cache.c`, `nix/card-shell-policy/card-shell-
policy.c`'s pad/plate interpolation, or app-launch first-frame handling,
because no defect was found there to fix; a future change should extend
`assert_no_black_flash`-style coverage to a from-launch sequence and to
scaled-cache-enabled runs (`--scaled-cache`) if the board re-check (this
change's remaining evidence gate) still shows glitching after this fix
lands.
