# Offline Help and app checks on the physical board

2026-09-22 America/Chicago (2026-09-23 UTC). These are software-injected touches
on the physical K230, with native compositor screenshots. They do not establish
finger accuracy, physical scanout, or a reboot into the new image.

The unchanged running system was
`/nix/store/24h4sb1msncgbasnwl3ckdlxqf9v2g6r-nixos-system-nixos-26.11.20260919.20b1ddd`,
boot `8915db67-9428-4b87-95fa-f83f075bc7cf`. The reviewed launcher was cross-built
as `/nix/store/jwgm6yid3y51ffvn85b7hy4fm80cjfn8-k230-touch-launcher-riscv64-unknown-linux-gnu-0.1`
(wrapper `/nix/store/qiray0dda5gf175fbkwab36hhmwzhwcs-k230-touch-launcher`).
Its binary ran temporarily from `/run/k230-help-test`, under user `shell`, using
the existing session's environment wrapper. No home-directory state was restored.
The `nnn` output was imported with `nix-store --import` for this trial; final
package selection belongs in `nix/shell.nix`, not that temporary import.

## Help and error recovery

[Navigation commands](navigation-console.txt) and the resulting
[page 1](help-page-1.png), [page 2](help-page-2.png),
[keyboard-visible page 3](help-keyboard-page-3.png), and
[Back to Apps](help-back-apps.png) exercise the two-page normal layout and
three-page keyboard layout. The injected device was made from the real
controller's evemu description; it was not a real finger.

A deliberately invalid desktop entry's working directory caused a visible
[launch error](launch-error.png), documented in [the console](error-console.txt).
The launcher remained open, Previous returned to the built-ins, and
[Help remained available](error-help.png); Back then returned to Apps and closed
it. The fixture lived under `/run`, not the user's application directory.
The empty-catalog case is covered separately by `tests/test_launcher_navigation.py`;
the board still discovered four existing entries, so this is not an empty board
catalog claim.

## Candidate launches

- `k230-editor.desktop` launches nano with `Terminal=true` through the existing
  Foot bridge. The first [attempt](editor-console.txt) inherited `/root` from
  the root test console and failed to change into that directory as `shell`.
  Repeating from `/home/shell`, the normal session working directory, succeeded:
  [console](editor-home-console.txt), [running editor](editor-running-home.png).
  Nano process RSS was 3,968 KiB.
- `nnn.desktop` retains the upstream terminal entry. The temporary fixture used
  its exact store executable while it was not yet installed in the system PATH.
  [Console](nnn-console.txt), [card](nnn-card.png), and
  [running browser](nnn-running.png) show the result. The starting home directory
  has no non-hidden files, hence the empty list. Process RSS was 2,688 KiB.

The on-board timestamps around the injected activation and a 0.2-second wait
span 0.682 seconds for nano and 0.663 seconds for nnn. These are process-observation
upper bounds including the injection helper and deliberate wait, not isolated
application startup or physical display-latency measurements. The earlier failed
editor attempt is retained rather than represented as a successful launch.

All three candidate packages cross-build. The closure set comparison in
`docs/evidence/offline-app-candidates/closure-deltas.json` supports nano + nnn:
nano adds no paths to the existing closure; nnn adds 441,408 NAR bytes; lf would
add 5,788,696. The rejected lf candidate has not been timed on the physical board.
