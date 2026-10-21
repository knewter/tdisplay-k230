## MODIFIED Requirements

### Requirement: The splash and the panel console are a build-time choice

The system SHALL offer two configurations and default to the first: a boot
that shows the splash and puts no console on the panel, and a boot that
lights the panel from the kernel and shows the framebuffer console on it as
`the-screen-comes-up-under-linux` left it. Selecting the second SHALL be one
option in the NixOS configuration, and SHALL be what a person reaches for
when the panel path itself is being debugged.

*Grounding: the daily mainline system `k230-mainline-drm-shell` sets
`k230.panelConsole = false` (`flake.nix`), so `sdImage` and
`kernelMainlineDrmShellBootFiles` carry `logo.xrgb` and bootargs without
`console=tty0`; `nix eval` gives `false` for it and `true` for the
vendor-kernel `k230` and `k230-console`
(`docs/evidence/mainline-boot-splash/board/README.md`). That system,
`kc3iyr4c…`, is installed on the board and was filmed on warm reboots showing
the splash from stage 1 to the compositor's first frame with no kernel text on
the panel (same README). The console configuration remains the
`panelConsole = true` option, photographed in
`docs/evidence/panel-photos/05-console-on-panel.jpg`.*

<!-- UNVERIFIED: the default boot was filmed on warm reboots only, never
 from cold power-on, and on the board's one card in place rather than a
 second card. The vendor-kernel `k230` configuration still selects the panel
 console explicitly; its splash handoff was not re-proven. -->

#### Scenario: The default configuration boots

- **WHEN** the system is built with no option set
- **THEN** the boot shows the splash and no kernel text appears on the panel

#### Scenario: The panel console is selected

- **WHEN** the system is built with the panel console option
- **THEN** the boot partition carries no splash file, stage 1 leaves the panel dark, the kernel lights it and the console appears on it as before

## ADDED Requirements

### Requirement: The splash remains stable until the compositor draws

Stage 1 and the system SHALL preserve a stable splash image from its
appearance through the compositor's first frame on the default warm boot,
without transient garbled scanout frames. Stage 1 owns initial scanout setup;
the system owns preserving it until its display client replaces the image.

*Grounding for the defect: the current accepted default was filmed on a
normal warm reboot on 2026-10-20, with original distorted-frame samples and
raw camera metadata committed in
`docs/evidence/mainline-boot-splash/current-baseline-2026-10-20/board/README.md`.*

<!-- UNVERIFIED: defect removal and a full warm-boot film aligned to kernel
 time to ±0.1 s remain task 4.1. A stage 1 DMA-request correction is authorized
 for testing; vendor source and host builds do not prove this behavior. -->

#### Scenario: The default warm boot reaches the shell

- **WHEN** the default image warm boots from a visible stage 1 splash to the compositor's first frame
- **THEN** a complete film shows no transient garbled splash frame, with frame times aligned to kernel time to ±0.1 s and the evidence committed under `docs/evidence/`
