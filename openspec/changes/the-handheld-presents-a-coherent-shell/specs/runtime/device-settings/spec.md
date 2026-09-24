## Purpose

Defines truthful device settings and system actions that a person can understand and operate on the handheld without an external keyboard.

## ADDED Requirements

### Requirement: Settings expose only supported state and actions
<!-- UNVERIFIED: proposed settings surface; existing system menu and Wi-Fi evidence do not prove this view. -->
The shell userspace SHALL show only controls backed by a readable or writable system capability in the installed image. It SHALL identify unavailable, read-only, and pending controls explicitly. It SHALL NOT show a battery gauge or battery-dependent action without observed battery hardware and state reporting.

#### Scenario: Network state cannot be read
- **WHEN** a person opens Settings and network state is unavailable
- **THEN** the network row says unavailable and does not display a fabricated connected state

#### Scenario: Control application fails
- **WHEN** a requested change cannot be applied
- **THEN** Settings shows failure and a Retry or Back action while preserving the last confirmed state

#### Scenario: Settings content exceeds the panel
- **WHEN** the person drags or flicks a longer Settings list
- **THEN** the rows follow the finger and settle within bounds while the current control value and Back route remain understandable

### Requirement: System actions require clear completion feedback
<!-- UNVERIFIED: proposed integration with existing system actions. -->
The shell userspace SHALL label power and restart actions by effect, require confirmation for disruptive actions, and report denial or failure without trapping the person. Settings defaults SHALL be provided by the NixOS image for a fresh home.

#### Scenario: Restart is cancelled
- **WHEN** a person opens Restart confirmation and chooses Cancel
- **THEN** Settings returns with prior focus and no restart request
