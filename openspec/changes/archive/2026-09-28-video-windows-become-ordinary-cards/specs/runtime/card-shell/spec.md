## ADDED Requirements

### Requirement: A video playback window is an ordinary, closable card

Network video windows (`k230-video-software`, `k230-video-mvx`) SHALL receive
the same ordinary-maximized card treatment as any other coherent-shell
application: full panel size, present in the overview, reachable by the
bottom-edge switch gesture, and closable by the same swipe-up-to-close every
other card uses. A video window MUST NOT be a small floating window with no
card and no close affordance while the coherent card shell is active.

Closing a video card SHALL also stop the underlying player session (not only
send the window's own close request), so the session controller cannot
mistake a requested close for a decode failure and relaunch a fallback
player. Closing a video card MUST NOT leave an orphaned player process.

A video card's deck-sized thumbnail MAY stop tracking every newly decoded
frame while the card is not shown at full panel size, provided it still
reflects a real captured frame of that session (not a placeholder) and
resumes live updates whenever the card is shown at full panel size again
(focused full-screen, mid-entry, or expanded).

*Grounding: `nix/card-shell/adapter.c`'s prior "video and transient views
stay unmarked" exclusion and `nix/shell.nix`'s prior unconditional floating
`for_window` rules for both video app IDs (source read, not board evidence
of the fix). The unclosable-video board observation itself is recorded in
the coordinator's session notes for this change; QEMU regressions proving
card membership, switch/close reachability and no orphaned process are
recorded under `docs/evidence/card-shell/video-card/`. Decoded-frame
presentation and physical touch remain `runtime/video`'s existing board
evidence and are not re-proven here.*

#### Scenario: A video card appears in the overview like any other app

- **WHEN** the coherent card shell enters the overview while a video window
  is mapped
- **THEN** the video window appears as an ordinary card in the deck at the
  same size and position rules as any other application's card

#### Scenario: A bottom-edge swipe switches away from a playing video

- **WHEN** a video card is focused full-screen and the user performs the
  bottom-edge app-switch gesture
- **THEN** the gesture behaves identically to switching away from any other
  application: the video card becomes reachable in the deck, and its own
  playback is not a special case in the gesture-handling code path

#### Scenario: Swipe-up-to-close stops the player, not just the window

- **WHEN** a user throws a video card upward to request its close
- **THEN** the window's ordinary close request is sent, the video-session
  controller is separately asked to stop, and no player or controller
  process remains running for that session once the close completes

#### Scenario: An unfocused video card's thumbnail does not chase every frame

- **WHEN** a video card is visible only as a small, unselected deck
  thumbnail while its player keeps decoding
- **THEN** the card's mirrored thumbnail may remain on its most recently
  captured frame rather than rescaling on every new decoded frame, and
  resumes tracking live frames once the card is shown at full panel size
