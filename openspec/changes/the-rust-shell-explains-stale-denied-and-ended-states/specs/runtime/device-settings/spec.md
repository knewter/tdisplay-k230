## ADDED Requirements
### Requirement: A denied system action SHALL explain itself
<!-- UNVERIFIED: no Rust-shell implementation or board observation yet. -->
When a system action is refused, the shell SHALL show short person-facing copy and a visible Back or Retry action, and SHALL NOT render raw paths, helper output, or secrets.

#### Scenario: An action is denied
- **WHEN** a person requests a system action the system refuses
- **THEN** the surface says the action was not allowed and shows Back
