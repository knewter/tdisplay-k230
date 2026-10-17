# App windows refit to the output after an HDMI plug or unplug

Fix: `nix/touch-trackpad/src/shell_ipc.rs` (`WindowRefit`, `REFIT_WINDOWS`),
which is scheduled from `main.rs` on every relay mode change.

## Fault (board, 2026-10-16)

The operator reported that, after an HDMI unplug, "the terminal on the
display on the device is taller than the device itself by a fair bit".
Sway's tree showed the `k230-terminal` floating window at 1280x800, at
-24,-116, on the active output, DSI-1 (1232x568). Sway sizes an ordinary
window only when it maps (`shell.nix`:
`for_window ... resize set 100 ppt 100 ppt`), so the window kept the
monitor's size.

The fixed command was run by hand first:

    swaymsg '[app_id="^(?!k230-video-).+" floating] resize set 100 ppt 100 ppt, move position 0 0'

Sway replied `success: true` twice and resized the terminal to 1232x568 at
0,0.

## Host

`cargo test --offline` in `nix/touch-trackpad` passed: 51 unit tests and 2
event-code tests, including
`an_output_change_refits_app_windows_twice_and_only_when_due`.
`cargo clippy --all-targets` reported no warnings.

## Board (2026-10-17 UTC)

The fix was deployed live (`deploy-live.sh`, commit `d4352733`). The board
ran `/nix/store/fmgszkgkc3w5x14b07dzp3bcfm4m01wj-nixos-system-nixos-26.11.20260919.20b1ddd`,
and its relay binary contains the refit command. The operator then plugged
in the HDMI monitor and unplugged it. A host loop polled Sway over SSH
every ~2 s and recorded only the samples where something changed:

    04:30:40 ['DSI-1:1232x568'] ['k230-terminal:1232x568@0,0']
    04:47:35 ['DSI-1:1232x568'] []
    04:47:40 [] []
    04:47:43 ['HDMI-A-1:1280x800'] []
    04:48:38 ['HDMI-A-1:1280x800'] ['k230-terminal:1280x800@0,0']
    04:48:48 ['DSI-1:1232x568'] ['k230-terminal:1232x568@0,0']

The relay journal (board local time, UTC-5) shows the mode changes:
Trackpad at 23:47:41, a brief DirectTouch/Trackpad flap at 23:48:19-23,
then DirectTouch at 23:48:48 with the panel connected.

After the unplug, the terminal fitted the panel in the first sample. The
operator confirmed it on glass: "works".

## Limits

- The terminal was not visible while HDMI first came up. It reappeared at
  1280x800. From these samples alone it is not known whether it was
  remapped or refit.
- The refit is sent 1.5 s and 5 s after each relay mode change. If Sway
  changed outputs later than that, the window would not be refit.
