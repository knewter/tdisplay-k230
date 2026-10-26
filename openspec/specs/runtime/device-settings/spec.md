# runtime/device-settings Specification

## Purpose
Defines truthful device settings and system actions that a person can understand and operate on the handheld without an external keyboard.

## Requirements

### Requirement: Settings expose only supported state and actions

*Grounding: operator acceptance and explicit additional-proof waiver in `docs/evidence/coherent-shell/operator-closeout-2026-10-10/README.md`; prior host/QEMU/board evidence retains its original provenance. This is acceptance of the installed result, not a newly recorded individual-case test or timing measurement.*
<!-- UNVERIFIED: operator acceptance and the proof waiver do not supply a new individual-case physical confirmation/failure/focus/priority recording. Existing implementation and host/QEMU results keep their original limits. -->
The shell userspace SHALL show only controls backed by a readable or writable system capability in the installed image. It SHALL identify unavailable, read-only, and pending controls explicitly. It SHALL NOT show a battery gauge or battery-dependent action without observed battery hardware and state reporting.

#### Scenario: Network state cannot be read
- **WHEN** a person opens Settings and network state is unavailable
- **THEN** the network row says unavailable and does not display a fabricated connected state

#### Scenario: Control application fails
- **WHEN** a requested change cannot be applied
- **THEN** Settings shows failure and a Retry or contextual dismissal action while preserving the last confirmed state

#### Scenario: Settings content exceeds the panel
- **WHEN** the person drags or flicks a longer Settings list
- **THEN** the rows follow the finger and settle within bounds while the current control value and contextual return route remain understandable

### Requirement: System actions require clear completion feedback

*Grounding: operator acceptance and explicit additional-proof waiver in `docs/evidence/coherent-shell/operator-closeout-2026-10-10/README.md`; prior host/QEMU/board evidence retains its original provenance. This is acceptance of the installed result, not a newly recorded individual-case test or timing measurement.*
<!-- UNVERIFIED: operator acceptance and the proof waiver do not supply a new individual-case physical confirmation/failure/focus/priority recording. Existing implementation and host/QEMU results keep their original limits. -->
The shell userspace SHALL label power and restart actions by effect, require confirmation for disruptive actions, and report denial or failure without trapping the person. Settings defaults SHALL be provided by the NixOS image for a fresh home.

#### Scenario: Restart is cancelled
- **WHEN** a person opens Restart confirmation and chooses Cancel
- **THEN** Settings returns to the shade or prior scene with prior focus and no restart request

### Requirement: A denied system action SHALL explain itself
*Grounding: `docs/evidence/recovery-routes/touch-capture-2026-10-11/README.md` (2026-10-11): a real-finger brightness drag after the backlight was made read-only over serial; the shell logged `brightness-denied`, and a native `grim` capture shows "That action isn't allowed · Done" under Settings' Done header.*
When a system action is refused, the shell SHALL show short person-facing copy and a visible Back or Retry action, and SHALL NOT render raw paths, helper output, or secrets.

#### Scenario: An action is denied
- **WHEN** a person requests a system action the system refuses
- **THEN** the surface says the action was not allowed and shows Back

### Requirement: Settings offers a keyboard backlight control only when the base has one

*Grounding: Board 2026-10-14: Settings shows the Key backlight row on the base and an injected tap toggles it (docs/evidence/keyboard-base/shell/board/); host renders show it hidden without the LED and, with it, a four-detent slider (Off, Low, Medium, High). The PWM LED has 255 steps (docs/evidence/keyboard-base/backlight/); Low, Medium and High are 8 %, 30 % and 100 % of it in `keyboard_based.py`. Board 2026-10-14: the slider on the glass previews each level live (operator) and the LED reads 20/76/255 within 0.5 s of each stored level (docs/evidence/keyboard-base/backlight/).*

When a `kbd_backlight` LED device exists, Settings SHALL offer a keyboard backlight control: an on/off switch while the device has one brightness step, and a level slider once it has more. The choice SHALL persist across reboots in system state, not in a home directory. Moving the slider to a lit level SHALL light the keys at that level within a fraction of a second, for a short preview, without a key press; outside that preview the keys stay lit only while typing. When no such device exists, Settings SHALL NOT show the control.

#### Scenario: Turning the key backlight off

- **WHEN** a person turns the keyboard backlight off in Settings and then types
- **THEN** the key legends stay dark, and stay dark after a reboot

#### Scenario: Choosing a level shows it live

- **WHEN** a person drags the keyboard backlight slider from Low to High
- **THEN** the key legends light at each level as the slider reaches it, and go dark again a few seconds after the drag if nobody types

#### Scenario: No keyboard base

- **WHEN** a person opens Settings on a board without the keyboard base
- **THEN** no keyboard backlight control appears

