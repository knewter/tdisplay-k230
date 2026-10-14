# Sway crash when HDMI is plugged into the landscape image

Board: second board, keyboard case, installed landscape profile
(`.#kernelMainlineDrmShellLandscapeBootFiles`), 2026-10-14.

## Operator report

Operator, 2026-10-14: "hdmi didn't work idk why i plugged it up … nothing
happened", then "i had to unplug the hdmi, the board showed a white screen and
when i unplugged it rebooted" / "it might not have been reboot might've been
shell crashing".

## What the journal shows (evidence class: board-read)

`journalctl` on the board, cable plugged at 02:58:41 CDT (trimmed):

```
02:58:41 sway[1052]: [wlr] [backend/drm/backend.c:139] Received hotplug event for /dev/dri/card0
02:58:41 sway[1052]: [wlr] [backend/drm/drm.c:1778] Scanning DRM connector 52 on /dev/dri/card0
02:58:41 sway[1052]: [wlr] [backend/drm/drm.c:1869] 'DSI-1' disconnected
02:58:41 sway[1052]: [sway/card_shell.c:631] K230_CARD_SHELL mirror-release id=5
02:58:41 sway[1052]: [sway/desktop/transaction.c:821] Transaction 0x2fa2b867d0 committing with 1 instructions
02:58:41 sway[1052]: [sway/desktop/transaction.c:717] Applying transaction 0x2fa2b867d0
02:58:41 kernel: sway[1052]: unhandled signal 11 code 0x1 at 0x0000000000000068 in libwlroots-0.20.so[7fcd0,36be735000+135000]
02:58:41 kernel: epc : 00000036be7b4cd0 ra : 0000002fa2836c7e … a0 : 0000000000000000
02:58:41 systemd-coredump[1226]: Process 1052 (sway) of user 1000 terminated abnormally with signal 11/SEGV, processing...
02:59:38 systemd[1]: shell.service: The kernel OOM killer killed some processes in this unit.
```

The kernel did not reboot. Sway crashed. systemd-coredump then read the
~600 MB core of Sway's shared memory, which ran the board out of memory, and
the OOM killer took the rest of the session. The session restarted at
03:00:03, which looked like a reboot from the glass.

Symbolized from the core (host, against the deployed store paths): `epc` is
`wlr_scene_output_set_position+0xa` in wlroots (load base `0x36be735000`,
offset `0x7fcd0`), dereferencing a NULL `scene_output` (`a0 = 0`,
`badaddr 0x68`). `ra` is in Sway's `transaction_progress`, reached through
`arrange_root`. Sway's base came from `gp = 0x2fa28a14f8`.

Sequence: wlroots tore down `DSI-1`. Sway's output teardown cleared that
output's `scene_output` but had not yet removed it from `root->outputs`. Sway
then called `card_shell_output_disable`, which left the card overview through
`restore()`. `restore()` committed a transaction, `arrange_root()` walked
`root->outputs`, and passed the half-destroyed output's NULL `scene_output` to
`wlr_scene_output_set_position()`.

Two questions are still open, and HDMI task 8.7 depends on them. Why did the
kernel's HPD worker report `DSI-1` disconnected? And did it ever report
`HDMI-A-1` connected? Only connector 52 (`DSI-1`) was scanned before the crash.

## Fix

`nix/card-shell/adapter.c`: `handle_output_destroy` sets `output_teardown`
around `cs_leave`, and `restore()` skips `transaction_commit_dirty()` while it
is set. Sway commits its own transaction once it has moved the output's
workspaces.

## Forced disconnect on the fixed build (evidence class: injected, sysfs)

Deployed system `/nix/store/i7r10d4x…` (bundle `bundle-teardown`). The overview
was opened with `swaymsg card_shell enter`, then
`echo off > /sys/class/drm/card0-DSI-1/status`, 08:57 CDT:

```
08:57:01 sway[1069]: [wlr] [backend/drm/drm.c:1869] 'DSI-1' disconnected
08:57:01 sway[1069]: [sway/card_shell.c:1928] K230_CARD_SHELL restored focus=5 message=0
08:57:01 sway[1069]: [sway/tree/output.c:290] Disabling output 'DSI-1'
08:57:01 sway[1069]: [sway/tree/output.c:307] Destroying output 'DSI-1'
08:57:01 sway[1069]: [wlr] [backend/drm/drm.c:984] connector DSI-1: Turning off
08:57:02 sway[1069]: [sway/config/output.c:1072] Commit of 0 outputs succeeded
08:57:06 sway[1069]: [wlr] [backend/drm/drm.c:1861] 'DSI-1' connected
08:57:06 sway[1069]: [sway/desktop/output.c:570] New output 0x36c967ff10: DSI-1 (non-desktop: 0)
```

Sway kept PID 1069 the whole time, and the journal has no `unhandled signal`.
`echo detect` brought the panel back: `swaymsg -t get_outputs` showed `DSI-1`
active with transform 270. A native `grim` capture afterwards was 1232×568 and
showed the terminal card that had focus in the overview (`focus=5`), restored
in front.

Limits: the forced status drives the same teardown path (output destroyed while
the overview is active), but this is not a cable plug. The unfixed build was
not run through the forced test. HDMI output on the landscape image has not
been observed.
