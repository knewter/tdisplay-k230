# Physical keyboard interaction

The user performed this test on the board on 2026-09-23 UTC and reported
that the command produced the correct output. The [operator report](operator-report.txt)
is distinct from the [camera audit](video-audit.md).

The board runs the corrected splash diagnostic system
`/nix/store/24h4sb1msncgbasnwl3ckdlxqf9v2g6r-nixos-system-nixos-26.11.20260919.20b1ddd`;
[preflight](preflight.txt) identifies it and the active shell, seatd and firewall.
Its image provenance is in
[the initial-scene trial](../splash-initial-scene-ready/build.txt). No image was
flashed, home state restored, or input injected in this session.

The [first camera clip](20260923T000200Z-keyboard-real-touch.mp4) records
physical hand contact during keyboard interaction. It was finalized after the
user reported done: 85.033333 seconds of the requested 180-second maximum.
The manifest records the deliberate SIGINT and successful container probe.
The [native result](after-test-native.png) shows an initial `exho` failure and
a subsequent successful `echo 1qazoplm`, with the letter `o` in its argument.
This differs from the requested zero but remains asymmetric across the layout.
The camera's angle/glare limits character and keyboard-state verification;
see the audit rather than treating native pixels as physical scanout proof.

[Observer setup](observer-start.txt) starts `evtest` on the physical Goodix
device without grabbing it. [Touch events](touch-events.txt) capture real
device contacts; the observer was stopped and its PID file removed after the
test. [Fresh input state](input-mapping-json.txt) reports the identity libinput
matrix `[1, 0, 0, 0, 1, 0]`. Source `nix/dts/k230-tdisplay.dts` supplies
1024×2400 input dimensions with no swap/invert properties; `nix/shell.nix`
uses native portrait output and maps touch to `DSI-1`. Mapping to an output
is not an axis correction. No calibration change was made by this test.

The first clip does not by itself prove every intended key hit, the full
show/hide sequence, a directional drag, or operation without a host connection.

## Visibility follow-up and acceptance

The [focus-30 follow-up](20260923T001007Z-keyboard-visibility-real-touch.mp4)
ran for its full 90 seconds. Its [audit](visibility-followup-audit.md) records
the physically [hidden keyboard](physical-keyboard-hidden-49s.png) and the
[shown keyboard](physical-keyboard-shown-56s.png) after finger interaction.
It ends shown; the hide transition itself is not visible. The earlier
[native state](visibility-followup-native.png) is hidden and the later
[native state](after-followup-native.png) is shown. The operator confirmed
completion of the keyboard sequence. Acceptance combines that direct report
with the physical states, rather than claiming a filmed hide transition.

The operator confirmed correct output from the asymmetric `1qazoplm` command.
That spans both sides and multiple rows and does not show a systematic
rotation or mirroring fault. The initial `exho` entry remains recorded; this
is not a claim that every individual tap was error-free. No axis correction
was needed or added: the fresh runtime matrix and source properties above
show zero correction layers. A deliberate full-panel directional drag was
not recorded in this session. Camera focus was restored to 90 afterward.
