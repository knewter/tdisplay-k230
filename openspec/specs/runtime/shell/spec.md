# runtime/shell Specification

## Purpose
Defines the handheld Sway session: CPU rendering, automatic startup, touch
input, an on-screen keyboard, application discovery and session controls.

## Requirements

### Requirement: Apps opens a portrait touch launcher

*Grounding: `docs/evidence/shell-features/portrait-launcher/README.md` records
physical-panel rendering and injected actions. The user separately confirmed launcher finger usability in
`docs/evidence/shell-features/desktop-launcher/README.md`; the normal source-image reboot and post-boot launcher capture are recorded
in the same evidence directory.*

The persistent Apps control SHALL open a native Wayland portrait launcher while
Keyboard, Windows/Home, and System remain available through the persistent
bar. The launcher SHALL present a visible title and touch-sized, high-contrast
Terminal, Monitor, New terminal, and Back targets. Terminal and Monitor SHALL
focus their existing window when present or start it when absent. New terminal
SHALL start a separate terminal window. Back SHALL close the launcher without
requiring a physical keyboard.

#### Scenario: A user opens an application

- **WHEN** the user taps Apps and then Terminal or Monitor
- **THEN** the launcher action focuses the selected running application, or
  starts it when no matching window is running

#### Scenario: A user starts another terminal

- **WHEN** the user taps Apps and then New terminal
- **THEN** a separate readable terminal window starts without requiring a
  physical keyboard

#### Scenario: A user leaves the launcher

- **WHEN** the user taps Back on the Apps surface
- **THEN** the launcher closes and the persistent bar retains Apps, Keyboard,
  Windows/Home, and System controls

### Requirement: Apps discovers installed desktop applications

*Grounding: `docs/evidence/shell-features/desktop-launcher/README.md`, its
console, PNGs and camera recording establish physical-panel discovery, launch,
refresh and error recovery using injected input. The user separately confirmed finger usability on 2026-09-22; normal source-image reboot persistence is demonstrated by the separate
image-launcher video and console, without restoring home-directory state.*

<!-- UNVERIFIED: functional launch splash accepted by the operator, docs/evidence/proposal-closeout/2026-10-01/splash.md; prior host/QEMU proofs remain. UNVERIFIED: quantitative one-frame timing and individual physical timeout/failure cases were not newly measured. Additional capture/fault-injection reruns are waived. Shared GNOME activation/menu parity remains the Home proposal's task group 11; this splash closeout does not claim that implementation. -->

The system's Apps surface SHALL list visible application desktop entries from
the user's XDG data directories and Nix profile data directories, applying
user-over-system precedence and desktop visibility rules. Reopening Apps SHALL
reflect entries added or removed since the previous open. The surface SHALL
provide readable application names and touch-accessible pages when the list
exceeds the portrait display. Launching an entry SHALL preserve desktop-entry
argument expansion and working-directory semantics. Terminal applications SHALL
open in the configured terminal. A launch error SHALL leave a visible explanation
and a usable Back control. The application grid SHALL present at least 4
columns of icons at this panel's width, each icon at least 56 logical
pixels square, with a single-line, ellipsized application name below each
icon and no surrounding card or plate. An application with no resolvable
icon SHALL show a round, theme-coloured fallback bearing its initial
letter, rather than leaving the tile blank.

A launch SHALL show the instant splash defined below instead of leaving the
previous app visible during startup. Terminal applications SHALL hand off
the splash correctly despite mapping under the terminal identity. A launch
failure SHALL use the splash's recoverable failure state and a reachable
return to Apps or Home, never an unexplained dead overlay.

#### Scenario: An installed application becomes available

- **WHEN** a visible application desktop entry is installed in a session data
  directory and the user reopens Apps
- **THEN** its name appears in the application list and can be selected by touch

#### Scenario: An application is removed or hidden

- **WHEN** an application entry is removed or hidden by a user override and the
  user reopens Apps
- **THEN** that application is absent from the list

#### Scenario: An application needs a terminal

- **WHEN** the user selects an installed application with Terminal=true
- **THEN** its expanded argument list runs in the readable terminal profile
  with the desktop entry's configured working directory, and the splash
  hands off correctly to that terminal window even though it maps under the
  terminal's own identity, not the launched entry's

#### Scenario: A launch fails

- **WHEN** the selected application cannot be launched, or its spawned
  process exits before any window maps
- **THEN** the splash shows a recoverable failure state naming the app and
  returns the user to Apps or Home, rather than leaving a dead overlay or an
  unexplained, unresponsive previous app

#### Scenario: The application grid presents a dense, legible layout

- **WHEN** the user opens Apps with more entries than fit in one screen
- **THEN** at least 4 columns of icons are visible per row, each icon at
  least 56 logical pixels square with a legible, ellipsized name below it
  and no surrounding card, and the list scrolls to reveal the remainder

#### Scenario: An application with no icon still gets a legible tile

- **WHEN** an installed application's desktop entry names no icon that
  resolves against the active icon theme
- **THEN** its grid tile shows a round, theme-coloured circle bearing the
  application's initial letter, not an empty or broken tile

#### Scenario: Searching uses the same system keyboard as other text fields

- **WHEN** a person focuses the app drawer's Search field
- **THEN** the normal system keyboard appears and its ordinary typed text and correction update the live app filter, with the list kept visible above the keyboard
- **AND** dismissing search, launching a result or leaving the drawer releases keyboard focus and lowers the keyboard without stranding application input

#### Scenario: Search focus and correction remain visible

- **WHEN** a person taps Search and types or presses the system keyboard's Backspace
- **THEN** a visible insertion caret and focus indication identify the active field, correction changes only the query, and the app drawer remains open

<!-- Closeout evidence: docs/evidence/proposal-closeout/2026-10-01/drawer.md. Operator report is physical
feedback; retained host/QEMU/injected evidence keeps its original class.
No additional capture, quantitative measurement or fault injection claimed. -->

### Requirement: The shell renders on the CPU, with no Mesa/DRI driver and no software GL

The compositor SHALL composite in software into DRM dumb buffers. It SHALL NOT
require OpenGL, OpenGL ES, Vulkan, a GBM allocator, or a DRM render node, and
the system SHALL NOT carry a Mesa GL or Vulkan runtime in order to run it. This
does not deny the separate VGLite 2D kernel driver; that driver is not a
Mesa/DRI path and is not used by this compositor.

*Grounding: `wlroots-0.20.2/render/wlr_renderer.c:220-228` lists `pixman` among
the values of `WLR_RENDERER`, alongside `gles2` and `vulkan`, so the software
renderer is a supported selection rather than a debug path; line 268 selects it
automatically when `has_render_node()` is false, which is the case for a
display-only KMS driver. The Pixman renderer
advertises `WLR_BUFFER_CAP_DATA_PTR` and not `WLR_BUFFER_CAP_DMABUF`
(`render/pixman/renderer.c:196-204`), so `wlr_allocator_autocreate()` skips its
GBM branch and reaches the dumb-buffer branch at
`render/allocator/allocator.c:140-152`, whose only conditions are a DRM fd and
`drmIsMaster()` on it. `include/render/allocator/drm_dumb.h` declares
`wlr_drm_dumb_allocator_create(int fd)` returning buffers with a `void *data`
the CPU writes into. The trade-offs of every alternative are recorded in
`docs/display-environment-options.md`. On the board, `docs/evidence/drm-info.txt`:
`canaan-drm` exposes a primary node only (no `renderD*`),
`DRM_CAP_DUMB_BUFFER = 1`, and `modetest` scanned out a dumb buffer in
ARGB8888 and in RGB565, photographed. The primary plane has no XRGB8888, so
the compositor must render RGB565 (sway `render_bit_depth 6`) or ARGB8888;
wlroots' default of XRGB8888 is refused by `output_pick_format()`
(`types/output/render.c:147-190`) with no fallback.*

