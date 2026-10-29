# runtime/shell-themes Specification

## Purpose
The userspace shell applies resolved theme roles to Settings and notification
Shade surfaces, reports unsupported roles explicitly, and restores their colors
when a shared appearance transaction rolls back.

## Requirements

### Requirement: Settings and notifications honor the active theme

Grounding: `docs/evidence/omarchy-themes/settings-notifications-themed/board/README.md` records the physical dark/light Settings and Shade presentation, named compatibility reports and forced rollback on the same Rust renderer.

The system SHALL make the Rust shell's Settings and notification Shade surfaces read
the active generation's resolved colors the same way the shell, drawer, and
card renderers already do, and repaint on the existing commit/rollback
signal `theme_transaction.py`'s receiver fan-out already sends. It SHALL
report their coverage in the existing `applied`/`adapted`/`unavailable`/
`unknown` compatibility view by name, rather than silently inheriting
hardcoded defaults, per `the-shell-loads-omarchy-themes`'s own
"Compatibility and physical completion are explicit" requirement. This
requirement adds no new palette role: it wires up `theme_tokens.py`'s
existing `sections["controls"]`/`sections["notifications"]` output.

#### Scenario: A theme with an explicit notifications section activates
- **WHEN** a person activates a theme whose source supplies a
  `notifications` section (or relies on documented fallback) and a
  notification is shown
- **THEN** the notification surface's colors match the active generation's
  resolved `notifications` section, and the compatibility report names it
  `applied` or `adapted` rather than silently defaulting

#### Scenario: Settings reflects the active theme after a swap
- **WHEN** a person opens Settings after switching themes
- **THEN** its rendered surface shows the newly active generation's colors without a restart, and a
  subsequent rollback restores the previous generation's colors on the
  same surface

#### Scenario: A surface has no themeable equivalent
- **WHEN** Settings or notifications turns out to have no rendered surface
  for a given palette role
- **THEN** the compatibility report names that role `unavailable` rather
  than omitting it or claiming coverage

#### Scenario: `--surface system` is exercised
- **WHEN** `python3 tests/test_handheld_theme_rendering.py --surface
  system` runs against a built package
- **THEN** it asserts every Settings/notifications role named above and
  fails rather than skips on an unimplemented one

### Requirement: An unchanged theme checkout is a usable source

<!-- UNVERIFIED -->
The system SHALL accept a community theme repository root or a theme within an Omarchy built-in collection without conversion, extra manifests, or edits to source files. Generated output and preferences MUST remain outside that checkout. Refresh SHALL detect changed contents and SHALL NOT execute theme code or alter the source revision. A failed refresh SHALL preserve the last valid generation.

#### Scenario: Clone then select
- **WHEN** a person selects a valid unchanged Quattro theme checkout
- **THEN** the system loads its appearance and assets and leaves its tracked and untracked source files unchanged

#### Scenario: Update the checkout
- **WHEN** a person updates that clone and refreshes the selected theme
- **THEN** changed colors and assets appear together or the previous valid appearance remains with a useful error

#### Scenario: Use the familiar swap command
- **WHEN** a person places an unchanged clone under `~/.config/omarchy/themes/NAME` and runs `omarchy-theme-set NAME`
- **THEN** the handheld adapter applies that theme through the same appearance path used by its touch chooser, without requiring the Omarchy desktop

### Requirement: All theme colors and applicable appearance overrides are honored

<!-- UNVERIFIED -->
The system SHALL preserve authored palette keys and reproduce the pinned Quattro alias, precedence, derived-color, mode, template, full-file, section-replacement, and machine-override behavior. Applicable surface colors, gradients, transparency, border widths, control states, typography and spacing SHALL reach their corresponding handheld surfaces. Touch geometry adaptations MUST be visible in the compatibility report; themes MUST NOT replace gesture navigation.

#### Scenario: A theme supplies more than ANSI colors
- **WHEN** a theme supplies distinct semantic, ANSI, selection, custom, and gradient values plus section overrides
- **THEN** the corresponding shell, drawer, card, keyboard and app appearance adapters retain their intended distinctions instead of reducing them to a small shared palette

<!-- Settings/notifications adapters moved 2026-09-28 (user-authorized scope
split, "yes a-d and f"): that portion of this scenario is now
`the-settings-and-notifications-surfaces-are-themed`'s own "Settings and
notifications honor the active theme" requirement, not this change's. -->

#### Scenario: A section override replaces defaults
- **WHEN** a theme supplies a complete shell file and a partial section file
- **THEN** full-file replacement precedes section replacement, missing section values use documented consumer fallbacks, and machine override keys win last

