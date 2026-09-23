## Purpose

Provide an evidence-gated, opt-in GPU composition trial while preserving the
working Pixman shell and the existing display owner's control of the panel.

## ADDED Requirements

### Requirement: Opt-in composition trial
The system SHALL keep Pixman as the default shell renderer. A VG-Lite
composition trial SHALL require an explicit experimental selection and SHALL
fall back to the existing Pixman session when its renderer initialization,
buffer import, or completion check fails.

#### Scenario: Default shell launch
- **WHEN** the shell starts without the experimental selection
- **THEN** it uses the existing Pixman renderer and its existing DRM path.

#### Scenario: Failed trial initialization
- **WHEN** the experimental renderer cannot initialize its sole VG-Lite context
  or import its private buffer
- **THEN** the shell starts or returns through Pixman without changing the
  current scanout configuration.

### Requirement: Bounded shared-buffer proof
The trial SHALL draw only into a private RGB565 DRM dumb-buffer dma-buf that
the trial owns. It SHALL complete GPU work before CPU or DRM consumption and
shall not import the live scanout buffer owned by another client.

#### Scenario: Private buffer composition
- **WHEN** the experimental renderer draws a nonuniform validation scene
- **THEN** captured samples and the displayed result establish the private
  buffer's RGB565 content after GPU completion.

### Requirement: Evidence-gated promotion
The project SHALL not make the trial default until board evidence establishes
stable shell interaction, correct color/alpha behavior for used operations,
frame completion ownership, and a measured benefit that survives a Pixman
comparison.

#### Scenario: Incomplete trial evidence
- **WHEN** any required renderer, cache/fence, scanout, interaction, or
  comparison evidence is absent or fails
- **THEN** the documented recommendation retains Pixman as default.
