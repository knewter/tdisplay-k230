## Context

This change is the OpenSpec half of a pair with
`docs/design/shell-ux-critique.md`, requested directly by the operator: "can
you have an agent really nitpick the shell design compared to webos/android
material expressive." That document's §12 ranks 15 findings; this change
implements only the three that have no existing owner (§0/§12 there explains
the routing for the other twelve). It targets capabilities three other open,
unarchived changes already introduce (`runtime/card-shell` from
`the-shell-manages-apps-as-cards`, `runtime/notification-center` and
`runtime/device-settings` from `the-handheld-presents-a-coherent-shell`),
adding further `ADDED` requirements to each rather than creating new
capability names — the same pattern `the-shell-loads-omarchy-themes` and
`the-shell-swaps-themes-without-a-python-stall` already use for
`runtime/shell-themes`.

Slice E was added later, from a second, more literal operator report on the
same finding this change's companion critique already named: "if in
settings swiping up from bottom does nothing it should be like any app
really." That is `shell-ux-critique.md` finding #1 (P0), already routed in
this change's original text to `the-handheld-presents-a-coherent-shell`
tasks 2.2/4.4; those tasks remain open (they cover the larger, still-
unimplemented side-edge contextual Back mechanism), so slice E targets the
narrower, immediately actionable defect those tasks' own evidence already
names — `nix/card-shell/adapter.c:2130`'s unconditional
`if (drawer_mapped()) return false;` — with a bounded touch-routing and
Rust-surface fix, rather than waiting on or duplicating that larger change.
It adds a fourth capability target, `runtime/handheld-shell-design` (from
the same sibling change as `notification-center`/`device-settings`), to the
three this change already touched, following the identical `ADDED`-only
pattern.

This change makes **no source changes** for slices A-D; slice E is a real,
implemented, host- and QEMU-tested fix (see `tasks.md` group E), authorized
directly against the operator's report per `AGENTS.md`'s instruction to
continue through bounded, authorized implementation rather than holding it
behind further proposal-only cycles. Slices A-D remain planning only,
produced while other agents concurrently edit the compositor and Rust
shell; per `AGENTS.md`, they should be validated and handed to the
coordinator promptly rather than held back for implementation.

## Goals / Non-Goals

**Goals:** name a bounded, independently-implementable fix for each of the
three genuinely unowned findings from `shell-ux-critique.md`; keep each fix
small enough to land without touching the gesture state machines several
other in-flight branches (`fix/app-switch-swipe`, `fix/bare-app-cards`,
`impl/direct-app-switch`, `fix/direct-drag`, `perf/theme-background-decode`,
per `python3 tools/work-status.py` at proposal time) are actively changing.