### Requirement: Theme icons and background choices remain available

<!-- UNVERIFIED -->
<!-- Narrowed 2026-09-28 (user-authorized scope split, "yes a-d and f"):
user-supplied overlays, non-crop fit modes (fill/solid), and bounded video
playback moved to `the-background-chooser-supports-fill-solid-and-video`'s
own "Every promised background fit mode exists" and "A video-suffixed
background plays, muted and bounded" requirements. This requirement keeps
only what this change itself still owns: icon fallback and the still-image,
crop-only background carousel with selection memory (implemented; see task
4.2.r/4.2.r2). -->
The system SHALL resolve `icons.theme` through installed freedesktop themes with explicit missing-theme fallback. It SHALL list all background candidates from the theme's own source, and support upstream still-image formats. Selection SHALL remember each theme's wallpaper across switches and boots. Portrait crop preview, empty-directory fallback and removed-file recovery SHALL remain usable by touch.

#### Scenario: Choose another background
- **WHEN** a person browses the background carousel (by drag or a side-slice tap) and confirms a different image (by tapping the centred slice or Apply)
- **THEN** the actual portrait preview and shell change to that image, other choices remain available, and the chosen image returns after switching away and back or rebooting

#### Scenario: An icon theme is missing
- **WHEN** a clone names an icon theme that the image does not contain
- **THEN** apps retain recognizable fallback icons and text labels and the missing icon dependency is identified

### Requirement: The theme chooser shows each theme's own imagery

<!-- UNVERIFIED -->
The touch chooser SHALL present each catalog entry as a full-image carousel slice, matching the horizontal Cover Flow layout of Omarchy's own picker (`shell/plugins/image-picker/ImagePicker.qml`, shared by `omarchy-theme-switcher` and `omarchy-theme-bg-switcher`): one large expanded centre slice with skewed side slices either side, browsed by drag or a side-slice tap and confirmed by tapping the centred slice or an explicit Apply. Each slice's imagery SHALL be sourced from that theme's own preview image when the source provides one, and otherwise a representative background image chosen by the same fallback rule Omarchy's picker uses (its first background asset, not a fabricated substitute). A theme with neither a preview image nor a background asset SHALL show a plain placeholder slice rather than an invented image. The background chooser SHALL show the same carousel treatment for each background candidate.

#### Scenario: A theme ships its own preview image
- **WHEN** a theme's source directory contains a supported preview image
- **THEN** that theme's carousel slice shows imagery decoded from that exact file, whether the slice is centred or a side slice

#### Scenario: A theme ships no preview image
- **WHEN** a theme has no preview file but does have background images
- **THEN** that theme's carousel slice shows imagery derived from that theme's first background image, sorted the same way Omarchy's own picker selects one

#### Scenario: A theme ships neither
- **WHEN** a theme has no preview image and no background image
- **THEN** its carousel slice shows a plain placeholder instead of imagery, and remains fully usable by touch (browsable and confirmable) all the same

### Requirement: Theme activation is coordinated and recoverable

<!-- UNVERIFIED -->
The system SHALL validate a new appearance before activation, coordinate its shell surfaces as one generation, and provide touch preview, cancel, apply and rollback. App-specific reload or restart limitations SHALL be reported without closing running work automatically. Invalid assets or appearance settings MUST NOT strand the recovery app or corrupt the active theme. Fresh homes SHALL receive a working pinned default from the Nix image without restored user state.

#### Scenario: Cancel a preview
- **WHEN** a person cancels theme preview or its activation fails
- **THEN** the prior colors, icons and background are restored and the existing app session remains usable

#### Scenario: Boot with no saved preferences
- **WHEN** the image boots with a fresh home and no valid saved theme generation
- **THEN** it displays the declared default theme and exposes a usable chooser and recovery route

#### Scenario: Boot after a selected source is removed
- **WHEN** the selected user theme source is unavailable but its saved generation remains valid
- **THEN** the system retains that generation and its selected wallpaper, exposes a usable chooser and recovery route, and does not require the source checkout to restore the appearance

### Requirement: Compatibility and physical completion are explicit

<!-- UNVERIFIED -->
The system SHALL classify every palette key, override and asset as applied, adapted, unavailable or unknown with a reason. Existing handheld surface omissions SHALL remain implementation gaps rather than full-compatibility claims. Absent surfaces, hardware and apps SHALL be distinguished from gaps. Completion MUST include unchanged-checkout host fixtures and an explicit disposition of physical screenshots, touch observations, performance measurements, reboot and recovery evidence. Existing device evidence and recorded operator acceptance MAY satisfy implemented-behavior acceptance when the operator explicitly waives additional collection. Waived recordings, unmeasured costs and unobserved individual boot cases MUST remain identified as UNVERIFIED; a waiver MUST NOT close missing consumer implementation.

