## ADDED Requirements

### Requirement: The side power button reaches the shell under the mainline kernel
On the mainline full shell, pressing the board's power button SHALL produce the
same shell response as under the vendor kernel (the power sheet), because the
PMU power-key input device exists.

#### Scenario: Press shows the power sheet
- **WHEN** a person presses the side button on the mainline full shell while the camera records
- **THEN** the power sheet appears on the panel and the key event is logged
*Grounding: observed on hardware 2026-10-06 (`docs/evidence/mainline-shell-parity-2026-10-06/README.md`): operator press brought up the power sheet; camera still and sway journal agree.*