#### Scenario: The rendering path is inspected

- **WHEN** someone asks how pixels reach this panel
- **THEN** the answer is a CPU rasteriser writing into a DRM dumb buffer, with no GL, no Vulkan, no GBM allocator and no render node anywhere in the compositor path

#### Scenario: The closure is inspected for a GPU stack

- **WHEN** the built system closure is searched for Mesa
- **THEN** it contains no Mesa GL or Vulkan runtime, llvmpipe, or LLVM. The
  separately linked `mesa-libgbm` library may be present but is unused by the
  Pixman/dumb-buffer path, as recorded in `docs/evidence/shell-build.txt`.

### Requirement: Hyprland is a recorded rejection, not an open question

Hyprland SHALL NOT be the compositor, and the reason SHALL stay written down so
the decision is not re-litigated from the name alone.

*Grounding: `hyprland-0.56.2/CMakeLists.txt:129-130` reads `set(GLES_VERSION
"GLES3")` then `find_package(OpenGL REQUIRED COMPONENTS ${GLES_VERSION})` — a
hard build requirement — and line 529 links `OpenGL::EGL OpenGL::GLES3`. Its
only renderer is `src/render/OpenGL.cpp`; Pixman appears in the tree solely as
region arithmetic (`pixman_box32` at `src/render/OpenGL.cpp:1020`). Since 0.41
it does not use wlroots but its own backend, aquamarine, whose
`CMakeLists.txt:22` also reads `find_package(OpenGL REQUIRED COMPONENTS
"GLES3")`. There is therefore no `WLR_RENDERER=pixman` to set. Measured on the
pinned nixpkgs, `hyprland` + `foot` adds 184 riscv64 derivations and 2.2 GiB of
substituted paths, including Qt 6 and a second GCC cross-bootstrap
(`riscv64-unknown-linux-gnu-gcc-16.2.0`); see
`docs/display-environment-options.md`.*

#### Scenario: Someone proposes Hyprland again

- **WHEN** Hyprland is suggested for this board
- **THEN** the repository states that it requires OpenGL ES 3 at build time, has no software renderer, and costs a second cross toolchain — with the file and line for each claim

### Requirement: The shell's build cost is measured and recorded

Every package this change adds is compiled for riscv64 without a native binary
cache, so the cost of the shell SHALL be measured on the build host and
committed, and SHALL be the smallest of the candidates that meets the other
requirements here.

*Grounding: `docs/evidence/shell-build.txt` records the completed enabled
build: about 235 derivations across resumed stages and 2705 seconds (45
minutes), with a final 1,280,679,016-byte (1221.0 MiB) closure, +110.2 MiB and
+95 paths over the 1109.9 MiB baseline. The final menu/image increment,
including `htop`, `jq`, `gnused`, and `grim`, added 22 derivations and 8.0 MiB
unpacked. `docs/display-environment-options.md` remains the historical
candidate estimate: 68 derivations for the `cage` smoke test, 89 for `sway`
with `foot` and `wvkbd`, 184 for Hyprland, and 288 for nixpkgs' default
Weston.*

The compositor SHALL be built with Xwayland disabled.

*Grounding: measured against the same pin, `wlroots` needs 85 local
derivations and 500 MiB of fetches by default and 30 derivations and 210 MiB
with `enableXWayland = false`; Xwayland drags in GTK 3, CUPS, Avahi,
at-spi2-core and dconf. Recorded in `docs/display-environment-options.md`.*

#### Scenario: The wall-clock cost of the shell is asked for

- **WHEN** someone asks what adding the shell costs to build
- **THEN** a measured derivation count and wall-clock time are committed under `docs/`, alongside the numbers for the options that were not chosen

#### Scenario: An X11 application is wanted

- **WHEN** someone needs an X11 application on this board
- **THEN** the repository states that Xwayland was deliberately disabled and what re-enabling it costs, rather than the application silently failing to start

### Requirement: The shell starts at boot and owns the panel

*Grounding: `docs/evidence/shell-real-touch-system/README.md` records a
physical touch-triggered reboot, automatic return to the terminal, the serial
boot transcript, and active shell/seatd/firewall after startup. The user
removed a separate wall-supply power-on trial from acceptance. This remains
USB-connected warm-reboot evidence; no disconnected power-on is claimed.*

The system SHALL start the compositor without a host computer, external keyboard, login prompt or
a display manager, and the compositor SHALL take the panel at its native
568x1232 in portrait, with no rotation and no scaling.

**A compositor that starts is not a shell that works.** The evidence SHALL be a
photograph of the physical screen together with the compositor's log, because a
Wayland session can report a successful mode set and present nothing — the same
failure this board already produced once, when the Wi-Fi driver reported
`start ap successs!` and transmitted nothing.

#### Scenario: The shell starts automatically after reboot

- **WHEN** the user reboots from the touch controls with the available power connection and no host commands or external keyboard input to start the session
- **THEN** the compositor is running with a terminal visible on the panel, photographed

#### Scenario: The compositor log is read

- **WHEN** the compositor's startup log is examined
- **THEN** it names the software renderer and the dumb-buffer allocator it selected, and reports no failed attempt to open a render node as an error

### Requirement: A person can type on the board without an external keyboard

*Grounding: `docs/evidence/shell-real-touch-keyboard/README.md` combines
real Goodix contacts, physical hidden/shown keyboard frames, native captures,
and the operator's confirmation of the keyboard sequence and command output.
The successful asymmetric argument is `1qazoplm` (letter o). The camera does
not independently resolve the hide transition; that action is accepted on
the direct operator report, not described as filmed.*

The shell SHALL present an on-screen keyboard that a person can summon and
dismiss by touch, and characters typed on it SHALL reach the focused
application.

#### Scenario: Someone types a command without an external keyboard

- **WHEN** a person summons the keyboard and types a command into the terminal on the panel
- **THEN** the command runs and its output appears on the panel, photographed

#### Scenario: The keyboard is dismissed

- **WHEN** the keyboard is dismissed
- **THEN** the application underneath is fully visible again and usable

### Requirement: A touch activates what is under the finger

*Grounding for key entry and axis decision:
`docs/evidence/shell-real-touch-keyboard/README.md` and
`docs/evidence/shell-session.txt` record the real-touch asymmetric command,
operator-confirmed output, and fresh identity calibration matrix. Source
contains no DT swap/invert correction; the panel uses native portrait and
explicit output mapping. The initial `exho` typo remains documented. This is
not a calibrated pixel-error or every-tap-perfect claim.*

<!-- UNVERIFIED in part: the deliberate full-panel directional drag scenario
has not been separately recorded. Completed task boxes for key entry and
operator-confirmed controls do not supply that missing motion evidence. -->

Touches SHALL be routed to the surface drawn at the touched location, in the
panel's own 568x1232 coordinate space, with the axes neither swapped nor
mirrored.

**Input events with coordinates are not the same claim as touch that works.**
`display/touch` proves the controller reports movement; this proves the shell
acts on it. Where the two disagree the fix SHALL be recorded as a compositor
input mapping or a libinput calibration matrix, and which one it is SHALL be
stated, because the two live in different files and a later kernel change can
invalidate only one of them.

#### Scenario: A person presses a key on the on-screen keyboard

