## MODIFIED Requirements

### Requirement: The shell hosts a later application shell; it does not choose one

The compositor and the separately archived installed-application launcher SHALL
NOT be treated as a decision about which application shell draws the product
experience. They provide a surface, an input path, a way to type, and a small
way to launch installed desktop entries. The shell SHALL preserve its persistent
Apps, Windows/Home, Keyboard, System, Help, terminal, monitor, and Back routes
when the new card shell is entered, dismissed, cannot present a live card, or
requests a close.

<!-- UNVERIFIED: the card-shell composition boundary and its control handoff have not yet been observed on the board. -->

*Grounding: `openspec/config.yaml` identifies the current Sway handheld goal and
places AtomVM/Dozer integration outside its scope. The archived launcher change
is scoped to desktop-entry discovery and session utilities. `docs/findings.md`
records the application-framework assessments as still open.*

#### Scenario: A later application shell is proposed

- **WHEN** someone proposes a way to draw the product experience on this board
- **THEN** nothing in this capability forbids it, whether it is a Wayland client,
  a direct DRM/KMS renderer that replaces the compositor, or something else

#### Scenario: The card shell cannot continue

- **WHEN** the card shell is dismissed or reports an unavailable live surface or
  an unsuccessful close request
- **THEN** the existing persistent controls and application recovery routes
  remain usable without a physical keyboard
