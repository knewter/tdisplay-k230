## Context

The shell is a portrait Sway/Pixman session on a 568x1232 panel with Foot, a persistent touch bar, wvkbd, desktop-entry discovery, and native launcher/window controls. Repository evidence shows a visible shell handoff around 72.6–72.7 seconds in one camera audit, a 568x1232 Sway tree, injected Apps/overview matrices, keyboard show/hide and Home recovery, and installed video playback with injected Back/Stop/Home/EOF checks. Those artifacts also state their limits: injected input is not real-finger proof, native images are not optical readability proof, and orientation/latency/continuity claims require narrower evidence.

The existing `touch-launcher-gestures-overview` proposal owns gesture classification and metadata-card behavior. The active `the-shell-has-a-card-composition-plan` and `the-shell-manages-apps-as-cards` work own card architecture and app lifecycle respectively. This plan supplies the cross-surface contract and routes work to those owners rather than duplicating their implementation.

## Goals / Non-Goals

**Goals:**

- Give design review one evidence ledger spanning boot, first use, discovery, visual hierarchy, touch, navigation, keyboard/focus, media/system states, errors, motion, and accessibility.
- Define reusable visual and interaction principles that can be measured on the 568x1232 portrait surface.
- Separate current observations from proposed behavior and label board-dependent work explicitly.
- Produce a small P0/P1 backlog with parallel host work and serialized board gates.

**Non-Goals:**

- No launcher, compositor, Nix, desktop-file, boot, video, or accessibility implementation in this change.
- No claim that the current shell is webOS or that Palm webOS behavior has been reproduced. webOS is an interaction benchmark for continuity, cards, and reversible navigation only.
- No assumption of rotation support, GPU composition, live thumbnails, user interviews, or new hardware capability.
- No replacement of the existing Apps/Windows/Keyboard/System/Home controls while the card proposals are under review.

## Decisions

1. **Use one outside-in journey map.** Start with boot feedback and the first successful app launch, then cover repeat navigation, keyboard-visible work, video/system states, and recovery. This exposes cross-surface inconsistencies that component specs miss. Evidence links point to `docs/evidence/splash-initial-scene-ready/video-audit.md`, `docs/evidence/network-video/installed-app/README.md`, `docs/evidence/network-video/installed-controls/README.md`, and the launcher/keyboard evidence reports.

2. **Use an evidence ladder.** Host source/tests establish structure and deterministic state behavior; native screenshots establish intended composition; injected board runs establish routing and cleanup; camera captures establish visible physical results; focused real-finger captures establish touch and reachability. A lower rung cannot substitute for a higher one. Missing rungs remain `UNVERIFIED`.

3. **Define tokens before polishing cards.** The successor visual-system work should record a small spacing scale, text roles, minimum contrast checks, focus/pressed/error treatments, and target geometry in panel pixels. It must test with the keyboard visible and hidden. This is a shared contract for the card-composition and app-card owners, not a second card renderer.

4. **Preserve explicit navigation fallbacks.** Every gesture route has a button/Back/Home path. The card owners decide gesture thresholds and overview state; the UX plan checks that Apps, Windows, Keyboard, System, Back, Home, and video Stop remain discoverable and composable. A card or overview surface must close or yield before focusing an application.

5. **Treat transient states as first-class screens.** Loading, empty, stale, launch failure, network failure, EOF, cancellation, and cleanup each need a visible status and a bounded recovery path. The network-video proposal owns player lifecycle; this plan owns whether the resulting state is understandable and returns to the shell.

6. **Budget motion for Pixman.** Existing feasibility evidence reports restrained scene-build/KMS timings and recommends solid cards, limited buffers, and short transitions. The card proposal owns implementation and performance measurements; this plan requires a fixed duration/frame budget, immediate settle fallback, and a board camera check before calling motion usable.

7. **Use Palm webOS as a comparison lens.** Evaluate continuity of cards, reversible navigation, and visible state transitions against the benchmark, while retaining this shell's Sway, layer-shell, keyboard, and persistent-bar constraints. Do not import webOS-specific assumptions about gestures, thumbnails, or compositor ownership.

## Risks / Trade-offs

