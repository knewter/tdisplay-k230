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

<!-- UNVERIFIED: the final bar-free Home/deck/drawer/shade route awaits implementation and real-glass proof. -->
In the final normal session, the shell SHALL make its live-card deck the Home
surface. An upward gesture from the bottom of an application or shell surface
SHALL reach Home; an upward continuation from the deck SHALL reveal the
installed-app drawer, which includes named Terminal and Monitor actions.
A downward gesture from the top SHALL reveal notification history and Settings.
An inward contextual Back gesture SHALL dismiss shell overlays and keyboard
before restoring the prior scene; it SHALL NOT assume every Wayland app has a
universal Back action. The final normal session SHALL NOT keep the current
Apps, Windows, Keyboard, System, Back, or Home controls permanently on screen.
A deliberately opened accessibility aid MAY show large labeled controls; the
current persistent-bar session SHALL remain an opt-in rollback until the
required physical route and recovery proof passes.

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

#### Scenario: A user returns Home

- **WHEN** the user swipes upward from the bottom of a running app
- **THEN** the app shrinks into the live-card deck and can be selected again

#### Scenario: A user opens installed apps

- **WHEN** the user continues an upward pull from the deck
- **THEN** the installed-app drawer rises from the bottom; a short cancelled
  pull returns to the same deck

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
