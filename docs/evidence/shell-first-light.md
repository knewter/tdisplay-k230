# First compositor light on the physical K230

Host date: 2026-09-22. The board's unset clock reports March 17; use the
host-relative timestamps in `shell-usb-flash.txt` for this session's ordering.

## Image and recovery

`/nix/store/bfjzna9z1b5n5h1kx2qm543q5hkaisip-k230-sd-image.img`
was written through U-Boot UMS, using the observed card capacity of
249872384 sectors. `shell-usb-flash.txt` records 2308669440 bytes written
in 181.1 seconds, then all bytes compared equal through direct I/O in
185.8 seconds, before reset. Linux returned to its serial login.
The SPL and U-Boot bytes match the preserved known-good image.

This first image does **not** yet provide a working unattended shell boot.
`shell-first-start.txt` records a missing `dbus-daemon` in the shell unit's
PATH. After adding its existing store directory through a temporary unit
override, Sway ran, but its children could not find `sh` or `swaybar`.
`shell-dbus-path-fix.txt` and `shell-exec-path-fix.txt` record that diagnosis
and the temporary addition of `/run/current-system/sw/bin`. The committed
Nix fix names `dbus`, `bash`, and the selected Sway package explicitly.
The successful photographs below use this temporary PATH override.

## Compositor proof

`compositor-first-light.txt` records both probe runs as user `shell`, with
seatd and `WLR_RENDERER=pixman`, under transient systemd units:

- Unpatched Cage selects Pixman and the DRM dumb allocator, but cannot
  select XRGB8888 (`0x34325258`) on this plane. Foot reports no monitor.
- `cage-rgb565 -D -- foot` selects the same renderer and allocator and
  displays a terminal, photographed in `cage-rgb565-first-light.jpg`.
  Debug messages about unsuccessful direct scanout attempts do not mean
  renderer fallback: the scene is composited into a DRM dumb buffer.

`sway-first-light.jpg` shows the terminal and Apps, Windows, Keyboard, and
System controls. `shell-session.txt` records DSI-1 active at 568x1232,
52.190 Hz, scale 1, transform normal. This is panel evidence, not QEMU proof.

## Input mapping and current limits

Sway recognizes `0:0:Goodix_Berlin_Capacitive_TouchScreen` as touch and
reports an identity calibration matrix. Its debug log explicitly maps this
device to DSI-1. The udev query in `shell-injected-pointer.txt` reports
`ID_PATH=platform-91408000.i2c` and `ID_INTEGRATION=internal`.

The explicit `input type:touch map_to_output DSI-1` configuration takes the
`MAPPED_TO_OUTPUT` branch in pinned Sway's `sway/input/seat.c`; the default
auto-detection branch is bypassed. There is no auto-detection message in
this run. Neither this mapping nor the identity matrix proves finger axes.

The first image omitted uinput because `INPUT_MISC` was disabled, despite
the source fragment requesting `INPUT_UINPUT`. `shell-uinput-missing.txt`
records the absent node and failed module lookup. The corrected kernel
must be checked after build and on the board, not inferred from the fragment.

IPC pointer commands were attempted with a seat that reports keyboard and
touch capabilities, but no pointer capability. They did not establish a
working menu interaction. The later keyboard probe was a direct process
signal, not a finger tap. At the end of that probe, real touch, keyboard
command entry, standalone boot, and the complete menu workflow were unverified.

## Subsequent real keyboard use

The user then reported: "i was able to use the keyboard".
`keyboard-user-touch.jpg` captures `ls` and its directory listing on the
panel, followed by an attempted `neofetch` (not yet installed). No injected
input entered these commands. A later native screenshot,
`keyboard-user-touch-screenshot.png`, captures the user's running `top`.
This proves a command was entered through the real keyboard and ran on the
panel. It does not replace a deliberate axis test or the remaining menu tests.

## Neofetch and Nix store initialization

The user requested Neofetch via Nix. The pinned Nixpkgs removed it, so
`nix/neofetch.nix` packages original version 7.1.0 from a hash-pinned source.
The build produced `/nix/store/8kby6bnnkd5360izrz9lal3vk0x9yvny-neofetch-7.1.0`.
All dependencies already existed in the image; only this path was transferred.

