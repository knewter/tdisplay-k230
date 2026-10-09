## ADDED Requirements

### Requirement: The switch is manual, reboot-based, and self-reverting

A person SHALL be able to trigger a switch to HDMI from Settings, which
reboots the board into the HDMI device tree; the board SHALL automatically
revert to the panel device tree on the *next* boot after that, regardless
of why that next boot happened, so a crash or an unrelated power cycle
cannot leave the board silently stuck showing nothing on the panel.

*Grounding: LILYGO's `ui_hdmi_test.c` implements exactly this pattern —
`hdmi_boot_switch_thread()` (lines 312-343) writes a one-shot marker file
naming the panel DTB before copying the HDMI DTB over the active boot file
and rebooting; `ui_hdmi_test_restore_one_shot_boot()` (lines 279-300) runs
early on every subsequent boot, and if the marker exists, restores the
panel DTB and deletes the marker before continuing. Our own
`nix/sd-image.nix:142-156` documents, from hardware observation, that
U-Boot's `bootcmd` already runs a `k230_set_dtb` command reading a named
selector text file (`force_dtb`, falling back to `hdmi_dtb`/`lcd_dtb`) —
the same class of mechanism, already present and boot-tested on this
board's stage 1, that this requirement's implementation reuses rather than
inventing a new one.*

<!-- UNVERIFIED: not yet implemented (tasks.md group 3) or observed on the
board. -->

#### Scenario: A person switches to HDMI and back

- **WHEN** a person taps the HDMI switch in Settings, confirms it, and the
  board reboots
- **THEN** the board comes up on the HDMI device tree, and the next reboot
  after that — triggered any way — comes up on the panel device tree again
  with touch working, without the person having to do anything else to
  restore it

