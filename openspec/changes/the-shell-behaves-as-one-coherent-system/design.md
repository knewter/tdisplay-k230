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

This change makes **no source changes**. It is planning only, produced while
other agents concurrently edit the compositor and Rust shell; per
`AGENTS.md`, it should be validated and handed to the coordinator promptly
rather than held back for implementation.

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

## Migration Plan

None — additive UI only, no data format, protocol, or persisted-state
changes beyond the new text-scale/contrast preference, which follows the
existing theme-choice persistence mechanism already in place.

## Open Questions

- Should the accessibility text-scale option offer more than two steps? Left
  at "at least two" deliberately narrow; a task owner with real low-vision
  input may want more granularity, which would not require new spec text 
  here, only a wider implementation of the same requirement.