**Non-Goals:** re-specifying anything `the-handheld-presents-a-coherent-shell`
already specifies (navigation-gesture consistency, real card icons,
non-color pressed states — see that document's still-open tasks 1.4, 2.2,
4.4); re-deriving any `webos-polish-review.md` finding; reopening the
recorded "search remains deferred" decision; a new multi-card grid Overview
*mode* distinct from the existing deck (considered below and set aside as
too large for a bounded, parallelizable slice); haptic feedback (no
actuator on this board, per `motion-research.md`'s schematic search);
battery/telephony.

## Decisions

1. **Fix deck legibility by widening the existing peek, not by adding a
   second Overview mode.** Considered alternative: a distinct multi-up grid
   "Overview" screen (illustrated as one option in
   `docs/design/shell-ux-critique-switcher.svg`'s proposed panel, closer to
   webOS/LuneOS's Exposé-like views or Android's grid-style recents) entered
   from its own affordance, separate from the existing single-card deck.
   Rejected for this bounded proposal: it is a new navigation destination
   (a fourth state machine layered on the three `shell-ux-critique.md` §2
   already found: C card policy, Rust overlay routes, Rust Home surface),
   with its own entry/exit gestures, its own empty/loading/private states,
   and its own physical-acceptance gate — a full redesign, not a narrow
   slice, and it risks re-litigating `the-handheld-presents-a-coherent-shell`
   design decision 11's carousel geometry rather than sitting beside it.
   Widening the existing deck's peek fraction is a single-function change
   (`cs_default_config`'s `card_width`/`gap`, and the layout math that
   consumes them) with no new state, no new gesture, and no new screen —
   implementable and testable independent of every other in-flight card
   branch. The richer Overview-mode option remains recorded here as a
   candidate a future proposal can pick up if a widened peek proves
   insufficient once tried.
2. **Shade quick toggles reuse existing request types instead of a new
   settings/notification bridge.** The shade already has an IPC path to the
   same service broker Settings uses (`ServiceRequest`, `service_data.rs`);
   adding shade-side UI that sends the identical `ServiceRequest::Brightness`/
   `KeyboardToggle` values Settings already sends avoids inventing a second
   capability-state protocol. Rejected alternative: a shade-only
   "mini-settings" model with its own state — rejected because it would
   duplicate `ControlState`'s unavailable/read-only/pending semantics
   (`the-handheld-presents-a-coherent-shell`'s "Settings expose only
   supported state and actions" requirement) instead of reusing them.
3. **Accessibility text-scale/contrast rides the existing theme-token
   pipeline rather than inventing a second styling mechanism.** Both
   renderers already consume theme tokens for color
   (`webos-polish-review.md` P1-1 documents the two renderers' *font*
   declarations are separately hand-rolled, which is exactly the failure
   mode this decision avoids repeating for scale/contrast). Extending that
   existing shared pipeline, rather than adding a Rust-only or C-only
   scale mechanism, is what makes the "applies to card headers too" scenario
   in the `device-settings` delta possible at all.

4. **Claim the bottom-edge escape at the compositor's touch-routing layer,
   not inside the Rust overlay's own route/page dispatch.** Considered
   alternative: give `Route::Settings` (and Drawer/Shade) their own
   bottom-edge-swipe-up case in `service_ui.rs`'s `panel_intent`, mirroring
   how each route already recognizes its own local dismiss swipe. Rejected:
   `panel_intent` only ever sees touches the compositor has already decided
   to forward to the client; the operator's literal report ("if in settings
   swiping up from bottom does nothing it should be like any app really")
   and `shell-ux-critique.md` S1.1's trace both locate the actual defect one
   layer lower, in `nix/card-shell/adapter.c`'s `input_down`, which cedes
   the touch to the overlay (`drawer_mapped()`) before the compositor's own
   recognizer ever runs. Fixing it there instead of in the Rust client has
   two consequences worth recording: it reuses the exact same thresholds
   and code path (`cs_begin_entry`/`cs_edge_down`) an app already gets, so
   "the same as any app" is true by construction rather than by a second,
   parallel implementation that could drift; and it applies uniformly
   regardless of which Settings sub-page (theme chooser, Wi-Fi, password
   entry) is currently showing, since the compositor's `drawer_mapped()`
   check does not distinguish sub-pages — closing `shell-ux-critique.md`
   S2's "dead ends three levels deep" finding as a side effect, with no
   separate per-page fix needed. The overlay is told to dismiss itself via
   the pre-existing `Route::Hide` (already reachable from the command line
   as `k230-shell-rust --surface hide`, which is how the coordinator's own
   testing closed a stuck Settings panel before this fix existed) rather
   than a new IPC message, spawned the same fire-and-forget way the
   compositor already launches the drawer/shade overlay
   (`card_shell_launch_surface`, `nix/card-shell/route.c`). Because that
   spawn is asynchronous, the compositor also needs to tolerate
   `drawer_mapped()` still reading true for a frame or two after the escape
   gesture legitimately starts, without letting its own defensive
   cancel-on-remap cleanup (`prepare_impl`, originally written to drop
   *stale* pre-existing drags when an overlay newly maps) discard the
   gesture it just started on the overlay's behalf; a small
   `shell.overlay_escaping` flag distinguishes the two cases.

5. **Unify Shade and Settings' own local dismiss gesture; leave the
   Drawer's alone.** `shell-ux-critique.md` S2 flagged three different,
   independently hand-tuned dismiss predicates (Drawer down, Shade up,
   Settings down) as evidence of three uncoordinated navigation state
   machines. The fully general fix that critique and
   `the-handheld-presents-a-coherent-shell` design decision 4 both point
   toward is a single side-edge contextual Back gesture (that change's task
   2.2); this change does not implement that larger mechanism, which needs
   its own edge-ownership arbitration across the compositor and both
   overlay clients. What this change does fix, narrowly: Settings and Shade
   are both top-anchored sheets reached through the same downward path
   (Settings opens from within the shade — decision 3 of
   `the-handheld-presents-a-coherent-shell/design.md`), so there was never
   a reason for them to disagree, and Settings' downward direction was
   simply copied from the Drawer's convention without noticing the two
   surfaces anchor to opposite edges. Flipping Settings to match Shade
   (both dismiss on an upward drag near the top) removes one of the three
   inconsistent predicates entirely; the Drawer's downward,
   scrolled-to-top-only convention is left unchanged because it anchors to
   the *bottom* edge and reversing it to match Shade/Settings would put it
   in direct conflict with scrolling the drawer's own content upward.

6. **Settings behaves like an app without being a card.** The operator's
   report frames the goal as "it should be like any app really." Read
   narrowly as a touch-routing complaint (decision 4 above), that is now
   true. Read as "should Settings appear in the card overview like webOS's
   Settings card, or Android's Settings-in-recents," the answer is no, for
   an architectural reason that predates this change and is not being
   revisited here: this shell's card overview represents the sibling
   `the-shell-manages-apps-as-cards` implementation's live, backgroundable
   toplevel windows (`CS_LIVE` content), each with its own eligibility,
   privacy, and close lifecycle; Settings is a layer-shell overlay
   (namespace `k230-shell-drawer`), the same kind of transient surface as
   the Drawer and Shade, with no backgroundable process or live pixels a
   card could represent. webOS's Settings genuinely was an ordinary
   card-switchable application. Android's standalone Settings app is a real
   Activity with its own task and does appear in recents — but this shell's
   Settings, reached only through the shade and closed with it, is a much
   closer match to Android's own Quick Settings panel, which is *not*
   represented in recents either. Making Settings a literal card would mean
   giving a transient overlay a live-source/focus/privacy contract designed
   for real applications, a materially larger change than this proposal's
   bounded slices, and the other agent currently reworking the overview's
   own card geometry and headers makes this an especially poor moment to
   add a new kind of card to that model. The bottom-edge escape (decision
   4) already delivers the touch-routing behavior "like any app" that
   prompted the request; `runtime/card-shell`'s new requirement in this
   change's spec delta makes the "not a card" half of this decision
   testable rather than merely asserted here.

## Risks / Trade-offs

- Widening the deck peek necessarily shrinks the selected card, which
  interacts with `the-handheld-presents-a-coherent-shell` design decision
  11's "full or near-full app carousel" language during a two-axis drag.
  This proposal's requirement is scoped to the *released, idle* layout only
  (see its "mid-drag" scenario) specifically to avoid touching that decision;
  an implementer must confirm the drag-time geometry genuinely stays
  independent of the idle peek constant, not merely assume it from this
  document.
- The exact peek fraction and text-scale step are left as evidence-gated
  choices for implementation (`tasks.md`), not fixed numbers here, because
  neither can be justified from a source read alone — both need a rendered
  comparison at minimum, and ideally on-glass legibility confirmation, per
  `shell-ux-critique.md` §14.
- The bottom-edge escape's async "hide" spawn (decision 4) means there is a
  brief window, bounded by IPC round-trip latency, where the overlay is
  still visually mapped while the compositor's own entry animation has
  already started underneath it; a host/QEMU pass cannot measure whether
  that window is perceptible on real glass, only that it resolves correctly
  (task E.4's board gate).
- Task 2.2's full side-edge contextual Back remains unimplemented after
  this change; the dismiss-direction fix (decision 5) only removes one of
  three inconsistent local predicates; it does not add the single
  general mechanism `the-handheld-presents-a-coherent-shell` still plans.

## Migration Plan

None — additive UI only, no data format, protocol, or persisted-state
changes beyond the new text-scale/contrast preference, which follows the
existing theme-choice persistence mechanism already in place. Slice E
(bottom-edge overlay escape and dismiss-direction consistency) is likewise
additive touch-routing behavior with no persisted state; it does not
replace or complete `the-handheld-presents-a-coherent-shell` tasks 2.2/4.4,
which remain open for the general side-edge Back mechanism.

## Open Questions

- Should the accessibility text-scale option offer more than two steps? Left
  at "at least two" deliberately narrow; a task owner with real low-vision
  input may want more granularity, which would not require new spec text 
  here, only a wider implementation of the same requirement.
