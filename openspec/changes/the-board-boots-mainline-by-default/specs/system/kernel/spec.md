## ADDED Requirements

### Requirement: The board boots the mainline kernel by default with a proven way back
Powering on or rebooting the board SHALL boot the mainline kernel and the full
coherent shell without operator intervention, and the vendor 6.6 kernel SHALL
remain restorable as the default by a recorded, tested rollback.

#### Scenario: Power-on reaches the shell on mainline
- **WHEN** the board is reset or rebooted after installation
- **THEN** the serial console reports kernel 7.3.0-rc5, the installed mainline system is booted, and the shell services are active with no failed units
<!-- UNVERIFIED: mainline is not yet installed as the default -->

#### Scenario: Rollback restores the vendor kernel
- **WHEN** the operator runs the installer's rollback and reboots
- **THEN** the board boots the vendor 6.6 kernel with the previous system and boot files byte-identical to their recorded backups
<!-- UNVERIFIED: rollback drill not yet performed -->