- **WHEN** a person presses a specific key drawn on the panel
- **THEN** that key's character is what arrives, not a neighbouring one and not one from the mirrored position

#### Scenario: A drag is performed across the panel

- **WHEN** a finger is dragged from one end of the panel to the other
- **THEN** the shell follows the finger in the same direction, and this is shown rather than asserted

### Requirement: The standalone session has practical touch controls

*Existing grounding: `docs/evidence/shell-real-touch-apps/README.md` records
physical Apps/Terminal/Monitor interaction and a legacy Home-to-Terminal
recovery confirmation. `docs/evidence/shell-real-touch-system/README.md`
records touch followed by reboot and return to the shell. Exact confirmation
labels and Cancel are not individually camera-legible; earlier injected menu
and failure-path evidence is separately labeled in `docs/evidence/shell-features/`
and `docs/evidence/shell-virtual-touch.txt`. These observations ground the
installed development bar, not the gesture-led final session.*

*Grounding: operator acceptance, exact installed/runtime identity and the additional-proof waiver are recorded in `docs/evidence/coherent-shell/operator-closeout-2026-10-10/README.md` and `docs/evidence/coherent-shell/combined-board-candidate-2026-10-10/README.md`.*
<!-- UNVERIFIED: no new per-case cancellation/conflict/confirmation physical recording or quantitative measurement is asserted. Side-edge Back and general at-down ownership remain unimplemented in their authorized successor. -->
In the final normal session, the shell SHALL keep live-card Overview and pinned
Home distinct. A purely upward bottom-edge gesture from an app or transient
shell surface SHALL reach Overview. An upward gesture from Overview’s bottom
navigation area SHALL reach pinned Home without closing running apps; a new
upward gesture from Home SHALL reveal All apps with named Terminal and Monitor
actions. Swiping a card itself upward SHALL retain its close action. An app-entry
gesture curving sideways without lifting, or a horizontal gesture from anywhere
within the qualified bottom band, SHALL select an adjacent running app for
activation on qualified release while preserving deck order, privacy and
existing app/keyboard ownership. The top-edge downward gesture SHALL reveal
notification history and Settings. Bottom-edge escape and explicit close/return
controls SHALL retain recovery from shell contexts. The shell SHALL NOT
synthesize a universal Back key into arbitrary apps; qualified side-edge Back
and the general at-down arbiter remain the separate successor’s requirements.
Normal composition SHALL NOT retain permanent Apps, Windows, Keyboard, System,
Back or Home controls. Help SHALL provide gesture guidance and a deliberately
opened large-labeled navigation aid. The old persistent-bar session SHALL remain
a separately selectable rollback with its existing Apps, Windows/Home, Keyboard
and System controls, at least 56-pixel-high targets and primary controls at least
128 pixels wide on the 568-pixel panel; its empty-window/Home/Back recovery and
keyboard controls retain their existing behavior.

Settings SHALL offer reboot and power-off only after a second confirmation
surface that names the action and includes Cancel. A failed or denied system
action SHALL show the failure and leave a route to the shade or Home. The
session user SHALL have authority only for those two explicit `systemctl`
operations; no general passwordless command or root shell is part of the
control.

#### Scenario: A user returns to an application without a keyboard

- **WHEN** the user opens the drawer from Home and taps Terminal, Monitor, or
  an installed desktop entry
- **THEN** the named running application is focused or started without serial
  or physical-keyboard input

#### Scenario: A user enters Overview and then Home

- **WHEN** the user swipes upward from a running app and then begins a new upward gesture from Overview’s bottom navigation area
- **THEN** the app first shrinks into Overview, then pinned Home appears while the running app remains available

#### Scenario: A user opens installed apps

- **WHEN** the user begins a new upward pull from pinned Home
- **THEN** the installed-app drawer rises from the bottom; a short cancelled
  pull returns to the same Home scene

#### Scenario: A user chooses a system action by touch

- **WHEN** the user opens the shade, enters Settings, and chooses Restart or
  Power off
- **THEN** the shell presents a distinct confirmation and Cancel target before
  invoking the corresponding operation

#### Scenario: A system action is denied

- **WHEN** the confirmed `systemctl` command fails or is denied
- **THEN** the shell reports failure and lets the user return to Settings,
  shade, or Home

#### Scenario: The menu is tested with injected input

- **WHEN** an `evemu`/uinput event activates a block in the rollback bar
- **THEN** that result is recorded as injected-input evidence for the rollback
  session only; it does not close final gesture or real-finger requirements

### Requirement: The shell hosts a later application shell; it does not choose one

The compositor and the separately archived installed-application launcher SHALL
NOT be treated as a decision about which application shell draws the product
experience. They provide a surface, an input path, a way to type, and a small
way to launch installed desktop entries; the later application shell remains
open.

*Grounding: `openspec/config.yaml` identifies the current Sway handheld goal and
places AtomVM/Dozer integration outside its scope. The archived launcher change
is scoped to desktop-entry discovery and session utilities. `docs/findings.md`
records the application-framework assessments as still open.*

#### Scenario: A later application shell is proposed

- **WHEN** someone proposes a way to draw the product experience on this board
- **THEN** nothing in this capability forbids it, whether it is a Wayland client, a direct DRM/KMS renderer that replaces the compositor, or something else

### Requirement: The shell exposes a bounded offline application set

The shell SHALL expose Help and the existing Terminal action through the portrait
Apps flow. It SHALL add only a small, explicitly reviewed set of portrait-usable
desktop entries selected from packages that build for the pinned riscv64 image and
fit the measured closure and startup budgets. An editor and a file browser are
preferred candidates when an existing dependency satisfies those constraints;
the image SHALL not gain a network installer, package manager UI, AtomVM, Dozer,
or a general desktop suite for this capability.

*Grounding: Package builds, measured closure differences, fresh-image discovery
and injected launches are recorded in `docs/evidence/offline-wifi-image/README.md`
and `docs/evidence/offline-app-candidates/selection.md`.*

#### Scenario: A user opens the offline app set

- **WHEN** the user opens Apps with no network connection
- **THEN** Help, Terminal, and every selected offline application appear as
  readable touch targets and do not require network access to launch

#### Scenario: A candidate fails the image checks

- **WHEN** a proposed editor or file browser fails the pinned riscv64 build,
  closure, startup, or portrait usability check
- **THEN** it is omitted and the remaining Apps and Help flow remain usable

### Requirement: Help explains the keyboard-free shell

The shell SHALL provide an offline Help surface reachable from Apps and SHALL
describe the purpose and action of Apps, Keyboard, Windows/Home, System, Back,
paging, and the terminal and monitor actions. Help SHALL be readable at
568x1232 in portrait mode, support touch navigation back to Apps, and avoid
requiring a network, physical keyboard, or text entry. <!-- UNVERIFIED: final
physical-finger readability and final-glass acceptance for the new Help pages
remain separate from injected native screenshots. -->

Injected paging, readable native portrait layout, Back and launch-error recovery
are recorded in `docs/evidence/offline-wifi-image/README.md` and
`docs/evidence/offline-help-injected/README.md`.

#### Scenario: A new user reads the controls

- **WHEN** the user taps Help and pages through its content
- **THEN** each persistent control and launcher navigation action has a concise
  visible explanation

#### Scenario: A user leaves Help

- **WHEN** the user taps Back from Help
- **THEN** Help closes and the user returns to the launcher or persistent shell
  controls without losing the existing touch actions

### Requirement: Offline app additions are checked before image integration

