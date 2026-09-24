## Purpose

Defines a bounded, privacy-aware way for the handheld shell to preview, revisit, act on, and dismiss system and application notifications.

## ADDED Requirements

### Requirement: Preview and history share one event state
<!-- UNVERIFIED: no notification center or physical preview behavior has been observed. -->
The shell userspace SHALL show a brief preview for an eligible new event and retain it in a reachable history until dismissal or expiry. System SHALL offer a Notifications entry and indicate pending events; a preview SHALL open its event when tapped. The history SHALL show source, time, readable summary, and whether an action remains available; dismissing a preview SHALL NOT silently erase history.

#### Scenario: Preview times out
- **WHEN** a non-urgent preview times out without interaction
- **THEN** the preview leaves the active surface and its event remains reachable in history

#### Scenario: History is empty
- **WHEN** the person opens Notifications with no retained events
- **THEN** it shows an empty message and a Back route

#### Scenario: Scroll through history
- **WHEN** the person drags or flicks a longer notification history
- **THEN** the list follows the finger, coasts within its content bounds, and can be stopped by a new touch without opening an entry

### Requirement: Actions and dismissal are explicit
<!-- UNVERIFIED: proposed action policy. -->
The shell userspace SHALL offer only actions whose target is currently available and SHALL distinguish opening an event from dismissing it. A failed action SHALL leave the event reachable with a short error and Retry or Back route. Dismiss All SHALL require a clearly labeled control and SHALL NOT dismiss an ongoing critical system event.

#### Scenario: Target app is gone
- **WHEN** a person selects an event whose action target has exited
- **THEN** the shell reports the unavailable target and keeps the event until the person dismisses it

#### Scenario: Swipe an event sideways
- **WHEN** the person swipes a dismissible history item sideways
- **THEN** the item follows the finger and exposes a Dismiss cue; a short or reversed swipe returns it without dismissal, while a completed swipe removes only that event from history

### Requirement: Privacy and interruption have safe defaults
<!-- UNVERIFIED: proposed privacy and priority behavior. -->
The shell userspace SHALL hide sensitive body text in unsolicited previews by default, showing a neutral source and summary until the person opens history. It SHALL distinguish ordinary, important, and critical events: ordinary previews SHALL not take keyboard focus; important previews SHALL remain non-modal; critical events SHALL explain the immediate condition and preserve a visible recovery route. Unknown senders SHALL use ordinary priority with a hidden body.

#### Scenario: Typing during ordinary event
- **WHEN** an ordinary notification arrives while the person types
- **THEN** input focus stays in the app and the preview does not cover the focused input or keyboard controls

#### Scenario: Unknown event source
- **WHEN** an event with no trusted source metadata arrives
- **THEN** its preview omits private body text and its history entry identifies the source as unknown
