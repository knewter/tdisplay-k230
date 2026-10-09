# Responsive HDMI physical acceptance — 2026-10-09

The operator answered the concrete remaining checks: "home/all apps/settings
worked fine. home fills the screen. all that stuff works on hdmi". This accepts
filled Home without side bars and correct Home app, All Apps app and Settings
row activation in the current HDMI arrangement. The panel touchscreen acts as
a touchpad in that arrangement. This is operator-reported physical evidence;
no camera or monitor photograph was obtained. The photograph was waived earlier.

`capture.json` identifies the same normal boot, system and Rust shell as the
accepted hotplug runtime: boot `4bf73b24-a16a-4786-96fb-f1288244d96f`, system
`yl3si5ak6yi709yg1fqsnwgq0zn4xfcs`, Rust package `q2rxmp980f9kxi962f29333z9pbixvbk`.
The resolved compositor executable is recorded separately. HDMI physical mode
is 1280×800 at 59.910 Hz, transform 90, scale 1, logical 800×1280. Sanitized
current-boot journal records show `wallpaper-configure 800x1280`,
`home-configure 800x1280` and `configure 800x1280` accepted by the shell.

Command from the change worktree:

```sh
python3 docs/evidence/shell-responsive/board/acceptance-2026-10-09/capture-board.py --output /protected/private-responsive-capture
```

The output must be a new protected directory. The diagnostic holds
`/tmp/k230-board.lock` while using `/dev/ttyACM0`; its committed source records
the exact remote commands. It reads the existing runtime-state inspector,
extracts only numeric configure records, identifies the live compositor, sends
`card_shell home`, then captures with `runuser -u shell -- env
XDG_RUNTIME_DIR=/run/shell WAYLAND_DISPLAY=wayland-1 grim -c
/run/shell/responsive-closeout-home.png`. The UART transcript remains private;
only sanitized JSON and the inspected image are committed.

The native image was captured at 2026-10-09T21:56:59.676454Z and transferred over
UART. Board and host SHA256 match:
`0938edbc429fe58e4ccc4f16e4f25e163b8a8c3664f8a298bed8b8c19bfc7f1d`,
359,917 bytes. It is 800×1280 and inspection shows wallpaper/Home content across
the entire width without a pillarbox band. The capture follows an injected Home
command; physical target acceptance comes from the separate operator report.

This completes responsive tasks 6.1/6.2; all 19 retained tasks are complete.
Original tasks 6.3–6.5 remain unchecked in landscape as 7.1–7.3 under the
committed scope decision. Existing host tests/fixtures retain their original
proof class. No optical motion/readability, arbitrary EDID, normal-transform
landscape, numeric latency or new real-touch pinned-item round-trip result is
inferred. No new system image, service implementation or default is installed.

Ownership: `closeout/responsive-output-2026-10-09`, worktree
`/home/jadams/tmp/k230-responsive-close-final`, closeout base
`c0ec1ea9622d17d58d29a4d7d98edb1d3dd91cab` (initial branch base `88655ee0`).
Owned paths: responsive proposal/archive, the resulting `runtime/shell` main
spec through the archive CLI, this evidence directory and related README,
blob inventory and relevant work-board entries/references. The board slot was
held only for the capture and released. No build slot was taken.
