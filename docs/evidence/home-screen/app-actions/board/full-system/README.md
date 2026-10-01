# Home app actions: full-system runtime qualification

On 2026-10-01 at 21:35:55 UTC, the built coherent NixOS system activated
successfully with `switch-to-configuration test` on the physical board.
[Executed script](activate.py), [activation result](result.json) and
[retained runtime](retained.json) identify the exact system and running Rust
executable. Source is `288535289172c8465c4fa408eaa8ba2c7ab8a5ac`.

The configured kernel, initrd and modules matched the baseline. Display
configuration and wrapper settings had no difference after normalizing store
references. Shell, shell UI and theme helper were active. Both component-only
runtime overrides were removed. The persistent system profile and boot-file
hashes stayed unchanged. This is full-system **runtime** activation, not boot
selection or ordinary-boot qualification. The boot proposal remains open.

The independent root restoration timer was armed before activation. After
service/process and native pointer-delivery checks passed, its timer was retired
to leave this runtime available for testing. The exact immediate restoration
command is recorded in `retained.json`; it returns to the baseline system with
the previously accepted component overrides. A reboot still follows the existing
persistent boot selection.

The existing [pointer probe](../pointer-test.py), executed against this full
session, passed all three checks in [pointer-result.json](pointer-result.json):
actual app-menu delivery, outside dismissal, and Home retained without Drawer.
This is injected pointer input on the board, not physical mouse acceptance.

The corrected [app-action probe](actions-test.py) passed all six checks in
[actions-result.json](actions-result.json): primary activation focuses the
existing window without a duplicate, New Window creates one distinct window,
existing windows survive, subsequent primary activation chooses the most recent
window, and no third window appears. Its owned new window was closed afterward;
the pre-existing window and operator layout were retained.

Initial probes were inconclusive because their tree filter ignored the actual
`floating_con` application node and initially assumed an app_id of `foot`.
Sanitized diagnostics showed primary input delivery and app-launch-focused
markers, revealing the harness error. The corrected probe accepts both `con`
and `floating_con` and uses the actual focused window, matching production's
window enumeration. No shell source correction was required. It keeps one real
virtual-pointer connection alive throughout the sequence. This remains injected
board input; task 11.4's separate operator confirmation of primary-focus/New
Window is still open. No private tree titles or raw console logs were committed.

The source/operator-report Pages run `36929358280` succeeded and the published
`https://knewter.github.io/tdisplay-k230/work/` served revision `29c9e144`.
