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

A further automatic primary-focus/New Window probe was inconclusive. Its first
version assumed an existing Foot window, which full session activation had
removed. Subsequent seeded probes did not observe an app window after a primary
virtual-pointer dock click, including after keeping the pointer connection alive
for 300 ms after release. No successful focus/New Window result is claimed; the
cause is not established as either harness delivery or shell behavior. The
previous paired cross-compositor/client fixture passes those cases, and separate
operator confirmation remains pending. No private tree titles or raw console
logs were committed.

The source/operator-report Pages run `36929358280` succeeded and the published
`https://knewter.github.io/tdisplay-k230/work/` served revision `29c9e144`.
