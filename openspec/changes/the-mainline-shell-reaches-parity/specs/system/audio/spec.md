## ADDED Requirements

### Requirement: Sound plays from the speaker under the mainline kernel
On the mainline full shell, the board's speaker SHALL play audio routed through the
same PipeWire session the vendor-kernel shell uses, and the shell's volume control
SHALL change what is heard.

#### Scenario: Test tone is heard
- **WHEN** an operator plays a test tone through the default PipeWire sink on the mainline shell
- **THEN** the tone is audible from the board's speaker (a person or a recording microphone confirms it)
<!-- UNVERIFIED: no K230 audio driver exists in mainline yet -->

#### Scenario: Volume changes loudness
- **WHEN** the shell's volume slider is lowered during playback
- **THEN** the tone becomes quieter
<!-- UNVERIFIED -->
