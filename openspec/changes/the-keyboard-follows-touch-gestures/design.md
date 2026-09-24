## Context

See proposal.md. The installed coherent shell uses wvkbd and compositor-owned bottom navigation, while the Wi-Fi Settings change adds a separate password editor. The user reported that external keyboard visibility was not discoverable. Existing `nix/card-shell/adapter.c` detects keyboard reservation and excludes it from card gestures. Layers: userspace compositor policy/scene plus Nix session wiring; no hardware change.

## Goals / Non-Goals

**Goals:** Explicit touch ownership, a visible dismissal affordance, direct held motion and continuous release, safe coexistence with app navigation and typing.

**Non-Goals:** New key layout/IME, typing recognition, replacing wvkbd, or binding an application-wide two-finger gesture outside the shell's edge region.

## Decisions

1. Reserve a bounded bottom-edge two-contact chord for explicit show. Both contacts must start inside the edge region within a short bounded join interval; after one-finger navigation commits, a late second contact cancels safely instead of changing ownership. Use centroid displacement after acceptance. Reject an app-wide two-finger grab because applications own their own gestures.
2. A themed grip above the keyboard owns dismissal input. Ordinary key rectangles never become dismissal targets. This makes a downward swipe visible and avoids delaying keystrokes while guessing whether typing will turn into a gesture. A Settings keyboard action remains a fallback with a concise gesture hint.
3. Keep keyboard lifecycle signals and compositor scene/exclusive-area changes under one transition owner. The actual keyboard surface moves, rather than a screenshot substituting for live keys. Prepare/map the surface before exposing it; clip to the output and maintain focus without allowing obscured keys to receive input. On completed hide release its reservation; on completed show account for the full keyboard. Resolve intermediate app allocation consistently instead of leaving a stale gap. Missing/mismatched surfaces abort to usable normal input.
4. Reuse the coherent-shell direct manipulation and velocity-continuous settlement rules. A drag is measured in output-local logical pixels. Samples are bounded and stale velocity expires. New contact, output change or process disappearance stops any uncontrolled animation. Reduced motion shortens post-release travel, never adds held-motion gain.

## Risks / Trade-offs

- Multi-contact edge recognition conflicts with app switching → test early/late second contacts, cancellation and one-finger behavior through native Wayland input.
- Keyboard maps asynchronously or reserves space before visible → verify real layer geometry and fail cleanly instead of animating an absent surface.
- Key input leaks from a dismissed surface → claim only the separate grip and cancel streams before changing ownership.
- Per-frame allocation or raster work harms responsiveness → reuse scene placement, measure on the board, keep hardware acceptance open.

## Migration Plan

Land the proposal first. Build host policy, then integrate compositor/keyboard grip with the current motion checkpoint in an isolated worktree. Cross-build narrowly and prove native injected input before guarded board deployment. Preserve the existing Settings toggle and previous system for recovery; capture real-finger show/hide/typing before archive.