Evidence and limits: `docs/evidence/omarchy-themes/compatibility-closeout-2026-10-10.md`, `docs/evidence/omarchy-themes/consumer-closeout-2026-10-10/README.md` and `docs/evidence/omarchy-themes/accepted-closeout-2026-10-10/README.md` retain the field inventory, source/license attribution, distinct host/board classes and explicit waiver. Individual unobserved physical cases and unmeasured costs remain UNVERIFIED.

#### Scenario: A theme targets absent desktop features
- **WHEN** a theme includes lock assets, RGB keyboard data, desktop Lua or colors for an app absent from the image
- **THEN** its source remains intact and the compatibility view explains those boundaries while showing which handheld appearance settings were applied

#### Scenario: Only a parser test has passed
- **WHEN** upstream fixture comparisons pass without a device trial
- **THEN** the change continues to identify physical usability and performance as unverified

### Requirement: Tapping a theme or background applies it immediately, with no separate preview-then-Apply step

<!-- Grounding: user decision (2026-09-25, verbatim): "i don't really think
     we need an 'apply' window for themes at all. tap theme in the theme
     picker, apply immediately, so i can compare them easily." This
     replaces the chooser's earlier two-page, tap-to-preview-then-tap-
     Apply/Cancel flow with a single page: the theme carousel, the active
     theme's own background carousel below it, and a plain "Current
     theme"/"Current background" label under whichever slice of each is
     centred and durably active. The two-phase prepare/commit/rollback
     protocol, the pre-render-ahead-of-Apply and prepare-ahead-of-a-likely-
     Apply mechanisms, and the optimistic-show requirement below are all
     unchanged by this requirement -- only what triggers them moved, from a
     separate Apply button to the carousel tap itself. Proof:
     nix/rust-shell-client/src/theme_ui.rs (`ThemeView::tap_theme`/
     `tap_background`/`advance`/`accept`, and their own unit tests) and
     tests/rust_theme_chooser_qemu.py. Background generation correction and
     injected physical-board Home captures:
     docs/evidence/theme-picker/background-selection/README.md. -->

*Grounding: user decision of 2026-09-25 (comment above); `nix/rust-shell-client/src/theme_ui.rs` and its unit tests; board apply trials on installed system `298a2bf6` in `docs/evidence/theme-picker/board-session-2026-10-12b/README.md` ("Task 6.6" and "Install of candidate 8"): a centre tap activates directly, with no preview request. Operator acceptance 2026-10-12: "it's great now i tried it all it's good". Taps in those trials were injected.*

The theme chooser SHALL present the theme carousel and the active theme's
own background carousel on one page, with no separate preview page and no
Apply/Cancel footer. A tap on a carousel's own already-centred slice SHALL
apply that theme or background immediately, through the same
`preview`(learn the generation)/`activate` request pair an explicit Apply
button previously sent, chained automatically with no further tap needed.
Dragging or tapping an off-centre slice SHALL only recentre the carousel on
that slice; it SHALL NOT itself apply anything. Rapid taps across different
targets SHALL coalesce onto the most recently tapped one: at most one
request for this chooser SHALL be in flight at a time, a reply that no
longer matches the most recently tapped target SHALL be discarded rather
than shown or applied, and the chooser SHALL move on to the now-desired
target as soon as that discarded reply is recognised, with no queue of
stale, superseded activations ever building up or later firing.

#### Scenario: Tapping the centred theme slice applies it with no further tap

- **WHEN** a person taps the theme carousel's own already-centred slice
- **THEN** that theme is applied immediately (through the existing
  `preview`/`activate` pair, and the existing optimistic-show path when the
  receiver already has it prepared), with no separate confirm or Apply step

#### Scenario: Tapping the centred background slice applies it with no further tap

- **WHEN** a person taps the active theme's own background carousel's
  already-centred slice
- **THEN** that background is applied immediately, the same way, without
  navigating to a different page first

#### Scenario: Dragging or tapping off-centre only browses

- **WHEN** a person drags either carousel, or taps a slice that is not
  already centred
- **THEN** the carousel only recentres on that slice; nothing is applied,
  and no `activate` request is sent

#### Scenario: A tap on a not-yet-prepared theme shows a brief busy state in place

- **WHEN** a person taps a theme or background the receiver has not already
  prepared
