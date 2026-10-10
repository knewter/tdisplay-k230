## MODIFIED Requirements

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