### Requirement: Settings offers a vision-accessibility text scale and high-contrast option

*Grounding (2026-10-16): the first implementation offered one larger step
(1.25x). On the panel (568x1232 at 4.1", about 331 ppi, 2.07 px per dp) the
default body text is 17-18 px (about 8.5 sp) and drawer labels are 14 px
(about 6.8 sp), roughly half of common phone defaults. The 1.25x step left the
drawer illegible to the operator: "the drawer is not particularly legible at
'large' text", with labels ellipsized ("Same G…") over a translucent drawer
that shows the Home clock and wallpaper through it
(`docs/evidence/coherent-shell/accessibility-scale/board/11-panel-drawer.png`).*

*Grounding (2026-10-16): the four steps and the reflow were host-tested and
rendered at every step in both orientations
(`docs/evidence/coherent-shell/accessibility-scale/README.md`, "Redesign").
On the landscape panel, native `grim` captures at 160% and 200% of Home, the
drawer, the Shade, Settings and the Vision page are in `board/13`–`23` of
that directory. The operator judged them legible on glass. Persistence across
a reboot was observed on the board with injected taps (`board/06`, `07`).
The card-shell headers' scaling is host-tested only
(`tests/test_card_shell_appearance.py`); no board capture of the card deck at
a larger step exists.*

Settings SHALL offer a person four text-size steps, 100%, 130%, 160% and 200%
of the shell's design size, and a high-contrast palette variant. Both choices
are independent of the theme currently active and of the existing
reduced-motion toggle. The 200% step follows WCAG 1.4.4 (resize text). At
every step, text SHALL reflow rather than be cut off: drawer labels wrap to
at most two lines and the drawer uses fewer columns, and Settings and Shade
cards grow to fit their text. A label is ellipsized only when it would
exceed two lines at the chosen size. With any vision option other than the
defaults, the drawer and Shade SHALL draw their text over an opaque surface,
not a translucent one that shows Home through it, and app icons and their
tap targets SHALL grow with the step up to at least 48 dp (99 px on this
panel).

The chosen scale and contrast variant SHALL apply consistently to both the
Rust-rendered surfaces (Home, drawer, shade, Settings) and the C-rendered card
deck and its labels, using the same shared theme-token mechanism that already
carries per-theme colors across that boundary, so a person does not get a
larger Settings but an unchanged card header. Home widgets keep the
proportions of their cells, so a widget's contents are not scaled by the step;
the Clock widget's date, which follows the step, is the exception. The choice SHALL persist across
restarts the same way the active theme choice already does.

#### Scenario: A person chooses a larger text size

- **WHEN** a person selects the 130%, 160% or 200% text-size step in Settings
- **THEN** Home's app labels, the drawer, the shade, Settings, and card
  headers all render at that size, not only the Settings screen itself

#### Scenario: The largest step keeps every drawer label readable

- **WHEN** the 200% step is active and the drawer is open on the panel in
  either orientation
- **THEN** every app label is shown whole on at most two lines over an opaque
  surface, with no label crossing a neighbouring tile and no icon or tap
  target smaller than 99 px

#### Scenario: A person chooses the high-contrast variant

- **WHEN** a person selects the high-contrast variant
- **THEN** the active theme's colors are overridden by the high-contrast
  palette consistently across both renderers, and the choice survives a
  reboot the same way an active theme choice does

#### Scenario: The choice is independent of other accessibility controls

- **WHEN** a person has reduced motion enabled, disabled, or has opened the
  separately planned gesture-discovery accessibility aid
- **THEN** the text-scale and high-contrast choice is unaffected by, and
  does not affect, either of those settings

### Requirement: Settings reads plainly and scrolls cleanly

*Grounding: the 2026-10-26 design review of native grim captures on the board (`the-shell-and-its-apps-look-finished` design.md); fixed-build captures in `docs/evidence/shell-design-review/README.md`.*

<!-- Grounding: injected-touch grim captures in docs/evidence/shell-design-review/README.md, and the operator's on-glass acceptance of build 1r8zfd5s on 2026-10-26 (docs/evidence/shell-design-review/operator-report.md). -->
Settings SHALL place its Vision and Themes links in the title row. While its body is scrolled, content passing under the section header SHALL meet a divider and a fade, never a bare cut through text. Control values SHALL be words a person uses: the Wi-Fi link SHALL read "Connected" or "Not connected" rather than a raw state, and the motion preference SHALL be titled "Reduce motion". The audio output SHALL show its name without an instruction suffix.

#### Scenario: Scrolled Settings
- **WHEN** Settings is scrolled so a card passes under the "Device controls" header
- **THEN** the card fades out against a divider and no half-cut line of text sits against bare background
