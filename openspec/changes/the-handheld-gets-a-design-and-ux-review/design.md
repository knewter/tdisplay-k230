## Context

See proposal.md for motivation. The archived `the-handheld-has-a-coherent-ux-plan` provides an interaction contract, flow matrix, issue ledger, reference study, and schematic layouts in `docs/research/handheld-ux/`. Those are inputs, not proof that today's integrated shell meets the intended design. Master `3a296b5` includes board-injected card architecture evidence and a host-tested product adapter; the installed image and opt-in compositor packages must be identified separately during review.

The review layer is documentation about userspace behavior and Nix defaults. Kernel, device tree, and stage 1 remain owned by their existing changes. Startup can be observed without making this analysis responsible for a boot-chain redesign.

## Goals / Non-Goals

**Goals:** Produce a useful, repeatable critique with concrete visual alternatives and an executable follow-up order. Make the gap between functional mechanisms and a polished whole apparent to a reviewer without asking them to infer it from test totals.

**Non-Goals:** No production source changes in this analysis change, no fresh-home state restoration, no numeric "UX completeness" percentage, and no claim of physical usability from screenshots. Implementation successors keep their own acceptance gates.

## Decisions

### Review complete tasks and visual details together

Create a dated `docs/research/handheld-ux/review-round-2/` baseline and reusable rubric. Cover: first usable USB-powered boot; discover and launch an app; type with the keyboard; enter/switch/return from cards; close and refusal; use/stop media; reach Home/Help/System; and recover from empty, loading, stale, error, and denied states. Evaluate keyboard-hidden and keyboard-visible composition where applicable.

For each journey record source/image/store path, starting state, actions, expected and observed result, evidence class, issue IDs, and unknowns. Review hierarchy, type roles, spacing, icons and labels, contrast, focus, reach, feedback, transitions, motion reduction, state persistence, and cross-surface consistency. An absent or unavailable feature is recorded as such, not simulated into the baseline. Rejected alternative: inspecting only isolated happy-path screens, which misses focus and recovery problems.

### Use references as interaction evidence, not a stylistic name

Reuse and verify the existing webOS references; inspect the actual cited material when applying the change. Record reference URL, access date, video timestamps where applicable, the observed principle, and its relevance to this device. Compare spatial continuity, direct manipulation, task switching, chrome, discovery, and feedback with our actual implementation. Distinguish observations from recommendations. Complement that comparison with general usability/accessibility analysis so the critique remains useful beyond cards. Rejected alternative: treating "webOS-like" as acceptance or promising a pixel clone.

### Deliver a small, coherent design direction

Provide at least three annotated current-versus-target comparisons covering Apps, cards, and keyboard/recovery composition, plus one transition storyboard. Use repo-native SVG/HTML or annotated captures with readable labels at 568x1232; mark target drawings as proposals. Render and inspect the artifacts. Consolidate recommendations into shared type, spacing, color, target, and motion guidance, building on the existing contract. Explain trade-offs and CPU/memory/performance dependencies; defer costly effects until measured. Rejected alternative: a list of unrelated aesthetic tweaks or a redesign that depends on unproved acceleration.

### Track impact and confidence separately

Extend the issue ledger with stable IDs, reproducible observation, user impact, severity, evidence confidence, current artifact, proposed correction, owning proposal/path, dependency, acceptance, and rough effort. Mark missing footage as an evidence gap rather than an observed defect. Route launcher actions and recovery language to their existing successors, card behavior to the card change, and renderer eligibility to the GPU change. Create full proposals only for uncovered priorities; landing a proposal does not implement it.

### Review twice with an independent critique

An analysis agent can review reference/visual consistency while another reviews task flows, using separate owned documents. The coordinator reconciles contradictions and selects a small first implementation tranche. This can run beside card/GPU work without a board/build slot. A later serialized board session captures the integrated candidate and rechecks P0/P1 findings against the baseline; note any items still unimplemented or lacking physical evidence. Reuse accepted Home/keyboard observations when unchanged. Cold-start timing remains an explicit observation gap if a justified power-cycle session is unavailable.

The final report answers: what works, what feels unfinished and why, how the webOS-inspired target differs, what improved in the candidate, and the next three implementation priorities. The analysis may conclude while its successor changes remain open; it cannot conclude before its own baseline, comparisons, critique, candidate recheck, and backlog are committed.

## Risks / Trade-offs

- Moving implementation baseline → Pin every capture and recheck to its own revision/artifact; never blend opt-in demos with the default image.
- Subjective taste presented as defect → Cite the concrete task or visual inconsistency, show alternatives, and record confidence separately from severity.
- Physical evidence unavailable → Keep affected claims UNVERIFIED and preserve explicit acceptance work; never convert native or injected captures into finger/optical proof.
- Review consumes the whole work window → Timebox reference collection and mockups to a first actionable pass, land recommendations early, then spend the remaining window on the selected existing/successor implementation scopes.
- Parallel edits collide → Split research documents by owner; serialize edits to the shared ledger and integration. Board and cross-build reservations remain explicit.

## Migration Plan

Publish this proposal first. Apply the analysis to the current baseline, then publish findings and any uncovered successor proposals promptly. Recheck a later integrated build and publish the resulting evidence/status through the existing site pipeline. Archiving syncs only the added documentation capability requirements; runtime features stay with their own changes. Documentation corrections use ordinary reviewed commits and require no reflash.