- **THEN** that slice shows a brief, in-place busy indicator while it
  applies, and the carousel itself remains visible and draggable the whole
  time -- the tap never blocks or hides the carousel

#### Scenario: Rapid taps across different themes coalesce onto the last one

- **WHEN** a person taps a theme, and before that tap's own request has
  settled taps a different theme
- **THEN** the first theme's own request, if already sent, is still
  answered but its reply is discarded rather than applied; the chooser
  applies the second, most recently tapped theme instead, and at no point
  does the first one become the active theme

#### Scenario: A failed apply rolls back with a visible, in-place error

- **WHEN** a tap-applied theme or background's durable commit fails
- **THEN** the chooser rolls back to the previous appearance, exactly as
  the optimistic-show rollback already does, and shows a specific, visible
  error in place, with no separate footer or dialog needed to see it

### Requirement: A theme swap does not pay Python start-up on the hot path

<!-- Grounding: docs/evidence/omarchy-themes/background-decode-cache-qemu/README.md
     (board PYTHONPROFILEIMPORTTIME breakdown) for the cost being removed;
     docs/evidence/omarchy-themes/theme-swap-jank/README.md and
     tests/test_theme_helper_daemon.py for this requirement's own proof. -->

*Grounding: `docs/evidence/omarchy-themes/background-decode-cache-qemu/README.md` for the removed cost; `docs/evidence/omarchy-themes/theme-swap-jank/README.md` and `tests/test_theme_helper_daemon.py`; board journals in `docs/evidence/theme-picker/board-session-2026-10-12b/README.md` show each Apply handled by the resident `helperd` (`THEME_TIMING helperd activate`).*

When the persistent theme helper (`theme-helper.service`) is running, a
`k230-theme preview` or `k230-theme activate` invocation SHALL NOT import
the theme-activation module chain (`theme_activate`, `theme_transaction`,
`theme_preferences`, `keyboard_appearance`) in its own process; that
invocation SHALL instead delegate the request to the already-warm helper
process over a private, owner-only Unix socket and print exactly the
answer that helper computed. The invocation SHALL fall back to the
unmodified, pre-existing in-process behavior, with no difference in
accepted flags, output shape, or exit codes, whenever the helper socket is
absent, refuses the connection, or does not answer within a bounded
timeout.

#### Scenario: The helper is running

- **WHEN** `theme-helper.service` is active and a person's chooser calls
  `k230-theme preview <id>` then `k230-theme activate <id>
  --expected-generation <g>`
- **THEN** both calls are served by the existing helper process and never
  start a second Python interpreter's worth of theme-activation imports

#### Scenario: The helper is not running

- **WHEN** `theme-helper.service` is stopped, crashed, or mid-restart
- **THEN** `k230-theme preview`/`k230-theme activate` still complete
  correctly, using the same two-phase prepare/commit/rollback protocol and
  producing the same result shape as before this requirement existed

#### Scenario: A malformed or unexpected request reaches the helper

- **WHEN** the helper receives a request it cannot parse or act on
- **THEN** it reports that one request as a failure and continues serving
  every later request without needing a restart

### Requirement: Commit adopts an already-prepared candidate instead of redoing its work

