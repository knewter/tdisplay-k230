## ADDED Requirements

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
