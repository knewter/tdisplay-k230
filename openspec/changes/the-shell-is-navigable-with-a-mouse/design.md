## Context

The shell has two input owners: compositor-native overview/edge navigation and Rust layer surfaces for Home and overlays. Standard wl_pointer support was added to Rust but is absent in the overview adapter. The relay makes the inactive built-in glass a relative trackpad in HDMI mode.

## Goals / Non-Goals

Provide complete round trips between app, overview, Home and drawer without terminating windows. Keep mouse controls consistent with touch. Preserve existing gestures and ordinary application input. Do not alter display transforms, kernel drivers or the trackpad relay's physical coordinate mapping.

## Decisions

1. Userspace compositor: reserve primary pointer streams only when overview owns the region or a pointer drag starts at a shell edge. Reuse the existing touch navigation policy with a separate pointer identity and balanced release/cancellation. Never forward a partial grabbed stream to an app. Hover alone must not activate navigation.
2. Turn the existing Home footer into a labeled tap/click target as well as a swipe origin. Opening Home hides app scene groups and clears app focus without closing or unmapping windows. Retain continuous swipe tracking.
3. Four-finger outward pinch uses a compositor command which performs the same animated expansion as tapping the centered live card. Disabled/private/unavailable cards and empty decks remain safe. Device scope prevents consuming an application's ordinary two-finger zoom. Pinch from a mapped overlay can dismiss that overlay before navigation when appropriate.
4. Rust shell: route axis events to each page's existing scroll or carousel state, bounded by its geometry; ignore scrolling during an owned press/drag. Reuse page rendering and state, without fake button presses or applying themes on scroll.
5. Edge gestures coexist with mouse navigation as primary-button drags from top/bottom screen edges. This uses pointer position on the active display; it does not reinterpret the physical trackpad's edges as absolute display edges. The latter would need a separate relay ownership design and is outside this fix.

## Alternatives rejected

Persistent Back/Home button bars were rejected in the prior touchscreen design. Make the existing footer affordance interactive and provide mouse edge drags instead. Replaying a mouse drag as touch into arbitrary apps is rejected; only compositor-owned shell navigation uses shared policy. Hard-coded desktop icon coordinates are unsuitable for production dispatch; tests may use known geometry with assertions against actual focus and scene state.

## Risks

Pointer ownership must survive dragging across a card or layer boundary and cancel safely on output/device/seat loss. Wheel deltas from discrete mice and smooth touchpads must both work without fighting momentum or changing theme selection on scroll. Native captures and injected input do not establish physical gesture recognition.
