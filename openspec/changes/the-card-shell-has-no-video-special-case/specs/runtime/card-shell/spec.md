## ADDED Requirements

### Requirement: Card eligibility, close, and deck-preview cost do not vary by app identity

The card shell SHALL decide whether a window becomes an ordinary,
closable card, how closing it is signaled, and how its deck thumbnail is
kept live, without inspecting the window's app_id or otherwise
special-casing any particular application. A window that reports a
fixed, non-resizable size (as mpv's `--geometry=WxH` does) MUST NOT be
excluded from ordinary-card treatment on that basis alone; only a real
transient/popup (a toplevel with a parent set) is excluded. Closing any
card SHALL send only the window's ordinary close request; the compositor
MUST NOT spawn an app-specific helper process as part of closing a card.

*Grounding: `nix/card-shell/adapter.c`'s `ordinary` command handler and
`cmd_card_shell`'s `CS_CLOSE` handling (source read); this generalizes
and replaces the app_id-keyed behavior proposed in
`video-windows-become-ordinary-cards` (its task 2.1
`card_shell_video_stop`/`SWAY_K230_CARD_VIDEO_STOP` hook is removed by
this change). Board verification of the close path (mpv actually exits,
no relaunch) is recorded under
`docs/evidence/card-shell/video-card-gestures/` or
`docs/evidence/card-shell/live-card-cost/`. <!-- UNVERIFIED: fill in the
exact evidence path once board verification for this change lands. -->*

#### Scenario: A fixed-size window becomes an ordinary card like any other

- **WHEN** an application window reports a fixed (non-resizable) size and
  has no toplevel parent
- **THEN** it receives the same ordinary-maximized, switchable, closable
  card treatment as any other application window, regardless of its
  app_id

#### Scenario: Closing a card sends only the ordinary close request

- **WHEN** a user closes any card (video or otherwise) by the swipe-up
  gesture or the persistent Close control
- **THEN** the compositor sends that window's ordinary close request and
  nothing else app-specific; whether the underlying process exits, and
  whether it relaunches anything, is entirely that application's own
  concern

### Requirement: Every card's small deck thumbnail stays live at a bounded cost

A card not currently shown at full panel size SHALL continue reflecting
its source's real, current content -- never a frame frozen indefinitely
-- while bounding the compositing cost of doing so, for every
application equally. The card shell MAY refresh such a thumbnail at a
capped rate (about 15 times per second) instead of on every single
client commit, and MAY use a cheaper resampling filter while the
overview is actively animating or being dragged, reverting to the
higher-quality filter once settled. A card currently shown at full panel
size (focused full-screen, mid-entry, or expanded) MUST always reflect
its most recent content with no rate cap.

*Grounding: `nix/card-shell/adapter.c`'s `scaled_mirror` (source read);
this generalizes and replaces the video-only frozen-thumbnail behavior
proposed in `video-windows-become-ordinary-cards` (its task 3.1). Board
timing evidence (entry-animation duration, touch latency, with a live
video and a separate busy non-video app) is recorded under
`docs/evidence/card-shell/video-card-gestures/` or
`docs/evidence/card-shell/live-card-cost/`. <!-- UNVERIFIED: fill in the
exact evidence path and measured numbers once board verification for
this change lands. -->*

#### Scenario: A busy non-video card's thumbnail never freezes

- **WHEN** a card whose application commits frequently (a game, a busy
  scrolling terminal, or a playing video) sits in the deck as a small,
  unselected thumbnail
- **THEN** the thumbnail keeps showing real, recent content -- capped to
  about 15 refreshes per second, never frozen on a single stale frame

#### Scenario: The overview stays responsive with a fast-committing card present

- **WHEN** the overview is entered, browsed, or exited while a
  frequently-committing card (video or otherwise) is present
- **THEN** the entry animation and touch handling proceed at essentially
  the same speed as with no such card present, rather than being
  dominated by that one card's recomposition cost
