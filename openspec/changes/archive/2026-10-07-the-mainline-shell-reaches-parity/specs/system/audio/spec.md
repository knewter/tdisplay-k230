## ADDED Requirements

### Requirement: Audio playback runs under the mainline kernel without disturbing the system
On the mainline full shell, PCM playback to the board's audio card SHALL complete
the same way it does under the vendor kernel, through the DMA path, without
freezing or otherwise disturbing the running system. The bare board has no
speaker or buzzer (the MAX98357A amplifier is on an optional base board that is
not fitted), so audible output is checked separately on the 3.5 mm jack when a
headset is attached.

#### Scenario: Playback completes
- **WHEN** an operator runs `speaker-test -D plughw:0,0 -c1 -t sine -f 440 -l1` on the mainline shell
- **THEN** it exits 0 with the same period and buffer sizes the vendor kernel reports, and the serial console stays responsive
<!-- Observed 2026-10-06 (docs/evidence/mainline-shell-parity-2026-10-06/README.md): exit 0, 48000-frame buffer, 2.09 s periods with ordinary cleanup; console responsive. -->

#### Scenario: Audible output on the headphone jack
- **WHEN** a headset is attached to the 3.5 mm jack and the same tone plays
- **THEN** the tone is heard and lowering the volume makes it quieter
<!-- UNVERIFIED: deferred until the operator attaches a headset; not required for this change -->