<!-- Grounding: nix/rust-shell-client/src/background_decode.rs (BackgroundCache,
     a bounded in-memory LRU) and nix/card-shell/appearance.c/adapter.c
     (the `prepare` callback and `appearance_canvas_refresh`'s adopt path),
     both read; tests/background_decode_module.rs and
     tests/test_card_shell_appearance.py for this requirement's own proof. -->

*Grounding: `tests/background_decode_module.rs` and `tests/test_card_shell_appearance.py`; board journals in `docs/evidence/theme-picker/board-session-2026-10-12b/README.md` show `activate_generation ... prepare_phase=0.1-3.9ms warm=2 targets=2` and `appearance-commit-accepted reused=optimistic`.*

Each of the two appearance receivers (the Rust chooser/wallpaper client and
the Sway/card-shell compositor) SHALL retain, in memory, the decoded
wallpaper or built gradient for at least the most recently prepared
candidate generations (bounded, not unbounded), so that a `commit` for any
of those candidates adopts the already-prepared result -- a buffer/pointer
swap plus redraw -- rather than re-decoding a wallpaper or repainting a
gradient. A candidate that was never prepared, or whose prepared state was
evicted or does not match the commit's own generation/geometry, SHALL fall
back to the pre-existing inline decode/paint; this requirement never
changes what is rendered, only whether that work is repeated.

#### Scenario: A previously prepared candidate is committed

- **WHEN** a generation was prepared (directly, or via the chooser's
  browse-ahead warm-up) and nothing since has evicted its retained state
- **THEN** the matching `commit` adopts that retained wallpaper/gradient
  without a fresh decode or Cairo paint

#### Scenario: Browsing a second candidate does not evict the first

- **WHEN** a person previews candidate A, then candidate B, while A has not
  yet been committed
- **THEN** a later `commit` for A is still a guaranteed in-memory hit,
  bounded to a small recent-candidate history rather than a single slot

#### Scenario: An unprepared or superseded candidate still commits correctly

- **WHEN** `commit` arrives for a generation that was never prepared, or
  whose prepared geometry/brush no longer matches
- **THEN** the receiver falls back to its existing inline decode/paint and
  the commit still succeeds

### Requirement: The chooser warms a candidate ahead of a likely Apply

<!-- Grounding: nix/rust-shell-client/src/theme_ui.rs (poll_prepare_ahead/
     prepare_ahead_submitted/prepare_ahead_reply) and main.rs's per-tick
     carousel-settle hook, both read; theme_ui.rs's own unit tests for this
     requirement's proof. -->

*Grounding: `nix/rust-shell-client/src/theme_ui.rs` unit tests; board cold-open neighbour check in `docs/evidence/theme-picker/board-session-2026-10-12/README.md` (second theme warm about 0.3 s after the first, not a fresh ~4 s preview).*

While the Themes list page is open and its carousel is at rest (no drag,
coast, or settle animation in progress) on one theme for a short, bounded
dwell time, the chooser SHALL issue a best-effort warm-up request for that
theme, bounded to a small number of requests in flight at once, without
navigating the chooser or otherwise becoming visible to the person browsing.
A theme passed through while the carousel is still moving, or superseded by
a different centred theme before its own dwell time elapses, SHALL NOT
itself cause a warm-up request.

#### Scenario: Dwelling on a theme warms it

- **WHEN** a theme stays the carousel's centred item, at rest, for the
  chooser's debounce interval
- **THEN** a warm-up request for that theme is issued, and its reply never
  changes the chooser's displayed page, list, or preview state

#### Scenario: A fast flick warms nothing per slice

- **WHEN** the carousel is dragged or coasting across several themes
  without settling
- **THEN** no warm-up request is issued for any theme only passed through

#### Scenario: The already-active theme is never warmed

- **WHEN** the carousel settles on the theme that is already active
- **THEN** no warm-up request is issued, since there is nothing to prepare

### Requirement: A warm Apply shows the new appearance ahead of the durable commit

<!-- Grounding: user decision (2026-09-25 coordinator message): "The user
     has explicitly approved the optimistic theme apply." Justification:
     board evidence (docs/evidence/omarchy-themes/instant-theme-swap/
     board-chooser-2026-09-25.md) showed tap-to-commit at 397 ms even after
     removing the redundant re-prepare, still short of the user's original
     ~100 ms target ("theme swaps should be instant"), with the remaining
     cost inside the durable two-phase commit's own pointer-swap,
     preference, and app-sync work -- none of which the receivers'
     already-prepared, already-validated resources need to wait on merely
     to be drawn. Proof: nix/rust-shell-client/src/main.rs
     (`should_apply_optimistically`, `optimistic_apply_due`,
     `show_theme_optimistically`), nix/card-shell/appearance.c (the `show`
     phase), and their own tests. "Apply tap" below now means a tap on the
     theme or background carousel's own already-centred slice (see "Tapping
     a theme or background applies it immediately", above) rather than a
     since-removed separate Apply button; the mechanism this requirement
     describes -- what the receiver does once that tap's own `activate`
     request is dispatched -- is unchanged by that later decision. -->

*Grounding: user decision of 2026-09-25 (comment above); board apply trials in `docs/evidence/theme-picker/board-session-2026-10-12b/README.md`: tap-up to shown frame 27.5-42.2 ms with `prerendered=true`, ahead of a durable activation of 149-179 ms, including one trial on installed system `298a2bf6`. Operator acceptance 2026-10-12: "it's great now i tried it all it's good". Taps were injected.*

When an Apply tap's target generation is already the Rust receiver's own
`prepare`d snapshot, the chooser SHALL render that appearance -- the
wallpaper, and every other Rust-shell surface driven by it -- on the very
next frame, without waiting for the durable two-phase commit (still
dispatched, unchanged, and left to settle to completion asynchronously).
This SHALL NOT alter the two-phase protocol's own acknowledgement contract
in any way: a receiver's `prepared`/`active` bookkeeping, and the "ack only
after a real, flushed frame" rule each receiver's `commit`/`rollback`
handling already applies, remain exactly as before this requirement: the
optimistic render is a side effect additional to that protocol, never a
substitute for its own eventual, authoritative commit or rollback. A
generation that is not already prepared SHALL continue to show the
pre-existing busy/pending state on Apply and SHALL NOT be prepared early
merely to make it eligible for this requirement. When the compositor can be
reached directly, the same already-prepared candidate MAY also be shown
there immediately, on the same advisory, side-effect-only basis (never
altering its own two-phase bookkeeping either); this is a best-effort
optimization, not a correctness requirement in its own right, since the
durable commit's own real `commit`/`rollback` message to the compositor
settles its display correctly regardless of whether this arrives.

#### Scenario: An already-prepared Apply shows on the next frame

- **WHEN** a person taps Apply for a theme the chooser has already prepared
  (by browsing to it, by prepare-ahead of a carousel neighbour, or by a
  previous identical Apply) and the wallpaper surface is ready for a new
  frame
- **THEN** the new appearance is rendered and flushed before the durable
  commit's own reply arrives, and the tap-to-shown latency is logged

#### Scenario: The durable commit later succeeds

- **WHEN** an Apply was shown optimistically and the durable two-phase
  commit subsequently acknowledges successfully
- **THEN** the receiver's own `active` snapshot and every other durable
  record (the active pointer, preferences, app appearance) settle to match
  exactly what is already on screen, with no further visible change

#### Scenario: The durable commit later fails

- **WHEN** an Apply was shown optimistically and the durable two-phase
  commit subsequently fails for any reason
- **THEN** the visible appearance is rolled back to the previous
  generation and the chooser shows a clear, specific error; at no point
  after the transaction settles does the screen show a theme that is not
  the durably active one

#### Scenario: A cold, unprepared theme is never shown optimistically

- **WHEN** an Apply targets a generation the chooser's receiver has not
  already prepared
- **THEN** the chooser shows its pre-existing busy/pending state and waits
  for the durable commit, exactly as before this requirement, with no
  early or speculative preparation triggered merely to qualify

#### Scenario: A rapid second Apply is not confused by the first

- **WHEN** a person applies one already-prepared theme, and before or
  shortly after that transaction settles applies a second, different
  already-prepared theme
- **THEN** each Apply's own optimistic check and shown appearance are
  scoped to that Apply's own request, and the second Apply is never
  suppressed or corrupted by bookkeeping left over from the first

#### Scenario: Rendering ahead of Apply never shows anything before it is confirmed

- **WHEN** a candidate theme's appearance is rendered ahead of time, while
  it is only being previewed
- **THEN** that rendering never becomes visible on any surface, and never
  alters what any ordinary (non-Apply) redraw shows, until an Apply tap
  actually requests it

#### Scenario: A render made ahead of Apply is discarded, not reused, if anything it depended on changed

- **WHEN** a theme's appearance was rendered ahead of an Apply tap, and
  before that tap the surface's geometry changed, the chooser navigated to
  a different page, or other on-screen content it captured changed
- **THEN** Apply falls back to rendering fresh rather than showing that
  stale render, with no incorrect or outdated content ever reaching the
  screen

### Requirement: Picker drags follow the finger before release

<!-- Grounding: task group 14. Injected board pairs and the sprite repaint
are in docs/evidence/theme-picker/row-sprites-2026-10-12/ and
docs/evidence/theme-picker/board-session-2026-10-12b/ (11.3). Operator
real-finger acceptance: "14.4 they do, is good" (2026-10-12), and "it's great
now i tried it all it's good" on installed system 298a2bf6 (2026-10-12). -->

*Grounding: injected board pairs and sprite repaint in `docs/evidence/theme-picker/row-sprites-2026-10-12/README.md` and `docs/evidence/theme-picker/board-session-2026-10-12b/README.md`; operator real-finger acceptance 2026-10-12 ("14.4 they do, is good"; "it's great now i tried it all it's good" on installed system `298a2bf6`). No camera recording was taken.*

While a person holds and drags either picker row, the reference preview card's
horizontal center SHALL track their horizontal displacement in surface pixels,
subject only to catalog end bounds. Momentum SHALL start only after release;
a stationary hold SHALL expire earlier fling velocity. Queued input SHALL be
coalesced to its latest position before the next eligible motion repaint.

#### Scenario: Drag, reverse and hold

- **WHEN** a person drags a row horizontally, reverses, then holds still
- **THEN** its reference card follows the displacement without amplified
  travel or autonomous settling while held, and old motion samples do not
  produce a visible animation backlog

#### Scenario: Release after a stationary hold

- **WHEN** a person releases after holding the row still
- **THEN** earlier drag velocity does not launch a delayed fling; only the
  remaining nearest-item settling motion may run

### Requirement: Picker release motion is continuous and interruptible

<!-- Grounding: task group 18. Board per-frame position and velocity curves
for 40 injected gestures (docs/evidence/theme-picker/board-session-2026-10-12b/
18.3/) show monotonic approach, no overshoot and repeatable final items.
Operator real-finger acceptance of tracking, flick distance, settling and
interruption on both rows: "it's great now i tried it all it's good" on
installed system 298a2bf6 (2026-10-12). No camera recording was taken. -->

*Grounding: board per-frame position and velocity curves for 40 injected gestures in `docs/evidence/theme-picker/board-session-2026-10-12b/README.md` (task 18.3: monotonic approach, no overshoot, repeatable final items); operator real-finger acceptance of tracking, flick distance, settling and interruption on both rows, 2026-10-12, on installed system `298a2bf6`. No camera recording was taken.*

Both picker rows SHALL use actual elapsed time for release motion and SHALL
carry screen-space release velocity continuously into centering. A new contact
SHALL interrupt motion at the displayed position without a jump. Held movement
SHALL remain direct, and settling SHALL not activate a theme or background.

#### Scenario: Frame cadence varies after release
- **WHEN** identical drag/release input is followed by different frame cadences
- **THEN** the trajectory at equal elapsed time remains equivalent within a
  defined numeric tolerance, with no artificial slow-down from elapsed clamps

#### Scenario: Person catches a moving preview
- **WHEN** a person touches a coasting or settling row and reverses direction
- **THEN** it stops autonomous movement immediately and follows from the current
  displayed position without waiting for a snap animation to finish

### Requirement: Every promised background fit mode exists

*Grounding (2026-10-16): host tests in `tests/background_decode_module.rs`, `tests/test_theme_preferences.py` and `tests/test_omarchy_theme_activation.py`; native board `grim` captures of all five modes on one dark and one light theme, and a user overlay staged, applied and kept across a shell/helper restart, in `docs/evidence/omarchy-themes/background-fit-modes-board/README.md`. Taps were injected over HDMI. The over-256 MiB overlay rejection is host-only.*
The system SHALL support `crop`, `fit`, `center`, `fill`, and `solid`
background placement modes, selectable the same way the existing modes
already are. `fill` SHALL stretch the image to exactly cover the panel, ignoring its
aspect ratio, with no letterbox and no crop (`crop` is the
aspect-preserving cover). `solid` SHALL show a plain fill color drawn from the active
generation's resolved background/base palette role for a theme that ships
no background asset. A person SHALL be able to choose a background image
from outside the active theme's own asset set, bounded the same way an
in-theme background already is (size limit, supported-format check, no path
escape).

#### Scenario: Fill mode covers the panel without letterboxing
- **WHEN** a person selects `fill` for a background whose aspect ratio does
  not match the panel
- **THEN** the image is stretched to cover the whole panel, with no visible
  letterbox and nothing cropped away

#### Scenario: Solid mode with no background asset
- **WHEN** a theme ships no background asset and a person selects `solid`
- **THEN** the panel shows a plain fill color drawn from that generation's
  resolved palette, not a decode error or a blank surface

#### Scenario: A user overlay image is chosen
- **WHEN** a person selects a background image from outside the active
  theme's own asset set
- **THEN** the system applies the same size/format/path bounds an in-theme
  background already has, and rejects an oversized or unsupported file
  without crashing

### Requirement: A video-suffixed background plays, muted and bounded

*Grounding (2026-10-22): board playback, cover pause/resume, reduced-motion startup and restoration in `docs/evidence/omarchy-themes/background-video-board-2026-10-21/README.md`. The paired still/video, one/three-card budget trial passes every frozen numeric metric at the shipped 12 ms panel allowance with injected drags at the measured real-finger rate, in `docs/evidence/omarchy-themes/background-video-board-2026-10-21/installed-12ms-trial/README.md`. The operator reported no flicker on real glass. Landscape only.*

<!-- UNVERIFIED: the budget trial's portrait 568x1232 session (the board runs
landscape by operator decision); unsupported-codec diagnostics and fallback
on the board (host proof only, docs/evidence/omarchy-themes/background-video-audit.md);
a live reduced-motion toggle (only the startup setting was tested). -->
The system SHALL play a video-suffixed background from a theme's own
`backgrounds/` directory, muted, bounded, and reusing the same decode path
already justified for another wallpaper surface. It SHALL distinguish an
unsupported codec from a missing or corrupt asset, pause decoding when the
background is fully covered or reduced motion is enabled, and show a still
fallback (the theme's own preview image, or its first still background)
in either case rather than a blank surface. This inherits the existing
card CPU/frame budgets as a physical performance gate; it is not claimed
closed by a host test alone.

#### Scenario: A supported video background plays
- **WHEN** a person selects a theme whose `backgrounds/` directory contains
  a supported video-suffixed file
- **THEN** the panel plays it muted and bounded, respecting the existing
  card CPU/frame budgets

#### Scenario: An unsupported codec is reported honestly
- **WHEN** a selected video background's codec is not supported
- **THEN** the system reports the specific unsupported-codec condition and
  shows a still fallback, rather than reporting a generic missing-asset
  error

#### Scenario: Covered or reduced-motion playback pauses
- **WHEN** a playing video background becomes fully covered by another
  surface, or reduced motion is enabled
- **THEN** decoding pauses and a still frame is shown, resuming visible
  playback only when uncovered and reduced motion is off, within the
  measured shell interaction budgets

### Requirement: GTK3 applications follow the active theme

*Grounding: the 2026-10-26 design review of native grim captures on the board (`the-shell-and-its-apps-look-finished` design.md); fixed-build captures in `docs/evidence/shell-design-review/README.md`.*

*Grounding (2026-10-29): the operator reported Files' text "mostly unreadable" on glass (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`). The board's `~/.config/gtk-4.0/settings.ini` held only `gtk-decoration-layout`, so GTK4 apps had no font size from the adapter.*

*Grounding (2026-10-29): host probes under a headless Wayland Sway with GTK 4.22.4 and 3.24.52, and native grim captures of Files and Net at 100% and 200% on the board with injected touch (`docs/evidence/gtk-text-size/README.md`). Files' labels went from 10 to 14 px ink at 100%. A step change reached new launches without a restart.*

*Grounding (2026-10-29): the operator read Files at 100% on glass on build `2867v7pm…`: "works great." (`docs/evidence/gtk-text-size/README.md`).*

The appearance adapter SHALL give GTK3 applications the active theme's colours, a touch-readable font size and controls at least 44 px tall, from files it generates per theme generation and links into the shell user's GTK3 configuration. It SHALL give GTK3 and GTK4 applications the same base text size, matching the shell's body text at the 100% text step, and SHALL multiply that size by the Settings text-size step (100%, 130%, 160% or 200%). A GTK application started after the step changes SHALL use the new size. It SHALL NOT overwrite GTK3 or GTK4 configuration it did not write. GTK3 and GTK4 applications SHALL show a close button only.

#### Scenario: A puzzle after a theme change
- **WHEN** a theme is applied and Same Game is then launched
- **THEN** its window uses the theme's background, text and accent colours

#### Scenario: Files at the default text step
- **WHEN** Files is opened with the text step at 100%
- **THEN** its sidebar rows, path bar and icon captions are drawn at the shell's body text size, not the toolkit's smaller default

#### Scenario: Files after a larger text step
- **WHEN** a person sets the text size to 200% in Settings and then opens Files
- **THEN** Files' text is twice its 100% size, and the window still fits the panel

#### Scenario: An app left open across a step change
- **WHEN** Net is open while the person changes the text size
- **THEN** Net keeps its current text size until it is closed and opened again

### Requirement: The theme chooser's carousels end softly at their column edges

*Grounding: the 2026-10-26 design review of native grim captures on the board (`the-shell-and-its-apps-look-finished` design.md); fixed-build captures in `docs/evidence/shell-design-review/README.md`.*

<!-- Grounding: injected-touch grim captures in docs/evidence/design-review-leftovers/README.md, and the operator's on-glass acceptance of build qh3i7b3f on 2026-10-26 (docs/evidence/design-review-leftovers/operator-report.md). -->
Neighbouring items in the theme and background carousels SHALL fade out at their column edge rather than be cut off at the output edge. Every carousel item SHALL carry a thin frame in ink that contrasts with the page, so a narrow slice of a pale image still reads as the edge of an item.

#### Scenario: Background carousel edge
- **WHEN** the background carousel shows items to the right of the centred one
- **THEN** the item nearest the output edge fades out instead of ending in a hard cut

#### Scenario: A pale neighbour slice
- **WHEN** the background beside the centred one is mostly the page's own colour
- **THEN** its slice shows a frame along its outline, not loose glyphs
