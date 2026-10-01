## Context

The operator said the drawer seems fine and asked to spend performance effort
when slow behavior arises. Keyboard gestures and ordinary-card/video behavior are also accepted. The archived
functional closeouts must not claim measurements they never performed.

## Goals / Non-Goals

Preserve pending quantitative obligations without tying accepted UX to a new
benchmark campaign. Do not reopen accepted navigation or optimize speculatively.

## Decisions

Userspace: retain existing bounded timing instrumentation. Start with the
reported route/workload and exact installed Rust/compositor/system identities.
For drawer sustained scrolling, read `K230_DRAWER_FRAME ms=` from the process
journal; compare it with the review's unverified 17.3–34.6 ms estimate and ~20 ms
target. Client paint timing alone is not a presentation or finger-latency result.
For keyboard show/hold/reverse/hide, use installed compositor instrumentation
and the already-defined shell responsiveness budgets; preserve failures as
failures. Static images do not demonstrate motion timing.
For ordinary cards, retain the sub-400ms entry-animation and sub-100ms touch-ack targets from `the-card-shell-has-no-video-special-case` task 5.1. The earlier per-event subprocess injector did not establish either target. Use real contact with instrumentation or a held uinput device, record installed identities, and distinguish input acknowledgement, presentation and optical latency.

Conditional optimization: if a measured drawer bottleneck justifies it, propose
scroll-direction damage-limited blitting from `docs/design/app-drawer-review.md`
section 6, with measured before/after proof. Otherwise document that no change
was justified. Reject unconditional tuning merely to empty a checklist.

## Risks / Trade-offs

A retained estimate could be mistaken for proof → mark quantitative claims
UNVERIFIED and record exact workload, identity and limitations with results.

## Migration Plan

Land this successor before archiving its parents. Keep it planned until a slow
interaction is reported or the user specifically requests measurements. Reserve
board/build resources only when actually executing its tasks. Any code change
gets its own qualified candidate and recovery path.
