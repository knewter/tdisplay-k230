# WebOS-like shell feasibility audit

Date: 2026-09-23

## Recommendation

A webOS-like feel is feasible as a shell-level feature. The smallest useful step is a
native overview surface that keeps Sway as the compositor and adds touch paging,
window cards, and one-handed transitions. Do not replace Sway or fork wlroots for
this goal.

The current system already has the right seams:

- Sway owns DRM, input routing, workspaces, and toplevel focus.
- `k230-touch-launcher` is a Wayland layer-shell client with SHM rendering and
  direct `wl_touch` handling.
- The bar/menu wrapper already reads Sway's tree through IPC and focuses or starts
  windows.
- Applications share a tabbed workspace, which gives an overview client a simple
  focus/return model.

The current launcher is intentionally tap-oriented. Its touch motion handler cancels
a card activation whenever the finger leaves the original card, so a directional
drag has no action. That is a clean place for a bounded gesture prototype.

## Hardware and rendering limits

The panel is 568x1232 at about 52.19 Hz, with RGB565 scanout and Pixman CPU
rendering. The board has no DRM render node or GL/Vulkan path for this shell. The
enabled VGLite `/dev/vg_lite` driver is a separate single-context vendor 2D API,
not a wlroots renderer or KMS buffer producer. Existing
measurements are encouraging for restrained transitions:

- Sway/Pixman scene-build plus KMS submission had a 14.0 ms median and 15.6 ms p95
  under a scrolling terminal with the 400 px keyboard visible.
- The measured p99 was 22.7 ms. These are submission intervals, not presentation
  or touch latency.
- The shell user's graphical-session PSS was 36.6 MiB with the keyboard hidden and
  40.0 MiB shown; Linux reported 760 MiB available in that idle measurement.

This leaves room for a small 150-250 ms slide or crossfade, but it does not establish
that a full-screen animated overview will hold 52 Hz. Avoid blur, shadows rendered
per frame, large live thumbnails, and animation that repaints several full-screen
surfaces at once. Use solid cards, text, small icons, and a fixed frame budget.

A 568x1232 ARGB8888 launcher buffer is about 2.8 MiB before compositor copies;
RGB565 is about 1.4 MiB. One or two additional buffers are affordable in memory,
but repeated full-screen Pixman composition is the relevant cost.

## Three implementation paths

### 1. Extend the existing launcher: recommended first spike

Keep the existing Apps client and add:

1. A drag recognizer with a minimum distance and release direction.
2. A page transition that moves two pre-rendered card pages across the surface.
3. A stable gesture contract: horizontal swipe changes app pages; vertical swipe
   opens/closes the overview; tap activates a card; movement below the threshold
   remains a tap.
4. A short transition timeout or frame counter so a slow render cannot leave the
   overlay half-open.
5. A visible fallback to Previous/Next and Back for users who do not perform the
   gesture.

This is a client-only change. It preserves current layer-shell input, error recovery,
Help, and terminal launch behavior. The first prototype can use app cards and window
labels without thumbnails, so it does not need compositor extensions.

### 2. Add a dedicated window-overview client: useful second step

A separate layer-shell client can subscribe to Sway IPC, enumerate containers, draw
cards, and issue focus/close/workspace commands. This is a better home for a polished
overview than making the Apps catalog also manage live windows.

It cannot obtain trustworthy live thumbnails through the existing client interfaces.
Sway IPC gives tree metadata, while a screenshot/thumbnail path requires a compositor
screencopy protocol or an external capture path. The first version should therefore
use deterministic cards containing app title, state, and a simple icon. Add thumbnails
only after measuring capture and Pixman cost and deciding the privacy/input behavior.

A dedicated client also needs explicit lifecycle handling: close on selected window,
focus/return after an app exits, stale-container IDs, empty-window state, and a
keyboard-visible layout. Those are manageable, but they make this a second proposal
after the gesture spike.

### 3. Fork or replace Sway: reject for this goal

A compositor fork would own gesture recognition, transitions, and card compositing, but
it would also inherit DRM handoff, RGB565 format selection, Pixman behavior, input
mapping, keyboard focus, layer-shell compatibility, and the project’s splash handoff.
That adds a large regression surface without solving a demonstrated limitation.

Replacing Sway with a GPU-oriented compositor is a poor fit for this board. The
existing shell deliberately selects wlroots Pixman and DRM dumb buffers because the
board has no render node. A compositor designed around GLES would add build and
runtime risk without improving the hardware path.

## Gesture and protocol notes

Current upstream Sway documents `bindgesture` for hold, pinch, and three-to-five
finger swipe gestures. That facility is useful for compositor-level workspace actions,
but it is not a substitute for the launcher’s single-finger touchscreen interaction:
the launcher receives `wl_touch` events directly and currently treats motion as card
cancellation. The app should recognize its own one-finger swipe from the touch stream.

The launcher already uses a layer-shell overlay with keyboard interactivity disabled,
which is appropriate for an app chooser that should not steal terminal keyboard
focus. A future overview should keep that behavior while it is visible, then destroy
or hide itself before focusing the selected terminal. The layer-shell protocol supports
normal pointer/touch delivery and explicit keyboard-interactivity modes; keep the
overview non-keyboard-interactive unless text search is deliberately added.

## Smallest useful prototype

Prototype only one behavior first:

- Open Apps.
- Swipe left/right across the card area to change page.
- Animate the page for at most 200 ms.
- Tap a card to launch.
- Back closes the launcher.
- Previous/Next still work.
- Help page explicitly describes the gesture and retains button controls.

Do not include window thumbnails, pinch-to-resize, inertial physics, or a new compositor.
The prototype should be a native client testable with the existing injected input path,
then a short real-finger camera capture focused on swipe direction, page change, tap,
and Back.

Suggested acceptance measurements:

- No missed or duplicate page changes across 20 injected swipes in both directions.
- No card launches from a swipe whose release point is outside the original card.
- Median and p95 client frame/update time during the transition, using the existing
  diagnostic timing method where possible.
- Memory delta with the overview open.
- Real-finger capture at focus 30 or better showing both swipe directions and a tap.
- Existing launcher, Help, keyboard, Terminal, Monitor, and error-recovery tests still
  pass.

The next formal change should therefore be scoped as “touch launcher gestures and
overview cards,” with a client-only first phase and thumbnail capture explicitly
deferred.

References: [Sway gesture bindings](https://github.com/swaywm/sway/blob/master/sway/sway.5.scd)
and [wlr-layer-shell keyboard/input semantics](https://wayland.app/protocols/wlr-layer-shell-unstable-v1).