The first import exposed a missing first-boot Nix database initialization:
the image's store files existed but were unregistered. Loading the image's
`/nix-path-registration`, setting the system profile, and removing the marker
fixed it. `neofetch-nix.txt` records the failure and successful recovery/run.
The committed `register-nix-paths` unit still needs verification on a fresh image.

`neofetch-panel.jpg` and `shell-features/neofetch/screen.png` show the program
running as the shell user in a separate Foot terminal, launched through
`nix shell` and Sway IPC. This launch is automated, not real-touch evidence.

## Corrected image: unattended shell and registered Nix store

The source-built corrected image is
`/nix/store/s50h4h5awhx9479nhflayif890z2r6c0-k230-sd-image.img`.
`shell-usb-flash-corrected.txt` records all 2308689920 written bytes
compared equal through direct I/O (184.5 seconds), then a successful boot.
The running toplevel is
`/nix/store/7py9rixdgi2z79p6njcv3rik7azsvfa9-nixos-system-nixos-26.11.20260919.20b1ddd`.

`shell-clean-start.txt` verifies shell.service running with no drop-ins,
WorkingDirectory=/home/shell, all graphical clients started, and /dev/uinput
present. The Foot process itself changes its own cwd to /; the interactive
shell is in /home/shell, independently confirmed by the recorded `pwd` command.
The register-nix-paths service exited successfully, removed its marker, and
`nix-store -q --requisites /run/current-system` returned 570 registered paths.
No manual database load or graphical-session override was used after this flash.

`shell-features/startup/` records the panel passing from boot console to Sway.
USB cables remained attached: battery-only startup is still unverified.
The shell user's saved home archive was restored after boot; its checksum is
recorded in `shell-virtual-touch.txt`.

## Recorded injected-input workflow

`shell-virtual-touch.txt` records a separately named uinput device cloned from
the Goodix descriptor. `tools/inject-tap.sh` sends it panel-coordinate taps.
The feature media under `shell-features/` demonstrate entering `pwd`, showing
and dismissing the keyboard, launching Monitor, paging through Windows,
closing Terminal with `exit` and recovering it with Home, and cancelling
power-off and reboot confirmations. These are injected-input demonstrations,
not proof of finger accuracy or an entire real-touch workflow.

The original Monitor's wide htop profile hid process names. The
`monitor-portrait` recording validates the committed narrow HTOPRC profile
and Monitor title at the unchanged 15-point font. That profile was launched
through IPC for this recording; the flashed image still has the old launcher
configuration. A later image must verify its integrated menu launch.

`neofetch-clean` shows offline `nix shell` successfully running original
Neofetch 7.1.0 with the automatically registered store. The first automated
launch used non-login Bash and lacked nix in its PATH; that failed recording
is retained as `neofetch-launch-failed`. Using a login shell supplies the
normal interactive environment. The successful recording is the evidence.

The separate `shell-features/reboot/` recording confirms the Reboot action
through injected touches on System → Reboot → Reboot now. The previous
boot journal records System Reboot completing; the boot ID changes from
`af476995-3edd-4c30-bf98-996223657bf2` to
`98227a7f-034d-4d32-b733-6230d2b79e78`, and shell.service is active again.
Actual power-off was not executed; its confirmation and cancellation were.

Native clips are finite Grim samples with actual `/proc/uptime` invocation
bounds, encoded on the host with FFmpeg at a 10 ms timestamp timebase.
They are readable workflow evidence, not compositor frame-rate measurements.
The original PNG sequences were retrieved read-only through U-Boot UMS;
`shell-media-usb-pull.txt` verifies 20756480 bytes against the board's SHA-256.
The source sequences are preserved in `shell-features/native-source.tar.xz`.

After recording, the portrait HTOPRC was also installed as the shell user's
normal htop profile so subsequent launches on this running image use it.
`shell-monitor-live-profile.txt` records the installation and checksum.
This local profile preserves usability until the source-configured image is
deployed; it is not evidence of that later image's configuration.
