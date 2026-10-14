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
