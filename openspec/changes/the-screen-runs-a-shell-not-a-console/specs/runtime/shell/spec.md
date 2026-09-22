## Purpose

Defines what owns this board's screen and touch panel once the system is up:
the compositor that draws, how it draws with no GPU driver, how a person types
with no cable, and what a touch actually does.

## ADDED Requirements

### Requirement: The shell renders on the CPU, with no GPU driver and no software GL

The compositor SHALL composite in software into DRM dumb buffers. It SHALL NOT
require OpenGL, OpenGL ES, Vulkan, a GBM allocator, or a DRM render node, and
the system SHALL NOT carry a Mesa GL or Vulkan runtime in order to run it.

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
- **THEN** the answer is a CPU rasteriser writing into a DRM dumb buffer, with no GL, no Vulkan, no GBM allocator and no render node anywhere in the path

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

<!-- The compositor has been started and owns the panel. Battery-only boot is
still unverified because the recorded startup retained USB cables. Grounding:
docs/evidence/shell-first-light.md, docs/evidence/shell-session.txt, and
docs/evidence/shell-features/startup/. -->

The system SHALL start the compositor without a serial cable, a login prompt or
a display manager, and the compositor SHALL take the panel at its native
568x1232 in portrait, with no rotation and no scaling.

**A compositor that starts is not a shell that works.** The evidence SHALL be a
photograph of the physical screen together with the compositor's log, because a
Wayland session can report a successful mode set and present nothing — the same
failure this board already produced once, when the Wi-Fi driver reported
`start ap successs!` and transmitted nothing.

#### Scenario: The board is powered on with nothing attached

- **WHEN** the board boots with no cable connected
- **THEN** the compositor is running with a terminal visible on the panel, photographed

#### Scenario: The compositor log is read

- **WHEN** the compositor's startup log is examined
- **THEN** it names the software renderer and the dumb-buffer allocator it selected, and reports no failed attempt to open a render node as an error

### Requirement: A person can type on the board with no cable attached

<!-- The user typed `ls` and its output was recorded on the panel; the feature
gallery also records injected keyboard show/hide and typing. Whether a real
finger can summon and dismiss the keyboard remains unverified. Grounding:
docs/evidence/shell-first-light.md and docs/evidence/shell-features/. -->

The shell SHALL present an on-screen keyboard that a person can summon and
dismiss by touch, and characters typed on it SHALL reach the focused
application.

#### Scenario: Someone types a command with no cable attached

- **WHEN** a person summons the keyboard and types a command into the terminal on the panel
- **THEN** the command runs and its output appears on the panel, photographed

#### Scenario: The keyboard is dismissed

- **WHEN** the keyboard is dismissed
- **THEN** the application underneath is fully visible again and usable

### Requirement: A touch activates what is under the finger

<!-- The controller is mapped and injected taps activate the menu, but full
real-glass coordinate accuracy remains unverified. Grounding for the injected
path: docs/evidence/shell-injected-pointer.txt and
docs/evidence/shell-features/. -->

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

### Requirement: The cable-free session has practical touch controls

<!-- The menu workflow is demonstrated by injected uinput, including launch,
window switching, keyboard, recovery, and cancelled system confirmations.
Those recordings do not prove a real GT9895/glass tap, so the full hardware
claim remains unverified. Grounding: docs/evidence/shell-features/index.html,
its adjacent manifests, and docs/evidence/shell-virtual-touch.txt. -->

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

### Requirement: The shell hosts Dozer's shell; it is not Dozer's shell

The compositor chosen here SHALL NOT be treated as a decision about which shell
draws Dozer. It provides a surface, an input path and a way to type; what runs
on it stays open.

*Grounding: `openspec/config.yaml` defines "a shell" as "whatever draws Dozer on
this screen; not yet chosen", and `the-screen-comes-up-under-linux` names
choosing a UI toolkit as an explicit non-goal. `docs/findings.md` records the
Compose Desktop and Kotlin/Native assessments as still open.*

#### Scenario: A Dozer shell is proposed later

- **WHEN** someone proposes a way to draw Dozer on this board
- **THEN** nothing in this capability forbids it, whether it is a Wayland client, a direct DRM/KMS renderer that replaces the compositor, or something else
