## Context

The current native launcher is a Wayland layer-shell client using SHM/Pango/Cairo
and direct `wl_touch` events. It activates a card only when release remains over the
same card; motion outside the card cancels activation. The persistent shell bar and
its `touch-menu.sh` already provide button-based Apps, Windows/Home, Keyboard,
System, Terminal, and Monitor paths. Sway owns DRM, input routing, workspaces, and
focus through IPC.

The panel is 568x1232 at about 52.19 Hz, RGB565, and Pixman-rendered with no DRM
render node. Existing scene-build/KMS submission measurements are 14.0 ms median,
15.6 ms p95, and 22.7 ms p99 under terminal scrolling and keyboard load. They do not
prove presentation timing for a new animation.

## Goals / Non-Goals

**Goals:**

- Add a deterministic one-touch gesture state machine to the existing launcher.
- Keep taps, buttons, Help, keyboard, Home, and error recovery unchanged.
- Add a metadata-only window overview in the same client, with stale/empty safety.
- Bound transition work and measure update cost/memory before physical acceptance.

**Non-Goals:**

- Sway/wlroots changes, a compositor fork, GPU/VGLite integration, or live
screencopy thumbnails.
- Multi-touch, pinch, inertial physics, edge gestures outside the launcher, or
keyboard search.
- Replacing the persistent Windows/Home bar or claiming final-glass usability from
injected input.

## Decisions

1. **Keep one launcher client.** Extend the existing layer-shell surface and state
machine so the gesture and overview share current launch/error/Back behavior. A
separate overview client would duplicate input and lifecycle handling before live
thumbnails are even available.

2. **Use fixed geometry thresholds.** Start with a 48 logical-pixel threshold
as an explicit tuning assumption, to be accepted or adjusted from new gesture
evidence on the panel. It is not yet a measured finger-jitter boundary. Require a 1.25
horizontal/vertical dominance ratio. Once the threshold is crossed, cancel tap
activation permanently for that touch. Reject multi-touch and compositor cancellation.

3. **Map directions to simple modes.** Horizontal left/right pages the existing Apps
catalog. Up enters metadata overview; down exits it. A mode transition is committed
only on release after classification, avoiding partial app launches during motion.
The existing Previous/Next/Back buttons remain equivalent non-gesture routes.

4. **Use Sway metadata, not thumbnails.** Read the current tree through the existing
IPC boundary or a small shell-owned helper and retain stable container identifiers
only for the open view. Draw title/app ID/state cards. Re-query before focus and treat
missing IDs as stale; never assume a window still exists. No screencopy or privacy
surface is introduced in this phase.

5. **Keep keyboard focus out of the overlay.** The launcher and overview remain
layer-shell keyboard-non-interactive. Selecting a card closes/yields the surface
before focusing the target. The on-screen keyboard is still controlled by the
persistent bar and retains its current focus semantics.

6. **Bound transitions for Pixman.** Pre-render the source and destination card
pages, use a short fixed translation/settle sequence capped at 200 ms, and fall back
to an immediate final frame if frame work misses the deadline. Do not add blur,
shadows, alpha-heavy thumbnails, or continuous physics until measured evidence
justifies them.

## Risks / Trade-offs

- [Touch jitter is classified as a swipe] -> require 48 px plus the 1.25 dominance
ratio, cancel on multi-touch, and preserve tap/button fallbacks.
- [A swipe launches an app] -> crossing the threshold permanently disarms card
activation for that touch; test release both inside and outside the original card.
- [Sway window IDs become stale] -> re-query metadata at selection and show a safe
empty/stale state with Back.
- [Pixman misses the transition budget] -> cap duration, pre-render, and settle
without animation; retain button navigation.
- [Overview obscures keyboard or terminal input] -> keep keyboard interactivity
none and close before focusing a selected toplevel.
- [Injected tests overstate physical usability] -> label them separately and require
a focused physical camera capture for real-finger direction, page change, tap, and
Back; do not repeat already accepted keyboard/Home tests.

## Migration Plan

Build the launcher with the gesture state machine behind the existing Apps entry.
Run host state-machine tests and injected input checks first. Flash only after the
launcher package and shell image validate. If gestures regress, disable gesture
recognition while retaining the existing tap/button launcher; the persistent bar
and Apps catalog remain the recovery path. If the overview is unstable, remove only
its mode and leave horizontal paging and all prior controls intact.

## Open Questions

None. Live thumbnails and compositor-level gestures are deferred decisions, not
requirements for this bounded first phase.
