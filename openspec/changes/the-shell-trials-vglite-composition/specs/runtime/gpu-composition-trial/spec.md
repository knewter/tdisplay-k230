## ADDED Requirements

### Requirement: Actual opt-in Sway renderer backend
The system SHALL keep the current Pixman Sway session as the default. An experimental session SHALL be a Sway package built against a local wlroots renderer fork and SHALL receive the real wlroots scene render passes; a separate Wayland client or private-buffer painter does not meet this requirement.

#### Scenario: Default shell launch

- **WHEN** the shell starts without the explicit experimental selection
- **THEN** it uses the existing Pixman renderer and its existing DRM path.

#### Scenario: Experimental renderer selection fails

- **WHEN** the forked renderer cannot initialize its one VG-Lite context or validate the wlroots output-buffer format
- **THEN** the selected session returns to Pixman without a modeset or a new DRM owner.

### Requirement: Existing DRM owner retains output ownership
The experimental renderer SHALL use only the `struct wlr_buffer` supplied by the existing wlroots output path for its render pass. Sway's existing wlroots DRM backend SHALL remain the sole DRM master, swapchain allocator and scanout committer.

#### Scenario: Renderer obtains a target

- **WHEN** wlroots begins a Sway output render pass
- **THEN** the renderer may import dma-buf attributes of that supplied buffer but SHALL not open a second DRM master, allocate a competing scanout buffer, modeset, or commit a framebuffer itself.

### Requirement: Coherent per-frame fallback
The experimental renderer SHALL record a complete render pass before submitting GPU work. If target format, texture import, clipping, blending, transform, damage, color conversion, synchronization or cache requirements are not supported, it SHALL replay the complete pass through Pixman into the same wlroots-provided buffer.

#### Scenario: Unsupported scene operation

- **WHEN** one operation in a render pass is unsupported by the VG-Lite eligibility table
- **THEN** no operation from that pass is submitted to VG-Lite and the whole pass is rendered by Pixman.

#### Scenario: GPU submit failure

- **WHEN** VG-Lite fails after the renderer has selected the GPU path
- **THEN** the pass fails without committing the partially rendered buffer, and the next frame is forced through Pixman.

### Requirement: Evidence-gated promotion
The project SHALL not make the experiment default until board evidence proves actual Sway render-pass use, exact target/source formats, clipping and blend semantics used by the shell, damage correctness, completion/cache ownership, stable interaction, and a repeatable benefit compared with the same Pixman scene. Process CPU evidence SHALL state that it excludes kernel, interrupt and whole-device cost.

#### Scenario: Incomplete renderer evidence

- **WHEN** any required output ownership, operation, cache/completion, interaction, or comparison evidence is absent or fails
- **THEN** the documented recommendation retains Pixman as the default.
