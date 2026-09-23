## Purpose

Provide an opt-in validation path for GPU prerequisites while preserving the
working shell and the live display owner's control of the panel.

## ADDED Requirements

### Requirement: Optional bounded GPU validation package
The system SHALL expose a source-built, optional GPU validation package outside
the default system closure. Its board invocation MUST report each probe's
completion and sampled color results, and MUST return nonzero if a required GPU
operation or its explicit pixel assertion fails.

#### Scenario: Host build of the validation package
- **WHEN** an integrator builds the package with the pinned cross toolchain
- **THEN** the build produces the validation executable without rebuilding or
  changing the system image.

#### Scenario: Board validation failure
- **WHEN** a GPU operation, explicit completion, or asserted sample fails
- **THEN** the executable reports the failed probe and exits nonzero without
  making a modeset or a framebuffer commit.

### Requirement: Non-invasive DRM dma-buf validation
The GPU validation path SHALL create and export a private RGB565 DRM dumb
buffer, import that dma-buf into VG-Lite, and verify the resulting buffer
through its CPU mapping. It MUST NOT acquire DRM master, set a CRTC, create a
framebuffer, or select a plane.

#### Scenario: Shell owns the live display
- **WHEN** the shell and its DRM owner are active during the validation
- **THEN** the validation reports whether dumb-buffer export/import succeeds
  while leaving the current scanout configuration untouched.

### Requirement: Evidence-bounded renderer decision
The project SHALL record RGB565, alpha/color, dma-buf, and timing outcomes
separately. A passing private-buffer or dma-buf probe MUST NOT be described as
an accelerated compositor, display scanout, or video pipeline.

#### Scenario: Board evidence is incomplete
- **WHEN** any prerequisite probe has not run successfully on the physical
  board
- **THEN** the integration recommendation identifies that missing prerequisite
  and does not enable a GPU renderer in the system.