Before an app is added to the image, the project SHALL record its desktop ID,
package source, riscv64 build result, closure delta, startup result, and injected
portrait touch result. Physical finger accuracy, reboot persistence, and final
glass readability SHALL remain separately labelled evidence rather than inferred
from host or injected checks.

*Grounding: The package comparison and hardware trials are recorded in
`docs/evidence/offline-app-candidates/selection.md` and
`docs/evidence/offline-wifi-image/README.md`.*

#### Scenario: A reviewer checks an app addition

- **WHEN** a reviewer examines the app evidence
- **THEN** the record distinguishes package/build and injected workflow checks
  from physical-touch, reboot, and final-panel checks, and names any failed or
  unverified check

### Requirement: Apps provides recoverable network video controls

The shell SHALL expose a visible terminal video entry through Apps. A user SHALL be
able to launch the documented player, stop or leave it with Back/Home, and return to
the existing shell controls without an external keyboard. A failed launch, closed
stream, or network error SHALL leave a usable recovery path.

*Grounding: `docs/evidence/final-shell-image/README.md` records Apps launch, advancing playback, Stop/Back/Home and final control regression on the installed image. `docs/evidence/network-video/installed-controls/README.md` covers EOF; `recovery-fixed/README.md` and `midstream-error/README.md` in that evidence tree cover decoder fallback, startup errors and an actual interrupted stream. Final control checks use injected touch on the physical board; they do not establish a new real-finger or audio claim.*

#### Scenario: A user starts video

- **WHEN** the user opens Apps and selects the video entry
- **THEN** a terminal video session starts with the configured player and remains reachable through the shell's normal window controls

#### Scenario: A user leaves video

- **WHEN** the user taps Back or Home while the video session is focused
- **THEN** playback stops or is safely backgrounded according to the documented policy, and the shell returns to a usable terminal or Apps surface

#### Scenario: Playback fails

- **WHEN** the player exits because the source, network, or decoder fails
- **THEN** the user sees a recoverable error or returns to Apps without a dead overlay, orphaned process, or secret-bearing runtime file

### Requirement: Apps recognizes bounded single-touch paging gestures

The Apps launcher SHALL treat a single touch as a tap until its movement reaches
48 logical panel pixels. After that threshold, a horizontal gesture SHALL require
horizontal displacement at least 1.25 times its vertical displacement. A left
swipe SHALL advance one application page and a right swipe SHALL return one page;
the same touch SHALL NOT activate a card. A gesture that does not meet the
threshold or directional ratio SHALL leave the page unchanged and SHALL NOT
launch an application.

*Grounding: `docs/evidence/launcher-gestures/integrated-injected/README.md`
records numeric threshold and transition checks on the installed image;
`docs/evidence/launcher-gestures/real-finger/README.md` records the accepted
physical paging workflow. The camera view does not resolve exact finger
coordinates or uniformly sharp small text.*

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

*Grounding: `docs/evidence/launcher-gestures/real-finger/README.md` records
overview entry, return, and window selection by a real finger. The installed
image's injected/native observations are in
`docs/evidence/launcher-gestures/integrated-injected/README.md` and
`docs/evidence/final-shell-image/README.md`. Exact touch paths and optical
sharpness remain outside this recording's proof.*

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

*Grounding: `docs/evidence/launcher-gestures/integrated-injected/README.md`
records installed-client transition timing, resource counts, and fallback
checks. `docs/evidence/launcher-gestures/real-finger/README.md` establishes the
accepted workflow, but optical timing of its transitions remains `UNVERIFIED`.*

#### Scenario: A transition exceeds its frame budget

- **WHEN** the client cannot render a gesture transition within its bounded timeout
- **THEN** it settles on the previous or destination page, releases input state, and leaves button navigation usable

#### Scenario: A user uses a button instead of a gesture

- **WHEN** the user taps Previous, Next, Back, Windows/Home, Keyboard, Help, Terminal, Monitor, or a system control
- **THEN** the existing button behavior remains available regardless of gesture state

### Requirement: The card overview shows an Android-recents-sized, rounded focused card

The card overview (`CS_DECK`) SHALL render its focused card at approximately
80% of the panel's width and 80% of its height, matching the panel's own
aspect ratio, with each neighbouring card's own edge visible only as a thin
sliver (not a wide multi-card fan). A live card's content SHALL fill the
entire card slot with no visible background, border, or plate behind it —
the card IS the app content, scaled — and its four corners SHALL read as
visibly rounded. The existing webOS-fan gesture behavior — a horizontal
flick that can carry the selection past more than one adjacent card via a
velocity-projected momentum coast, an upward throw past a configured
distance/speed that requests a close, and a tap that expands the selected
card to full screen — SHALL be unchanged by this sizing; only the geometry
the same gesture formulas operate on changes.

While a card is entering the deck from a full-screen app, or expanding from
the deck to full screen, its corner radius SHALL interpolate continuously
between 0 (full screen) and its settled deck-card radius, so the transition
does not pop between square and rounded corners; cards not themselves
undergoing that size change SHALL keep their full, constant radius
throughout.

*Grounding: `nix/card-shell-policy/card-shell-policy.c`'s `cs_default_config`
(`card_width=.8*width, card_height=.8*height`) and `nix/card-shell/adapter.c`'s
matching runtime recompute. The original corner-overlay evidence below
predates the transparent-corner correction. Current implementation uses
`wlr_scene_buffer_set_rounded_clip` and `nix/card-shell/rounded-clip.h` in
the pinned Pixman compositor; `tests/card_rounded_clip.c` independently
compares its pixels over a patterned backdrop.
`docs/evidence/card-shell/transparent-corners/README.md` records matching
headless-QEMU wallpaper checks with cached, direct and ARGB/child paths,
plus a failing pre-fix control. The correction's board
wallpaper result remains UNVERIFIED until task F.3. Non-live
(private/unavailable) cards keep the pre-existing `card_background` plate,
since they have no live pixels to protect from a background.
`tests/card_shell_policy_driver.c`'s `overview_geometry` case asserts the
75-85% width/height band, a ≤15%-of-card-width neighbour peek, and a fully
off-screen third card; 36/36 cases in `tests/test_card_shell_state.py` pass.
`docs/evidence/card-shell/android-sized-cards/README.md` records a
headless-QEMU capture of the resulting overview, scroll, close, and open
sequence in both themes, compared directly against the prior 50%/60%
webOS-fan capture, confirming no visible background/border behind a live
card. Real-finger board acceptance of the gesture feel and the radius
transition's smoothness is UNVERIFIED and tracked as this change's open
board task.*

#### Scenario: The overview is entered with more than one card open

- **WHEN** a person enters the overview with two or more cards open
- **THEN** the focused card fills roughly 80% of the panel on both axes,
  keeps the panel's own aspect ratio, shows visibly rounded corners with no
  background or border behind the live content, and each neighbouring card
  is visible only as a thin edge sliver

#### Scenario: A person flicks through the deck

- **WHEN** a person performs a fast horizontal flick starting on the focused
  card
- **THEN** the selection can land more than one card away from the start,
  the settled card is exactly centered once the momentum coast finishes,
  and the same release-velocity formula governs this regardless of the
  focused card's size

#### Scenario: A card opens or closes

- **WHEN** a person taps a card to expand it to full screen, or a
  full-screen app enters the deck as a new card
- **THEN** that card's corner radius interpolates continuously from 0 to
  its settled deck-card value (or the reverse) across the transition, with
  no visible pop between square and rounded corners, while every other
  card in the deck keeps its full, constant radius throughout

### Requirement: Home weather uses Fahrenheit

