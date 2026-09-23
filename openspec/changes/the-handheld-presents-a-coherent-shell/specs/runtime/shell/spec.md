## MODIFIED Requirements

### Requirement: The standalone session has practical touch controls

*Existing grounding: `docs/evidence/shell-real-touch-apps/README.md` records
physical Apps/Terminal/Monitor interaction and the user's explicit legacy Home
recovery confirmation after the camera limitation was explained.
`docs/evidence/shell-real-touch-system/README.md` records touch followed by
reboot and automatic return to the shell. Exact confirmation labels and the
cancel action are not legible in the camera view; acceptance combines the
operator's completed procedure and overall confirmation with those recordings.
Earlier injected menu/state/failure-path evidence remains separately labeled
in `docs/evidence/shell-features/` and `docs/evidence/shell-virtual-touch.txt`.
Do not describe operator-confirmed actions as individually camera-proven.*

<!-- UNVERIFIED: the new Home→Apps and named Terminal recovery behavior awaits implementation and physical proof. -->
The shell SHALL keep a persistent touch bar with distinct Apps, Windows,
Keyboard, and System controls. Its visible targets SHALL be at least 56 pixels
high and the primary controls SHALL each be at least 128 pixels wide on the
568-pixel panel. Apps SHALL start or focus a readable terminal and a system
monitor without a physical keyboard, with Terminal named explicitly as an
action. Windows SHALL page through running sway windows, wrap after the last
window, and show an explicit no-windows state while keeping Home and Back
available. Home SHALL open the safe Apps landing, whether or not a terminal is
running; Terminal SHALL start or focus a terminal as a separate labeled
recovery action. Keyboard SHALL summon or dismiss the on-screen keyboard.
System SHALL offer reboot and power-off only after a second confirmation page
that names the action and includes Cancel. A failed or denied system action
SHALL return a visible failure state with a route back to System or Home; it
SHALL NOT terminate the touch menu.

The session user SHALL have authority only for those two explicit `systemctl`
operations; no general passwordless command or root shell is part of the
control.

#### Scenario: A user returns to an application without a keyboard

- **WHEN** the user taps Apps or Windows and selects Terminal, Monitor, or a
  listed sway window
- **THEN** the named running application or window is focused, or Terminal
  starts a new terminal when it had been closed, without serial or
  physical-keyboard input

#### Scenario: A user chooses Home

- **WHEN** the user taps Home from a shell overlay or a failed action
- **THEN** Apps opens as a stable landing while Terminal remains a separately
  named recovery action

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
