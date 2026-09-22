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
signal, not a finger tap. Real touch, keyboard command entry, standalone
boot, and the complete menu workflow remain unverified here.
