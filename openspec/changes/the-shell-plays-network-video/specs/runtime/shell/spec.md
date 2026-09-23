## ADDED Requirements

### Requirement: Apps provides recoverable network video controls

The shell SHALL expose a visible terminal video entry through Apps. A user SHALL be
able to launch the documented player, stop or leave it with Back/Home, and return to
the existing shell controls without an external keyboard. A failed launch, closed
stream, or network error SHALL leave a usable recovery path.

<!-- UNVERIFIED: the existing shell has Apps, Back, Home, and terminal recovery,
but the integrated video entry and its network-error path are not yet implemented
or physically exercised. -->

#### Scenario: A user starts video

- **WHEN** the user opens Apps and selects the video entry
- **THEN** a terminal video session starts with the configured player and remains reachable through the shell's normal window controls

#### Scenario: A user leaves video

- **WHEN** the user taps Back or Home while the video session is focused
- **THEN** playback stops or is safely backgrounded according to the documented policy, and the shell returns to a usable terminal or Apps surface

#### Scenario: Playback fails

- **WHEN** the player exits because the source, network, or decoder fails
- **THEN** the user sees a recoverable error or returns to Apps without a dead overlay, orphaned process, or secret-bearing runtime file
