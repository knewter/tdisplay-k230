# runtime/video Specification

## Purpose
Provides a reproducible network-video path for the handheld shell and distinguishes
software playback, optional MVX hardware decoding, audio, and physical presentation.

## Requirements

### Requirement: The image provides a reproducible software video baseline

*Grounding: `docs/evidence/network-video/integration-host.md` records the pinned player and source boundary. `docs/evidence/final-shell-image/README.md` records the flashed default image, installed player wrapper and successful Apps playback/cleanup; `docs/evidence/network-video/midstream-error/README.md` records interrupted-stream recovery.*

The Nix image SHALL provide a version-pinned player and FFmpeg path that can open
a runtime-supplied HTTP(S) or DASH media URL with software H.264 decoding and the
existing CPU Wayland output. A protected network credential, URL, or derived secret
MUST NOT be stored in Nix configuration, source control, process arguments, or the
Nix store.

#### Scenario: A public DASH stream is opened

- **WHEN** the operator supplies the documented public Big Buck Bunny manifest and selects the measured 480x270 H.264 representation
- **THEN** the player opens it with software decoding and records the selected representation, output path, audio setting, decoder drops, video-output drops, and cache result

#### Scenario: The network source is unavailable

- **WHEN** the URL cannot be resolved, fetched, or read after playback starts
- **THEN** the player reports a recoverable error and returns to the shell without leaving a stuck window or protected runtime material

### Requirement: Hardware decode is an explicit optional path

The system SHALL keep the MVX V4L2 decoder experiment separate from the software
baseline. Hardware decoding MUST be enabled only when the device, format, and output
path are verified on the board; a failed or unsupported MVX attempt SHALL fall back
to the known software path without claiming hardware acceleration.

*Grounding: `docs/evidence/network-video/recovery-fixed/README.md` records a forced MVX initialization failure followed by a distinct software child with advancing media time. `docs/evidence/network-video/strict-comparison/README.md` records strict MVX selection and over 30 seconds of steady playback/presentation. The experiment remains limited to the documented known-30-fps source; general MVX timestamps and seek smoothness remain UNVERIFIED, and software remains the default.*

#### Scenario: MVX playback is attempted

- **WHEN** the operator selects the hardware decoder experiment on a board exposing the audited MVX V4L2 device
- **THEN** the evidence identifies the decoder device and negotiated format, and records whether decoded frames reach the panel or the player falls back to software

### Requirement: Video acceptance distinguishes decode from presentation

Playback evidence SHALL identify source frame rate and selected representation,
report decoder and output-drop counters, and include at least 30 seconds of timing
samples that distinguish decoded frames from actual presentation or scanout. A native
compositor screenshot alone MUST NOT be treated as proof of sustained presentation.

*Grounding: `docs/evidence/network-video/README.md` records >30-second per-frame presentation feedback, declared clock, event flags and kernel IRQ path, separately from decoder/output counters and physical photographs.*

#### Scenario: A playback trial is accepted

- **WHEN** a bounded trial runs for at least 30 seconds on the target image
- **THEN** the report includes source and player provenance, decoded-frame correctness, presentation-timing evidence, CPU samples, cache behavior, and explicit limitations

### Requirement: Audio is measured separately from video

*Grounding: `docs/evidence/big-buck-bunny/README.md` records explicit `--audio=no` video trials and makes no audio-output claim.*

The player SHALL expose whether audio is disabled, decoded, or presented. Video
acceptance MUST NOT imply audio acceptance when audio is disabled or lacks measured
physical output evidence.

#### Scenario: A silent baseline is recorded

- **WHEN** the trial runs with audio disabled
- **THEN** the report labels it video-only and leaves audio usability unverified