*Grounding: `docs/evidence/fahrenheit-weather/README.md`, `activation.log` and the cropped native capture establish physical-board deployment and Fahrenheit rendering. Finger and reboot proof are not claimed.*

The Home weather widget SHALL display current, daily high/low and hourly temperatures in rounded Fahrenheit with an explicit °F label. Fresh and stale Celsius cache snapshots SHALL retain their existing schema and receive the same display conversion.

#### Scenario: Weather data is available

- **WHEN** fresh or cached weather is displayed on Home
- **THEN** every displayed temperature is converted from Celsius to Fahrenheit and labeled °F

#### Scenario: Weather is unavailable

- **WHEN** there is no weather snapshot
- **THEN** the widget preserves its existing unavailable display without fabricating a temperature

### Requirement: The card overview hides the Home screen while active

*Grounding: Real-finger operator confirmation, native overview capture, physical panel photograph and sanitized scene probe on the installed themed system; docs/evidence/card-shell/overview-home-bleed-through/board-2026-09-30/README.md. Entry/drag and self-healing regression coverage remains explicitly headless QEMU evidence in docs/evidence/card-shell/overview-home-bleed-through/README.md.*

The shell SHALL NOT show any part of the Home screen surface while the card
overview (`card_shell`'s deck) is active, for the whole duration the
overview is entered -- including the finger-driven bottom-edge entry
gesture from its first touch-down, not only once the gesture settles -- and
SHALL restore the Home screen's normal visibility the moment the overview
hands the screen back to a focused application or to the idle/no-app state.

#### Scenario: The overview is entered while Home would otherwise be exposed

- **WHEN** a person swipes up from the bottom edge of a running application,
  or the overview is entered directly (e.g. a recovery route), regardless of
  whether the active theme's overview canvas is opaque or configured to
  reveal the wallpaper
- **THEN** no Home grid tile, dock icon, or other Home content is visible at
  any point during the entry gesture or the settled overview

#### Scenario: Dismissing the overview with nothing focused restores Home

- **WHEN** the overview is dismissed (back/close) and no application ends up
  focused
- **THEN** the Home screen becomes visible again, exactly as it would have
  been had the overview never opened

#### Scenario: An unrelated focus change while the overview is open does not reshow Home

- **WHEN** anything reassigns keyboard/seat focus while the overview
  remains open (for example an IPC `focus` command reaching an already-
  mapped card, or any other code path outside `card_shell`'s own gesture
  and button handling), and the overview's own state does not otherwise
  change
- **THEN** the Home screen stays hidden; correcting this is not limited to
  the specific moments `card_shell`'s state machine itself toggles
  visibility (entering, leaving)

### Requirement: The coherent shell offers discoverable keyboard gestures

*Grounding: operator acceptance in `docs/evidence/proposal-closeout/2026-10-01/keyboard.md`, with prior source and board/QEMU evidence retaining their original classes and limits.*

<!-- Grounding: operator accepts keyboard gestures on 2026-10-01; see docs/evidence/proposal-closeout/2026-10-01/keyboard.md. Earlier source/QEMU/installed evidence remains distinct. Quantitative responsiveness measurement is deferred to the-shell-profiles-reported-interaction-jank; not claimed passed. -->
The system's coherent shell SHALL reveal the external keyboard with a deliberate two-finger upward swipe from the bottom edge and expose a visible handle above a shown keyboard for downward dismissal. Settings SHALL retain an explicit keyboard action and describe the gestures. One-finger bottom navigation MUST remain available without opening the keyboard.

#### Scenario: Show the keyboard explicitly
- **WHEN** the keyboard is hidden and a person swipes upward with two fingers beginning at the bottom edge
- **THEN** the keyboard appears for the current app without opening the app drawer or switching apps

#### Scenario: Discover dismissal
- **WHEN** the keyboard is shown
- **THEN** a visible, touch-sized handle above its keys permits a downward dismiss drag without needing an external keyboard or permanent navigation bar

### Requirement: Keyboard motion follows contact and settles continuously

*Grounding: operator acceptance in `docs/evidence/proposal-closeout/2026-10-01/keyboard.md`, with prior source and board/QEMU evidence retaining their original classes and limits.*

<!-- Grounding: operator accepts keyboard gestures on 2026-10-01; see docs/evidence/proposal-closeout/2026-10-01/keyboard.md. Earlier source/QEMU/installed evidence remains distinct. Quantitative responsiveness measurement is deferred to the-shell-profiles-reported-interaction-jank; not claimed passed. -->
During an accepted keyboard drag the system SHALL move the keyboard with direct proportional contact displacement, remain stationary while contact is held still, and reverse immediately with contact. Release SHALL settle from the displayed geometry and bounded measured velocity to shown or hidden without a position jump or abrupt end. Reduced motion SHALL preserve direct manipulation while shortening release settlement. Reserved app space MUST match the final visible keyboard and remain coherent during transition.

#### Scenario: Drag and reconsider
- **WHEN** a person drags the keyboard handle down, pauses, reverses, and releases before dismissal commits
- **THEN** the keyboard mirrors that motion and returns smoothly without losing the focused app

#### Scenario: Finish hiding
- **WHEN** a downward dismiss gesture commits
- **THEN** the keyboard smoothly leaves the output, its handle disappears and the app regains the available space

### Requirement: Keyboard gestures preserve typing and touch ownership

*Grounding: operator acceptance in `docs/evidence/proposal-closeout/2026-10-01/keyboard.md`, with prior source and board/QEMU evidence retaining their original classes and limits.*

<!-- Grounding: operator accepts keyboard gestures on 2026-10-01; see docs/evidence/proposal-closeout/2026-10-01/keyboard.md. Earlier source/QEMU/installed evidence remains distinct. Quantitative responsiveness measurement is deferred to the-shell-profiles-reported-interaction-jank; not claimed passed. -->
The system SHALL claim only its explicit edge chord or handle stream and SHALL preserve ordinary key taps and application touch input. Cancelled, late, additional or lost contacts MUST NOT type keys, launch apps, or strand an invisible input surface. Keyboard failure, output change and interrupted settling SHALL restore a usable app and a reachable Settings action. The Wi-Fi editor's integrated keyboard MUST retain its own explicit cancellation and focus contract.

#### Scenario: Ordinary typing stays ordinary
- **WHEN** a person taps or moves within ordinary keyboard keys without starting on the dismiss handle
- **THEN** input remains owned by the keyboard and does not dismiss it or navigate apps

#### Scenario: A gesture is interrupted
- **WHEN** an accepted keyboard gesture loses its contact stream or the keyboard process exits
- **THEN** no residual gesture becomes a key/app action and the app remains reachable

<!-- Closeout evidence: docs/evidence/proposal-closeout/2026-10-01/keyboard.md. Operator report is physical
feedback; retained host/QEMU/injected evidence keeps its original class.
No additional capture, quantitative measurement or fault injection claimed. -->

### Requirement: Shell navigation is complete with pointer input

*Grounding: operator acceptance in `docs/evidence/proposal-closeout/2026-10-01/mouse.md`, with prior source and board/QEMU evidence retaining their original classes and limits.*

<!-- Grounding: implemented pointer matrix and installed-board evidence under docs/evidence/the-shell-is-navigable-with-a-mouse/; physical operator acceptance and capture waiver: docs/evidence/proposal-closeout/2026-10-01/mouse.md. -->
The userspace shell SHALL allow primary clicks/drags and scrolling to navigate Home, app drawer, overview, notification shade and Settings, including theme and Wi-Fi pages. An app SHALL remain open when Home is selected from overview.

#### Scenario: Home without closing windows
- **WHEN** a person taps or clicks the Home affordance in overview, or swipes upward from its footer
- **THEN** Home is displayed and existing app windows remain available in overview

#### Scenario: Return from Home to open windows
- **WHEN** Home is visible with apps still open and a person taps or clicks its bottom gesture handle
- **THEN** overview shows those live windows without launching or closing an app
- **AND** an upward drag from that handle opens the app drawer instead

#### Scenario: Client controls remain tappable at screen edges
- **WHEN** a person taps a client control in a shell edge band, including an app header or the drawer-search keyboard Backspace key
- **THEN** the intended live client receives a balanced tap and performs its normal action
- **AND** no shade is revealed and no drawer is dismissed solely because the contact began at an edge
- **AND** a deliberate qualifying edge drag still uses the native shell gesture

#### Scenario: Pointer overview round trip
- **WHEN** a person drags upward from the bottom screen edge with the primary mouse button, then clicks a live overview card
- **THEN** overview opens and the chosen app expands and receives focus

#### Scenario: Pointer screen-edge routes
- **WHEN** a person drags downward from the top screen edge or upward from the bottom edge
- **THEN** the appropriate shell shade, overview or drawer follows the drag and settles using the existing navigation rules
- **AND** ordinary pointer interactions away from shell-owned regions remain application input

#### Scenario: Shell scrolling
- **WHEN** a person uses a mouse wheel or two-finger scrolling over scrollable drawer, notification, Wi-Fi or theme content
- **THEN** the relevant content moves within its bounds without launching an app or applying a theme

### Requirement: Four-finger spread enters the centered window

<!-- UNVERIFIED: individual physical four-finger recognition not separately documented. Overall mouse navigation accepted, exhaustive recheck waived; docs/evidence/proposal-closeout/2026-10-01/mouse.md. Host binding/routing is distinct from physical recognition. -->
In HDMI trackpad mode the userspace shell SHALL use a four-finger outward pinch on the built-in glass to expand the centered live overview window. Inward pinch SHALL open overview. Ordinary two-finger application pinch SHALL remain available to applications.

#### Scenario: Spread from overview
- **WHEN** overview is open with a centered live, focusable window and a person spreads four fingers
- **THEN** that window expands through the existing transition and becomes focused

#### Scenario: Empty overview
- **WHEN** no live window is available and a person spreads four fingers
- **THEN** no app is closed or incorrectly focused

<!-- Closeout evidence: docs/evidence/proposal-closeout/2026-10-01/mouse.md. Operator report is physical
feedback; retained host/QEMU/injected evidence keeps its original class.
No additional capture, quantitative measurement or fault injection claimed. -->

### Requirement: Four-finger trackpad pinch opens app overview

<!-- UNVERIFIED: normal Sway binding syntax and routing are read in the pinned source; individual physical four-finger recognition is not separately documented; overall acceptance and waived exhaustive recheck are recorded in docs/evidence/proposal-closeout/2026-10-01/trackpad.md. -->

While the board's built-in display is inactive and its touchscreen is a
virtual touchpad for HDMI, the shell SHALL open app overview after a
four-finger inward pinch on that touchscreen. The Sway configuration SHALL
scope this binding to the virtual touchpad and leave two-finger application
scroll/zoom gestures available. Direct-touch panel-mode gestures SHALL retain
their existing configuration.

#### Scenario: Navigate from a running app

- **WHEN** an app is open on HDMI and the operator pinches four fingers inward
  on the board's touchscreen glass
- **THEN** app overview appears without a keyboard or edge-touch gesture

#### Scenario: Ordinary app gestures remain available

- **WHEN** the operator uses two-finger scrolling or pinch in an app
- **THEN** the four-finger shell binding does not consume that gesture

### Requirement: HDMI two-finger gestures have explicit ownership and direct motion

*Grounding: operator acceptance in `docs/evidence/proposal-closeout/2026-10-01/trackpad.md`, with prior source and board/QEMU evidence retaining their original classes and limits.*

<!-- Grounding: installed uniform-gesture trial/source evidence and overall operator acceptance in docs/evidence/proposal-closeout/2026-10-01/trackpad.md. No new camera/contact-count measurement is claimed. -->

In HDMI trackpad mode, two-contact shell gestures SHALL use the same navigation,
card manipulation, sheet scrolling/dismissal and release policies as one-contact
direct touch gestures. Three-contact upward bottom gestures SHALL use the existing
two-contact direct touch keyboard policy. Motion SHALL follow the contact centroid,
reverse while held, and settle with the shared release physics. The shell SHALL
preserve ordinary application center scroll/pinch and one-contact pointer/tap.
Transport loss and cancellation SHALL restore recoverable state without a stale
contact, and translated pan release SHALL NOT activate an app as a tap.
Direct-touch behavior SHALL retain its existing gesture configuration.

#### Scenario: Open shell surfaces without positioning the cursor

- **WHEN** two fingers swipe down from the glass's top edge or up from its bottom edge in HDMI mode
- **THEN** Shade or the existing app/overview/Home/drawer navigation follows that movement, independent of where the pointer is

#### Scenario: Browse cards without stepping

- **WHEN** two fingers move horizontally while overview is showing
- **THEN** live cards move continuously, reverse with the fingers and settle from release velocity without discrete card jumps

#### Scenario: Ordinary input retains its owner

- **WHEN** a center two-finger scroll/pinch, one-finger pointer/tap, incompatible movement or an unqualified additional-contact sequence occurs
- **THEN** the compatible ordinary sequence remains libinput-owned; a canceled owned shell gesture cannot generate a stray app click

#### Scenario: Dismiss, reverse or lose a controller

- **WHEN** an owned sheet gesture reverses, cancels or loses its transport
- **THEN** the current sheet settles to a recoverable state without a stale owned contact, half-visible sheet or unrelated route

#### Scenario: Dismiss a drawer using its native content rules

- **WHEN** a two-finger downward drag begins in an open app drawer at the top of its scrollable content
- **THEN** it closes with the same tracking, reversal and release as a one-finger direct-touch drag
- **AND** a gesture that began while the list was scrolled retains scrolling ownership

#### Scenario: Keyboard uses the next contact count

- **WHEN** three fingers swipe upward from the bottom in HDMI trackpad mode
- **THEN** the existing keyboard show/drag/settle policy handles the gesture as the corresponding direct-touch two-finger chord
- **AND** a two-finger navigation gesture does not accidentally show the keyboard

<!-- Closeout evidence: docs/evidence/proposal-closeout/2026-10-01/trackpad.md. Operator report is physical
feedback; retained host/QEMU/injected evidence keeps its original class.
No additional capture, quantitative measurement or fault injection claimed. -->

### Requirement: A drawer scroll gesture never converts into a close

*Grounding: `docs/design/app-drawer-review.md` §1 (an earlier revision
of this document) traces the reported bug ("swipe down in the app drawer
to scroll back up, it closes the drawer") to two independent mechanisms
that each decided close-eligibility once, at the start of a touch, and
never revisited it as the gesture actually unfolded. Fixed in
`nix/rust-shell-client/src/navigation.rs` (`Contact::scrolled_away`,
gating `DrawerNavigation::up`'s release-only dismiss check) and
`service_ui.rs` (`drawer_close_candidate_after_scroll`, gating the live
"follow the finger" close drag `main.rs`'s `motion` handler runs on
every sample). Landed in its own commit, separately from the redesign
this change otherwise covers. Regression tests reproduce the exact
gesture: `navigation.rs::scrolling_away_from_the_top_then_reversing_never_closes_within_one_gesture`,
`main.rs::drawer_live_close_drag_never_engages_after_a_mid_gesture_scroll_reversal`.*

A downward drag on the app drawer's grid or its top chrome SHALL close
the drawer only when the grid was at rest at its own scroll top — with
no fling still decelerating toward it — at the moment the finger touched
down. Once a gesture has actually scrolled the grid away from its own
top, that same held gesture SHALL NOT close the drawer for the remainder
of its duration, even if the grid's scroll position later returns to (or
clamps at) its top before the finger releases. After a fling has fully
decelerated to a stop at the top, a new, separate downward drag MAY close
the drawer.

#### Scenario: Scrolling down then reversing within one gesture never closes

- **WHEN** a person, in one continuous touch starting with the grid at its
  own top, drags to scroll down through the list and then, without
  lifting, reverses and drags back down past where the touch began
- **THEN** the grid keeps scrolling for the gesture's entire duration and
  the drawer does not close, regardless of where the gesture ends

#### Scenario: A downward drag from rest at the top still dismisses

- **WHEN** a person drags downward on the drawer's grid or top chrome
  while the grid is already at rest at its own top, with no gesture-borne
  scroll in between
- **THEN** the drawer closes, following the finger

#### Scenario: A fling settles before a new close drag begins

- **WHEN** a scroll fling has fully decelerated to a stop at the grid's
  own top, and the person then begins a new, separate downward drag
- **THEN** that new drag may close the drawer

### Requirement: The app drawer filters its grid by a live search query

*Grounding: `docs/design/app-drawer-review.md` §2.4. Reopens an explicit
prior deferral (`the-handheld-presents-a-coherent-shell/design.md`
decision 2, `shell-ux-critique.md` §4) at the coordinator's direction, on
review of a first redesign attempt that omitted it. Initially implemented with a compact keyboard; superseded by the shared
system-keyboard path and visible caret proven in
`docs/evidence/app-drawer/system-keyboard-board/README.md` and a plain
case-insensitive substring filter (`service_ui::filter_app_indices`).*

The app drawer SHALL present a tappable search field above its icon
grid. Tapping it SHALL raise an on-screen keyboard and filter the grid,
live, to applications whose name contains the entered text, matched
without regard to letter case. Clearing or leaving the field empty SHALL
restore the full, unfiltered grid. Selecting a filtered result SHALL
launch or pin the same real application selecting it from the
unfiltered grid would have.

#### Scenario: Typing a search query filters the grid live

- **WHEN** a person taps the search field and types characters matching
  part of an installed application's name, in either case
- **THEN** the grid immediately shows only applications whose name
  contains those characters, updating with each keystroke

#### Scenario: A filtered result launches the correct application

- **WHEN** a person taps an application shown while a search query is
  active
- **THEN** the same application that name identifies launches, exactly
  as if it had been tapped in the unfiltered grid

#### Scenario: Clearing the search restores the full grid

- **WHEN** a person clears the search field's text
- **THEN** every installed application reappears in the grid

### Requirement: Launching an app shows an instant splash until it appears

*Grounding: operator acceptance in `docs/evidence/proposal-closeout/2026-10-01/splash.md`, with prior source and board/QEMU evidence retaining their original classes and limits.*

<!-- UNVERIFIED: functional launch splash accepted by the operator, docs/evidence/proposal-closeout/2026-10-01/splash.md; prior host/QEMU proofs remain. UNVERIFIED: quantitative one-frame timing and individual physical timeout/failure cases were not newly measured. Additional capture/fault-injection reruns are waived. Shared GNOME activation/menu parity remains the Home proposal's task group 11; this splash closeout does not claim that implementation. -->

Tapping an installed application in the drawer, on Home, or in the dock
SHALL show a full-screen splash within one visible frame: the active
theme's background colour, the tapped application's desktop-entry icon
large and centred, and its name below the icon. The previously active
application or overlay SHALL NOT be visible at any point during this
transition, including momentarily. The splash's icon and name SHALL ease in
over roughly 200-250 milliseconds; the backdrop itself SHALL be fully
opaque from its first painted frame regardless of that easing. The splash
SHALL remain shown until the launched application's own window maps, at
which point the shell SHALL hand off to it as an ordinary running
application with no further splash. Matching that window SHALL NOT depend
solely on the launched entry's own identity, since a `Terminal=true` entry's
window maps under its terminal's identity instead.

When a tapped Home or dock entry has an identifiable running instance, the
shell SHALL focus that instance instead of starting a new process, and SHALL show the splash
for no more than one round trip confirming that focus -- never a splash
lasting as long as a genuine cold start.

If no window has mapped after approximately ten seconds, the splash SHALL
show an explicit "taking longer than usual" state offering a way to dismiss
it or return Home, and SHALL remain until the user acts. If the launched
process exits before any window maps, the splash SHALL show that the named
application could not be opened and SHALL dismiss itself shortly after,
without requiring a tap.

#### Scenario: A user taps an app in the drawer

- **WHEN** the user taps an installed application's entry in the drawer
- **THEN** a full-screen splash showing that application's icon and name
  appears within one frame, the previously shown drawer or app is never
  visible afterward, and the splash hands off to the application's own
  window once it maps

#### Scenario: A user taps an app pinned to Home or the dock

- **WHEN** the user taps an application pinned to Home or docked
- **THEN** the same full-screen splash appears at that tap, using the same
  icon and name resolution as the drawer, and hands off the same way once
  the application's window maps

#### Scenario: The tapped app is already running

- **WHEN** a tapped Home or dock application has an identifiable running window
- **THEN** the shell focuses that window directly, and any splash shown is
  no longer than the time needed to confirm that focus, never a splash that
  waits as long as a fresh launch would

#### Scenario: A terminal application's window maps under a different identity

- **WHEN** the tapped application has `Terminal=true` and its window maps
  as the configured terminal rather than under the launched entry's own
  application identity
- **THEN** the splash still recognizes that window as this launch's result,
  by the spawned process or its process tree rather than by application
  identity alone, and hands off correctly

#### Scenario: No window maps in time

- **WHEN** about ten seconds pass with no window mapping for the launch the
  splash is showing
- **THEN** the splash shows a "taking longer than usual" state with a way
  to dismiss it or return Home, and remains visible until the user acts

#### Scenario: The launched process exits before mapping a window

- **WHEN** the spawned process exits without ever mapping a window
- **THEN** the splash shows that the named application could not be opened
  and dismisses itself shortly after, without requiring the user to tap
  anything

#### Scenario: The compositor never shows a stale focused app during launch

- **WHEN** an application is launched from the drawer, which sits above the
  previously focused application
- **THEN** the compositor's existing overlay ordering keeps that previously
  focused application fully covered by the splash for the whole transition,
  with no compositor-side change required to prevent it from showing
  through

<!-- Closeout evidence: docs/evidence/proposal-closeout/2026-10-01/splash.md. Operator report is physical
feedback; retained host/QEMU/injected evidence keeps its original class.
No additional capture, quantitative measurement or fault injection claimed. -->

### Requirement: The side power button reaches the shell under the mainline kernel
On the mainline full shell, pressing the board's power button SHALL produce the
same shell response as under the vendor kernel (the power sheet), because the
PMU power-key input device exists.

#### Scenario: Press shows the power sheet
- **WHEN** a person presses the side button on the mainline full shell while the camera records
- **THEN** the power sheet appears on the panel and the key event is logged
*Grounding: observed on hardware 2026-10-06 (`docs/evidence/mainline-shell-parity-2026-10-06/README.md`): operator press brought up the power sheet; camera still and sway journal agree.*

### Requirement: The shell fills a whole non-panel output instead of letterboxing it

*Grounding: the normal board's accepted `wallpaper-configure 800x1280`,
`home-configure 800x1280` and `configure 800x1280`, matching native Home image
and operator acceptance are recorded in
`docs/evidence/shell-responsive/board/acceptance-2026-10-09/README.md` and
`capture.json`. The system's actual logical HDMI geometry is 800×1280.
`nix/rust-shell-client/src/main.rs` accepts a valid size when it preserves the
existing aspect guard or matches a known whole output. Existing host fixtures
cover other geometries. <!-- UNVERIFIED: physical normal-transform landscape,
arbitrary EDID modes and keyboard-exclusive-zone behavior on HDMI were not
newly qualified in this closeout. -->*

When a Wayland layer-shell `configure` gives a surface exactly the size of
a currently known output (an HDMI monitor at its own resolution, at any
aspect ratio, landscape or rotated portrait), the shell SHALL accept that
size and paint its wallpaper, Home grid/dock, and Drawer/Shade/Settings/
Power panel chrome to fill it completely, with no letterboxed or
pillarboxed band of unpainted or differently-colored space. A configure
that fails the existing aspect guard and is not the size of any known output
(in particular, a single-axis shrink such as an on-screen keyboard's exclusive
zone) SHALL continue to be rejected exactly as before this requirement existed,
leaving the surface at its last accepted geometry. Aspect-preserving resizes
SHALL retain their existing acceptance behavior.

This requirement governs whether the *surface itself* is allowed to take
the output's full size and whether what already reflows (the wallpaper
fill, Home's row count, panel chrome) is allowed to do so. It does not by
itself require every on-screen element to relayout for the new size:
`paint_wifi`'s own pre-existing non-uniform scale and the theme chooser are
untouched by this requirement and remain named, out-of-scope follow-up work
in `design.md`.

#### Scenario: An HDMI monitor is configured at its own landscape resolution

- **WHEN** the compositor sends a layer-shell `configure` whose size
  matches a connected HDMI output's own logical size (e.g. 1920x1080)
- **THEN** the shell accepts that size for the surface, and the wallpaper,
  Home, and any open Drawer/Shade/Settings/Power panel fill it edge to edge
  with no pillarboxed column

#### Scenario: An on-screen keyboard's exclusive zone shrinks one axis

- **WHEN** a `configure` reduces only the surface's height (or only its
  width), beyond the existing aspect tolerance, to a size that does not match
  any known output's own logical size
- **THEN** the shell rejects that configure and keeps the surface at its
  last accepted geometry, exactly as it did before this requirement

#### Scenario: The Drawer reflows its column count with a wider output

- **WHEN** the Drawer is open on a surface wider than the 568px design width
- **THEN** its app grid uses more columns, proportional to the extra width,
  instead of the same 4 columns stretched into wider, sparser tiles

### Requirement: Home's grid reflows its column count without losing or reordering pinned items

*Grounding: `nix/rust-shell-client/src/home_state.rs`'s `HomeLayout::
reflow_to` and its own `columns` field, `home_grid::columns_for_width`, and
`home_screen::HomeScreen::sync_columns`, all read for this change. Proven
host-side by `home_state.rs`'s `reflow_to_a_wider_column_count_never_loses_
or_reorders_items`, `reflow_to_round_trips_4_then_8_then_back_to_4`,
`reflow_to_is_a_no_op_when_columns_already_match`, `reflow_to_keeps_a_
multi_span_widget_intact_as_one_item`, and `home_screen.rs`'s `sync_columns_
reflows_to_a_wide_output_and_back_without_losing_items` -- host unit tests.
The operator accepts the Home target on the real
800×1280 HDMI arrangement in
`docs/evidence/shell-responsive/board/acceptance-2026-10-09/operator-report.json`.
<!-- UNVERIFIED: the wider-grid pinned-item drag, multi-span widget and
round-trip placement guarantees remain host-tested; no new physical sequence
exercises every placement state. -->*

The Home screen's grid SHALL use more columns, proportional to the
surface's own width (the same reflow the Drawer's grid already uses),
instead of a fixed column count that leaves a wide output's extra space as
bigger gaps between the same four columns. The dock SHALL retain its existing
four slots; whether/how its slot count reflows is preserved in
`the-hdmi-shell-works-in-landscape` task 7.3. Every icon, folder, and widget
already pinned to the grid SHALL remain present after a column-count
change, in its original relative reading order (top-left to bottom-right,
page by page); a widget's multi-cell span SHALL remain a single, contiguous,
non-overlapping footprint at the new column count. Reflowing to a column
count already in effect SHALL NOT alter the stored layout.

#### Scenario: An HDMI monitor is configured wider than the panel

- **WHEN** Home is displayed on a surface wider than the 568px design width
- **THEN** its grid uses more columns, proportional to the extra
  width, and every previously pinned item is still present, in its
  original relative order

#### Scenario: The output returns to the panel's own width

- **WHEN** Home's surface returns to exactly 568px wide after having been
  reflowed wider
- **THEN** the grid returns to exactly 4 columns and every item is restored
  to its original page and slot

### Requirement: Settings' body content is a centered, density-scaled column

*Grounding: `nix/rust-shell-client/src/lib.rs`'s `density_scale` and
`settings_content_transform`, `render.rs`'s `scene` (the transformed block
in its `Route::Settings` arm) and `settings_panel_h`, and `service_ui.rs`'s
`panel_intent` (the matching touch-point remap), all read for this change.
Proven host-side by `lib.rs`'s `density_scale_is_pixel_identical_at_native_
and_bounded_above`, `settings_content_transform_fills_the_panel_at_native_
size`, and `service_ui.rs`'s `settings_row_taps_follow_the_scaled_centered_
content_column_on_hdmi` (which maps a real touch point through the same
transform `scene` paints with and confirms it still resolves to the
correct row, and that a point past the row still misses). The operator
accepts the real Settings row target in the same HDMI arrangement, recorded in
`docs/evidence/shell-responsive/board/acceptance-2026-10-09/operator-report.json`.
<!-- UNVERIFIED: physical normal-transform landscape and optical typography/
readability across arbitrary densities are not proved by these observations. -->*

Settings' body content (the row cards, sliders, and Power section below the
unscaled header strip) SHALL paint within a centered column no wider than
the design's own 568px, scaled up on a surface taller and denser than the
568x1232 design so its rows and text are not left disproportionately small
relative to the extra space, and the panel containing it SHALL grow to
match that scaled content's own real height instead of remaining a short,
content-sized "stub" over empty space below it. A tap SHALL resolve against
that same centered, scaled position -- never the row's un-transformed
design-unit position -- so a real touch always lands on what is actually
drawn there.

#### Scenario: Settings is opened on a wide landscape HDMI output

- **WHEN** Settings is displayed on a surface wider than the design's own
  568px
- **THEN** its body content paints in a centered column no wider than 568
  design px times the surface's own density scale, not stretched edge to
  edge

#### Scenario: Settings is opened on a tall, dense HDMI output

- **WHEN** Settings is displayed on a surface both taller and denser than
  568x1232
- **THEN** its body content paints larger, proportional to that density,
  and the panel containing it grows to match instead of leaving empty
  space below a content-sized stub

#### Scenario: A person taps a Settings row on a scaled, centered output

- **WHEN** a person taps where a Settings row (e.g. the Reboot card) is
  actually drawn on a surface where the content column is scaled and/or
  offset from the panel's own left edge
- **THEN** that row's action fires, exactly as it would at the row's
  design-unit position on the native panel
