## Why

A person can boot into the handheld shell and reach working controls, but the experience is currently described as a collection of bring-up features rather than one dependable product journey. Existing evidence covers pieces such as the 568x1232 portrait shell, launcher/catalog, keyboard, splash handoff, window controls, and video playback; it does not yet give a single evidence ledger for first use, discovery, readability, touch reachability, state recovery, and accessibility. Without that plan, new card and gesture work can polish one surface while leaving inconsistent labels, focus, loading, and recovery behavior elsewhere.

This change creates an evidence-driven UX plan and an ordered backlog. It can be authored and checked on the host now; final readability, reachability, motion, and first-boot acceptance still require explicitly labelled board observations.

## What Changes

- Add a reviewable UX plan covering onboarding and boot feedback, launcher discovery, visual hierarchy, touch geometry, navigation, keyboard/focus, video/system states, recovery, motion, and accessibility.
- Record current observations and limits from source, native captures, injected tests, and physical camera evidence without converting injected or host results into real-finger claims.
- Define shared visual and interaction principles for the portrait panel, including measurable type, spacing, contrast, touch-target, focus, state, and motion checks.
- Maintain a prioritized issue ledger and user-flow/task matrix that routes implementation to the correct layer and avoids duplicating the existing card-composition and app-card proposals.
- Identify bounded P0/P1 successor proposals, dependencies, parallel ownership, and board versus host acceptance gates.
- Keep this change planning-only: it does not alter the launcher, compositor, image, desktop files, or runtime behavior.

## Capabilities

### New Capabilities

- `docs/handheld-ux-plan`: An evidence-labelled, reviewable UX plan with user flows, heuristic findings, shared visual/interaction principles, measurable acceptance, and successor proposal boundaries.

### Modified Capabilities

None. This change documents and plans cross-surface behavior; implementation changes will land through successor proposals.

## Impact

The planning deliverable defines a concrete follow-up audit at `docs/research/handheld-ux/` (flow matrix, issue ledger, evidence index, and visual comparison sheets) without adding those research assets in this proposal-only change. It references the Sway/Pixman shell, Foot, touch launcher and catalog, persistent bar, wvkbd, desktop entries, video session, splash evidence, and existing card proposals. Host analysis and deterministic fixture checks can proceed without the board. Board work is required for final first-use timing, real-finger gesture/reachability, optical readability, and any orientation claim. Palm webOS is used as an interaction benchmark for continuity, cards, and recovery, not as a claim that the current shell matches it.
