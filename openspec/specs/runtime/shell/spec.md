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

The system's Apps surface SHALL list visible application desktop entries from
the user's XDG data directories and Nix profile data directories, applying
user-over-system precedence and desktop visibility rules. Reopening Apps SHALL
reflect entries added or removed since the previous open. The surface SHALL
provide readable application names and touch-accessible pages when the list
exceeds the portrait display. Launching an entry SHALL preserve desktop-entry
argument expansion and working-directory semantics. Terminal applications SHALL
open in the configured terminal. A launch error SHALL leave a visible explanation
and a usable Back control.

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
  with the desktop entry's configured working directory

#### Scenario: A launch fails

- **WHEN** the selected application cannot be launched
- **THEN** the launcher reports the failure and lets the user return or choose
  another action without a physical keyboard

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

*Grounding: `docs/evidence/shell-real-touch-apps/README.md` records physical
Apps/Terminal/Monitor interaction and the user's explicit Home recovery
confirmation after the camera limitation was explained.
`docs/evidence/shell-real-touch-system/README.md` records touch followed by
reboot and automatic return to the shell. Exact confirmation labels and the
cancel action are not legible in the camera view; acceptance combines the
operator's completed procedure and overall confirmation with those recordings.
Earlier injected menu/state/failure-path evidence remains separately labeled
in `docs/evidence/shell-features/` and `docs/evidence/shell-virtual-touch.txt`.
Do not describe operator-confirmed actions as individually camera-proven.*

The shell SHALL keep a persistent touch bar with Apps, Windows/Home, Keyboard,
and System controls. Its visible targets SHALL be at least 56 pixels high and
the primary controls SHALL each be at least 128 pixels wide on the 568-pixel
panel. Apps SHALL start or focus a readable terminal and a system monitor
without a physical keyboard. Windows SHALL page through running sway windows,
wrap after the last window, and show an explicit no-windows state while keeping
Home and Back available. Its Home control SHALL return to a running terminal or
start one when it was closed. Keyboard SHALL summon or dismiss the on-screen
keyboard. System SHALL offer reboot and power-off only after a second
confirmation page that names the action and includes Cancel. A failed or denied
system action SHALL return a visible failure state with a route back to System
or Home; it SHALL NOT terminate the touch menu.

The session user SHALL have authority only for those two explicit `systemctl`
operations; no general passwordless command or root shell is part of the
control.

#### Scenario: A user returns to an application without a keyboard

- **WHEN** the user taps Apps or Windows/Home and selects Terminal, Monitor, or
  a listed sway window
- **THEN** the named running application or window is focused, or Home starts
  the terminal when it had been closed, without serial or physical-keyboard
  input

#### Scenario: A user chooses a system action by touch

- **WHEN** the user taps System, then Reboot or Power off
- **THEN** the bar presents a distinct confirmation and Cancel target before
  invoking the corresponding operation

#### Scenario: A system action is denied

- **WHEN** the confirmed `systemctl` command fails or is denied
- **THEN** the bar remains available, reports the failure, and lets the user
  return to System or Home

#### Scenario: The menu is tested with injected input

- **WHEN** an `evemu`/uinput event activates a menu block
- **THEN** that result is recorded as injected-input evidence only; it does not
  close the requirement for a real finger tap on the glass

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
