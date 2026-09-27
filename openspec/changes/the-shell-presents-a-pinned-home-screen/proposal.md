## Why

A person picking up this handheld today has no ordinary home screen. At rest
(no application focused, the card overview dismissed) the panel shows only the
theme wallpaper; the only way to a specific application is the vertically
scrolling "All apps" drawer reached by swiping up, and the only thing titled
"Home" on this device is the live app-card overview itself. The user's own
words: "why no homescreen there should be a normal-ass homescreen with pinned
icons and i can swipe between screens of icons". No amount of drawer scrolling
gives a person the thing every phone launcher (webOS, Android, iOS) provides:
a small, chosen set of app icons, arranged by the person, reachable in one
glance without opening a full alphabetical catalog.

This collides with a real prior decision. Decision 1 of
`the-handheld-presents-a-coherent-shell` (`design.md`, still unarchived) reads
"Home is the deck, not a grid... This shell chooses the Palm-style live deck
as Home rather than an Android home grid", and its non-goals list "an
Android-style second home grid". That decision was made to avoid two competing
home destinations, which was the right worry with the information available
then. The user has now explicitly asked for exactly the grid it rejected. This
proposal supersedes that specific sentence of decision 1 (not the sibling
change's card-manipulation physics, close lifecycle, or composition-boundary
decisions, which this proposal does not touch) and resolves the "two homes"
worry differently: by giving the *deck* back its own name (the app switcher/
overview) and reserving "Home" for the one screen that already appears
whenever nothing else is focused. See `design.md` for the full reconciliation
and the coordinator note about updating the sibling proposal's wording.

## What Changes

- Add a pinned-icon home screen: the theme wallpaper with a grid of
  touch-sized app icons across horizontally swipeable pages (1:1 drag,
  momentum, ease-out settle to the nearest page, non-interactive page-dot
  indicators — never buttons), plus a persistent bottom quick-launch dock
  (webOS Quick Launch / Android hotseat convention) whose icons stay fixed
  across every page.
- Add pinning and unpinning: long-press an app in the drawer for an "Add to
  Home" action; long-press an icon already on Home to enter a dismissible
  rearrange mode that drags an icon within or between pages, into or out of
  the dock, or removes it.
- Seed a fresh Home from installed desktop entries with a sensible curated
  default set (terminal, file manager, text editor, system monitor, video
  player, Settings, and the app drawer itself) when no saved layout exists,
  and persist every change (pin, unpin, reorder, page assignment) under the
  shell user's XDG state directory so it survives a restart and a reboot.
- Make tapping a Home icon launch the app, or focus its existing window when
  one is already running, instead of always starting a second instance.
- Wire the user's explicit navigation sequence: the bottom-edge swipe from
  an app opens Overview; an upward swipe from Overview's bottom navigation
  area reveals Home without closing apps; the next upward swipe from Home
  opens All apps. Swiping a card itself upward still closes only that card.
- Add compositor-owned Home visibility and focus handling. Apps stay mapped,
  keep their container IDs and remain selectable; selecting an existing app
  or launching a new app returns it to the foreground. Partial/reversed Home
  gestures return to Overview, with movement tracking the contact.

**Non-goals:** search, folders or categories beyond the existing drawer list,
home-screen widgets, a wallpaper picker (Home reads the existing theme
wallpaper, it does not add a way to choose one), multi-user profiles,
haptics (no haptic hardware exists on this board), the second CPU core, and
any change to the sibling change's card drag/expand/throw-close physics or
composition boundary. The navigation addition changes Overview-to-Home routing and scene visibility;
card manipulation and close-lifecycle behavior remain owned by their existing
implementation.

**Board dependency:** the pager physics, grid layout, pin persistence, and
drag-reorder are host-testable Rust unit tests and run under `cargo test
--offline` with no hardware. A QEMU injected-touch test (styled on
`tests/rust_theme_chooser_qemu.py`) exercises the compositor/client pairing,
the new layer-shell surface, page swipe, dock taps, and the pin flow with a
synthetic desktop-entry/icon fixture — this is QEMU proof of wiring and
layout, not of touch feel, contrast, or real-glass usability. The navigation addition includes a reserved physical-board injected-input
trial and matching-system installation. The broader real-finger, daylight
readability and rearrangement acceptance remains explicitly open in task 8.1.

## Capabilities

### New Capabilities

- `runtime/home-screen`: a pinned-icon, paged launcher shown whenever no
  application owns the panel, its persistence, its pin/unpin/rearrange
  interactions, and its reconciled place in the shell's gesture topology.

### Modified Capabilities

None. (The card overview's on-screen title is cosmetic chrome text, not a
requirement of any archived `openspec/specs/` capability; `runtime/shell`,
`runtime/gpu-validation`, and `runtime/video` are unaffected. The sibling
`the-handheld-presents-a-coherent-shell` and `the-shell-manages-apps-as-cards`
changes are still unarchived, so no `MODIFIED` delta can legally target their
not-yet-existing capability specs per `.skills/k230-spec-change/SKILL.md`;
this proposal's `design.md` instead records in prose exactly which sentence of
the sibling's `design.md` it supersedes, for the coordinator to reconcile at
that change's next revision or archive.)

## Impact

Userspace only: `nix/rust-shell-client/` gains new modules (pager physics,
grid/dock layout, pin persistence) and a new always-mapped layer-shell surface
plus its touch/frame/configure wiring in `main.rs`; `nix/card-shell/adapter.c`
and its routing/focus hooks make Home reachable without unmapping apps.
No kernel, device tree, boot, radio, or second-core change. No new Nix
package; the existing `.#handheld-shell-rust` and `.#card-shell` outputs and
the `k230-coherent-shell` NixOS configuration absorb the change. Host build,
`cargo test`, and a QEMU injected-touch smoke test can all proceed without the
physical board; real-finger and daylight-readability board acceptance remain
open evidence gates for the coordinator.
