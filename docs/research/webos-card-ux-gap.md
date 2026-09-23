# webOS card UX: clarified target and current gap

Date: 2026-09-23

## What the target means

The target is a card-based application interaction, rather than a launcher that
only labels windows. The reviewed visual reference is the Palm webOS user guide,
pages 25–26: [Palm Pre User Guide (English PDF)](https://support.bell.ca/_web/guides/User-Guides/Mobile/PalmOne/Palm-EN/palm_pre_userguide_en(en).pdf).
Those pages were reviewed as images by the project maintainer. This note records the
resulting product intent; it does not claim that the current shell implements the
reference interaction.

The desired interaction is:

1. Enter a global application deck from the running application, while retaining a
   coherent launcher and keyboard story.
2. Show visual application cards rather than text-only metadata rows.
3. Let a card track the user's finger during the interaction instead of deciding its
   destination only after release.
4. Move to an adjacent card by swiping, then expand the chosen card back into its
   application.
5. Dismiss an application by throwing its card away, with deliberate close semantics
   and recovery when that application cannot close cleanly.

The intended user-visible acceptance sequence is therefore: **app -> shrink to a
card -> swipe to an adjacent card -> expand it, or dismiss a thrown card**. The
launcher, on-screen keyboard, terminal recovery, and button paths must remain
consistent through that sequence; the card deck cannot become a separate UI that
breaks those existing routes.

## What exists now

`nix/touch-launcher/touch-launcher.c` implements a bounded layer-shell launcher. It
recognizes one touch by a 48-pixel threshold and direction ratio, then begins a
pre-rendered transition after release. Horizontal motion changes Apps pages; an
upward release opens a Windows view; a downward release leaves it. The Windows view
uses Sway tree metadata (title, app ID, and state), revalidates an ID, and yields the
launcher before requesting focus.

That is useful launcher behavior, but it is not an interactive card deck:

- cards are full-width text controls, not rendered running-app surfaces;
- no card follows the finger while it moves;
- there is no shrink-from-app or expand-to-app transition;
- there is no throw-to-close gesture, close affordance, or close lifecycle;
- gestures exist only while the launcher overlay is open and begin in its card area,
  so there is no global gesture from an arbitrary running application;
- the implementation intentionally omits live thumbnails, screencopy, multitouch,
  inertial physics, and compositor-wide policy.

The observed release-classified transition has a bounded 120 ms animation path. That
timing and the injected swipe evidence establish neither finger-tracking quality nor
the visual continuity needed for the target sequence.

## Next investigation before a broader proposal

Do not assume that VGLite or another GPU path is the answer. First establish the
capability boundary in the existing Sway/wlroots architecture:

1. Can it expose a safe, correctly synchronized representation of each eligible
   application for a card without taking a second DRM owner or leaking protected
   content?
2. Can the card surface receive and hand back touch/keyboard focus while preserving
   the existing launcher, keyboard, and terminal recovery contracts?
3. Can it animate shrink, finger tracking, adjacency, expand, and dismissal within a
   measured frame and memory budget on RGB565/Pixman, or is renderer/compositor work
   required?
4. What Sway command and application lifecycle contract can request a close, observe
   refusal/exit, and restore a usable deck?

Only those answers can define whether the work remains a client extension, needs a
wlroots/Sway integration, or needs a new rendering path. No broader card-UX proposal
has been created yet. The existing `touch-launcher-gestures-overview` change remains
its own bounded metadata-overview work; its requirements, tasks, and status are not
changed by this research note.
