# Card shell policy integration contract

This is the product policy for `the-shell-manages-apps-as-cards`, task 2.1.
The compositor adapter must compile this C source directly. The Python test
runner compiles the same source with AddressSanitizer and UndefinedBehaviorSanitizer;
there is no parallel Python state model. The module contains no compositor,
renderer, surface, buffer, IPC, title, or app-text access.

The reviewed UX contract is
`docs/research/handheld-ux/interaction-contract.md`, accepted by the coordinator
in `docs/research/handheld-ux/design-review.md`. The defaults retain the 56px top
bar, 24px content inset, 56px footer controls, horizontal adjacent-card visibility,
and distinct title/state area. Card identity, private/unavailable feedback and
recovery have non-color labels. Motion and throw constants are provisional
configuration, not measured or accepted physical thresholds. No interpolation
is performed: reduced-motion mode has identical direct tracking and outcomes.

## Integration order and ownership

1. Initialize once with `cs_default_config(568, 1232)` and `cs_init`. The
   adapter obtains actual output dimensions and keyboard reservation; it must
   adjust `bottom_reserved` and `card_height` through `cs_set_config` before
   drawing into the available viewport. Invalid geometry returns a normal-shell
   recovery action. Never move recovery buttons beneath the keyboard.
2. Enumerate the compositor's current application records and call
   `cs_set_cards` with a complete snapshot of stable nonzero container IDs,
   `CS_LIVE`, `CS_PRIVATE` or `CS_UNAVAILABLE`, and separate focus/close
   permissions. There is no app-ID allowlist or fixed card-count limit in the
   policy. It copies the snapshot, accepts 257 cards in the host fixture, and
   aborts to normal on malformed IDs or allocation failure. IDs must not be
   reused within a session. Snapshot updates belong on lifecycle and policy
   changes, not on every frame.
3. Classification belongs to the Sway adapter. Only a source whose ownership,
   content policy and format have been checked can be `CS_LIVE`. An unknown or
   unsupported source is `CS_UNAVAILABLE`; explicit private/protected/session
   exclusion is `CS_PRIVATE`. Unknown protection cannot be assumed safe.
   Call `cs_set_cards` before accessing a changed source after map, unmap,
   destruction, policy, output or source-class changes. Private/unavailable
   sources must have **no mirror, buffer reference, thumbnail, title, or app
   text** in the deck. Use `cs_card_text` for fixed placeholder wording.
4. The persistent Cards button calls `cs_enter` directly. Global edge input
   calls `cs_edge_down/motion/up` before app dispatch: the adapter reserves
   that initial edge touch and must never replay a partial stream into an
   application. Entry requires an upward single-contact swipe, not a tap.
   While the keyboard occupies the bottom edge, use the persistent button;
   do not intercept keyboard touches. After entry the initial contact is
   consumed through its up, without selecting a card accidentally.
5. While the deck is active, call `cs_down/motion/up` for touch input. Check
   compositor-owned controls before card hit tests, and clip every card to
   `cs_content_rect`. Bar and keyboard regions pass through. Every accepted
   touch gets exactly one down and up: policy cancellation drains the owned
   stream; further contacts cannot accidentally activate the restored app.
   This draining is for local rejection only (`cs_cancel`/`cs_edge_cancel`). A
   compositor touch-cancel event or device removal may end the stream without
   any up. In that case call **`cs_stream_cancel`**, which clears contact, edge
   and blocked-contact state immediately, returns a dragging card to the stable
   deck and permits the next stream. A pending graceful close keeps its separate
   deadline. On output loss/session lock, follow with `cs_leave`.
   Forward `cs_motion` on every real motion, then use `cs_card_rect` for all
   card positions. The horizontal deck follows the same `dx`; a vertical
   throw moves only the actual touched card, including a visible adjacent card.
6. Buttons call `cs_step(-1|1)` and `cs_request_close(id, monotonic_ms)`.
   A tap on a live, focusable card produces expansion. Private/unavailable
   taps expose recovery wording instead. Upward close requires both displacement
   and recent upward velocity; a slow drag, downward release or long-held
   position never requests close. The close button uses the same request path
   without requiring a gesture. Repeated requests while pending dispatch nothing.
7. For `CS_CLOSE`, resolve `close_id` against a still-current live container
   and invoke Sway's graceful `view_close` exactly once. Never kill a process.
   Arm the deadline and call `cs_tick`; classify an explicit refusal or failed
   dispatch with `cs_close_result`. A still-present source at the deadline is
   **timeout**, not proven refusal. An absent source returns `source_gone_id`,
   which establishes unmap/removal only, never process exit. The adapter's
   client/process observations are separate evidence. Refusal, timeout and
   failure leave the source and card usable, with safe recovery wording.
8. For every Apps, Windows, Home, Keyboard, System, Help, Terminal, Monitor or
   Back control, call `cs_leave`, reconcile/destroy card nodes, restore source
   routing/focus, then execute the existing route. `CS_RESTORE`/`CS_EXPAND`
   carries `focus_id`; resolve it afresh before focus, falling back to a valid
   workspace when zero or no longer present. The pure policy tests establish
   the shared leave transition; they do not establish that UI routes are wired.
9. On `CS_RECONCILE`, reconcile node ownership against the **new** snapshot.
   `cs_can_mirror` is false in normal mode and for every denied/unknown ID.
   This must be checked before attaching or retaining any live scene node.
   On surface loss during a drag, consume the remaining touch and remove the
   source. On session lock, output loss, or compositor failure, call `cs_leave`
   and restore ordinary Sway. Finish with `cs_finish` to release the snapshot.

`cs_result.actions` is a bitmask. A result may combine redraw, reconcile and
restore. `close_id` is actionable only with `CS_CLOSE`; `focus_id` is actionable
only with restore/expand. No callback or presentation claim follows from a
policy result. Renderers must keep frame callbacks, sample/damage and physical
presentation measurements independent.

## Host acceptance and remaining slices

Run from the repository root:

```sh
python3 tests/test_card_shell_state.py
```

Twenty-one compiled scenarios cover shrink/expand, horizontal movement, adjacent
identity, private/unavailable classification and changes during/after drag,
close deadlines/refusal/failure, source loss, recovery transitions, multiple
contacts, edge entry, keyboard/bar geometry, changed IDs, more than two cards,
reduced-motion equivalence, invalid events, button equivalents, and 9,999
mixed event transitions. Complete-stream cancellation is exercised with no later
up, followed by a fresh successful gesture, including after a multi-contact
abort. They run with memory and undefined-behavior checks.

This module supplies task 2.1 only. It does not close global gesture/button
integration (2.2), actual surface safety/rendering (3.1), native gestures (3.2),
packaging (3.3), or any benchmark, QEMU or physical acceptance task. The adapter
must prove its use of this module with live root/subsurface changes, private
placeholder pixels, real focus and close traces, all persistent controls, and
scene teardown before default integration. The architecture's board capability
proof remains a dependency for integrating live product composition.

The performance slice still needs a declared CPU frame/update, input-to-visible
and incremental-memory budget plus measurements at 568x1232 RGB565. Existing
probe cgroup CPU/memory and callback counts do not alone establish input latency
or panel presentation. Neither the 200ms launcher release result nor this host
state test can be reused as physical live-card acceptance. Every physical
motion/readability/protection/callback gate remains **UNVERIFIED** here.
