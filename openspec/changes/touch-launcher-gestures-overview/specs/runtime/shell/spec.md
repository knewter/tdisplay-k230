## ADDED Requirements

### Requirement: Apps recognizes bounded single-touch paging gestures

The Apps launcher SHALL treat a single touch as a tap until its movement reaches
48 logical panel pixels. After that threshold, a horizontal gesture SHALL require
horizontal displacement at least 1.25 times its vertical displacement. A left
swipe SHALL advance one application page and a right swipe SHALL return one page;
the same touch SHALL NOT activate a card. A gesture that does not meet the
threshold or directional ratio SHALL leave the page unchanged and SHALL NOT
launch an application.

<!-- UNVERIFIED: the existing launcher records real touch contacts and deliberately
cancels activation when motion leaves a card, but these numeric gesture thresholds
and page transitions have not yet been implemented or tested on the glass. -->

#### Scenario: A horizontal swipe pages Apps

- **WHEN** a user starts one touch in the Apps card region, moves at least 48 logical pixels with horizontal displacement dominant by the stated ratio, and releases
- **THEN** Apps changes exactly one page in the swipe direction without launching the touched card

#### Scenario: A short movement remains a tap

- **WHEN** a user presses and releases within 48 logical pixels on the same card
- **THEN** the existing card action runs once and no page transition occurs

#### Scenario: A diagonal or cancelled touch is harmless

- **WHEN** movement fails the directional ratio, a second contact appears, or the compositor sends touch cancellation
- **THEN** the launcher cancels the gesture, leaves its page and applications unchanged, and remains usable

### Requirement: The launcher provides a metadata-only window overview

The launcher SHALL provide an overview mode reachable by an upward single-touch
gesture from the Apps card region using the same 48-pixel threshold and 1.25
directional ratio. It SHALL render one touch-sized card per current Sway window using
metadata such as title and application identity, focus the selected window on tap,
and return to Apps or the prior shell surface through Back or a downward gesture.
Stale or empty window state SHALL be represented visibly and SHALL not make the
launcher exit.

The first overview SHALL use text, solid surfaces, and small icons only. It SHALL
not require live window thumbnails, a compositor fork, a GPU renderer, or a
screencopy protocol. Existing persistent Windows/Home, Keyboard, Apps, Help,
Previous, Next, and Back controls SHALL remain available according to their current
contracts.

<!-- UNVERIFIED: metadata cards and the upward/downward overview gestures are a
new client behavior; existing Windows/Home evidence proves button-based focus and
Home recovery, not this overview. -->

#### Scenario: A user opens the overview

- **WHEN** a user starts in the Apps card region and completes an upward gesture meeting the threshold and directional ratio
- **THEN** the launcher shows current window cards without stealing keyboard focus from the underlying shell until a card is selected

#### Scenario: A user focuses a window card

- **WHEN** the user taps a visible metadata card
- **THEN** the corresponding running window receives focus and the overview closes or yields to that window without spawning a duplicate

#### Scenario: A user leaves the overview

- **WHEN** the user taps Back or completes a downward gesture meeting the threshold and directional ratio
- **THEN** the overview closes and Apps or the prior shell surface remains usable

#### Scenario: Window metadata changes during overview

- **WHEN** a listed window exits or no windows remain before selection
- **THEN** the overview refreshes to an explicit empty or stale-safe state, and Back remains available

### Requirement: Gesture transitions preserve shell fallbacks and bounded rendering

A gesture transition SHALL complete or cancel within 200 milliseconds of its
release, SHALL not leave a half-open overlay after a rendering or input error, and
SHALL preserve the existing button paths for Previous, Next, Back, Apps,
Windows/Home, Keyboard, Help, Terminal, Monitor, and system controls. The client
SHALL remain keyboard-non-interactive while it is an app chooser or overview so
that the existing terminal keyboard path is not displaced.

<!-- UNVERIFIED: the 200 ms transition and Pixman frame cost require measured
client evidence; current shell timing only measures ordinary Sway scene/KMS work. -->

#### Scenario: A transition exceeds its frame budget

- **WHEN** the client cannot render a gesture transition within its bounded timeout
- **THEN** it settles on the previous or destination page, releases input state, and leaves button navigation usable

#### Scenario: A user uses a button instead of a gesture

- **WHEN** the user taps Previous, Next, Back, Windows/Home, Keyboard, Help, Terminal, Monitor, or a system control
- **THEN** the existing button behavior remains available regardless of gesture state
