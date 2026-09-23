## Why

A working launcher, keyboard, and card mechanism do not yet tell us whether the handheld feels coherent, discoverable, and refined in everyday use. The first UX plan is archived, but new card work needs a broader design critique against actual screens and journeys, with an explicit answer to what still separates this shell from the intended webOS-inspired experience.

## What Changes

- Run a general design and UX analysis round across the shell, Apps, cards, keyboard, terminal, media, Help, System, startup, and recovery, using a reusable review rubric.
- Review visual hierarchy, typography, spacing, iconography, color/contrast, density, touch reach, feedback, motion, focus, language, accessibility, and consistency across complete tasks.
- Compare dated current captures with annotated target layouts and referenced interaction examples. Separate implementation completeness from design quality and confidence in the evidence.
- Produce an actionable severity-ranked critique, a small coherent set of design recommendations, and an ordered implementation backlog. Route existing issues to existing proposals; land bounded successors for uncovered priorities.
- Recheck the highest-priority findings on the integrated build before calling the review complete, recording regressions, improvements, and remaining unknowns.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `docs/handheld-ux-plan`: Add a repeatable whole-product critique, reviewable current/target comparisons, and a baseline-to-integrated-build review with explicit ownership of follow-up work.

## Impact

Planning and evidence live under `docs/research/handheld-ux/` and `docs/evidence/`; recommendations target userspace and Nix image defaults. This proposal owns analysis and successor planning, not implementation of another shell, renderer, or design system. It does not reopen the archived first audit or duplicate launcher-action, recovery-navigation, card, gesture, or GPU ownership.

Reference study, native-capture critique, and annotated layouts can proceed without the board. Fresh integrated captures require the coordinator's serialized board slot; any new optical, real-finger, or startup observation needs its own recorded evidence. Existing accepted keyboard/Home observations are reusable; do not request repetition unless a changed behavior or specific evidence gap requires it.

Non-goals: webOS pixel cloning, speculative effects, battery acceptance (the device is USB-powered), new hardware enablement, AtomVM/Dozer, or claiming design recommendations are shipped. The marketing site is updated for accurate evidence and status, not redesigned as part of this round.