- [A broad audit becomes an unprioritized redesign] → keep a severity-ranked ledger, assign P0/P1 successors, and require one narrow proof command per task group.
- [Injected tests overstate touch usability] → require focused physical-finger camera evidence for gestures and reachability and keep injected results separately labelled.
- [Visual tokens conflict with card implementation] → publish the shared contract first; card architecture and app lifecycle owners consume it through explicit dependencies.
- [More visible state text consumes the small portrait surface] → measure keyboard-visible layouts and prefer short labels, stable placement, and existing bar controls before adding overlays.
- [Animating beyond CPU budget] → cap motion and use an immediate final frame; defer thumbnails, blur, and compositor changes until measured.
- [First-boot or rotation gaps are mistaken for completed features] → retain `UNVERIFIED` markers and require board evidence for boot timing, optical readability, orientation, and real-finger behavior.

## Migration Plan

1. Land this planning change and its evidence ledger on master.
2. Run host source/fixture checks and reconcile the ledger with the existing card composition and app-card proposals.
3. Create successor proposals for P0 onboarding/recovery and visual/state consistency; allow host-only source and fixture work in parallel with card model work.
4. Reserve serialized board sessions for final boot, optical readability, touch reachability, keyboard/focus, and motion captures. If a successor regresses, retain the persistent bar and disable only the new surface or gesture path.

## Open Questions

- Which existing onboarding/splash proposal should own the first-boot instructional copy after the ledger identifies its exact gap?
- Whether a future overview needs compositor screencopy remains deferred until metadata cards and measured Pixman cost are accepted.

## Current user-flow matrix and issue ledger

The first planning pass records these flows as the review baseline; completion is not implied by the evidence labels.

| Flow | Person-facing task | Current evidence | Open acceptance |
|---|---|---|---|
| Boot to shell | See a continuous handoff and identify the first action | Camera audit brackets shell appearance at about 72.6–72.7 s; portrait shell native frame exists in `docs/evidence/splash-initial-scene-ready/video-audit.md` | `UNVERIFIED`: fresh power-on continuity, first-use instruction, optical readability |
| Discover and launch | Open Apps, understand desktop-entry labels, launch and return | Installed Apps/video report records injected catalog launch; launcher tests cover catalog/navigation | `UNVERIFIED`: real-finger discovery, label hierarchy, reachability |
| Switch and recover | Use Windows/overview, Back/Home, and retain bar controls | Card proposal and injected matrices describe controls; video controls report injected Stop/Home/Back/EOF cleanup | `UNVERIFIED`: physical card gesture, focus clarity, stale/empty visual states |
| Type and focus | Show/hide keyboard without losing focus or shell recovery | Keyboard show/hide and Home recovery reports plus launcher/menu tests | `UNVERIFIED`: finger reachability, readable keyboard-visible content, focus indication |
| Watch and recover | Observe loading/progress, stop, EOF, network failure, and return | Installed video evidence proves sustained software playback and injected controls; network/MVX gates remain separate | `UNVERIFIED`: final image network failure messaging, MVX fallback presentation, error comprehension |

| Priority | Issue | Evidence / gap | Recommended owner and next proof |
|---|---|---|---|
| P0 | No single first-use contract joins boot handoff, primary action, Apps, Help, and recovery | Splash and shell evidence are separate; no first-use camera task is claimed | New onboarding/recovery proposal; host flow review, then one board camera session |
| P0 | State vocabulary and recovery affordances need one cross-surface contract | Video evidence has cleanup controls, while catalog/keyboard/card states have separate paths | New visual/state consistency proposal; fixture matrix, then injected and physical error capture |
| P1 | Card navigation needs shared visual/focus/motion rules | Existing `touch-launcher-gestures-overview` and card proposals own mechanics/architecture | Existing card owners consume this contract; host model tests, then focused finger capture |
| P1 | Touch target, typography, contrast, and keyboard-visible reachability lack optical proof | Native 568x1232 geometry exists; injected tests do not prove glass usability | Visual-system successor; native measurements, then camera/real-finger acceptance |
| P1 | Orientation and advanced effects are not evidenced | Current evidence is portrait; feasibility warns against unmeasured GPU/full-screen effects | Keep `UNVERIFIED`; no implementation until source/board evidence justifies it |

This ledger is intentionally a planning artifact. It does not convert the existing injected video, launcher, keyboard, or splash captures into real-finger acceptance.
