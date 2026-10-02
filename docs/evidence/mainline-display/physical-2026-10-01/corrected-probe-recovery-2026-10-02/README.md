# Recovery after the corrected initrd diagnostic

The operator reported “i power cycled” after the bounded 2026-10-02 mainline
`rdinit=/bin/sh` trial reached Linux but returned no complete fresh-token
probe result or observed reboot. The coordinator then reserved the board and
serial port for an independent normal-system recovery check. Raw serial
captures remain protected outside Git; no raw credentials or addresses are
published.

At 2026-10-02T06:44:06.065931+00:00, the unchanged fail-closed checker from
source revision `b209129b1cf681669edfe3e1e05be317842bf6f4` passed on the physical board.
[postflight.json](postflight.json) records the exact `p1a1hz…` normal system
and persistent profile, selected `03zyl0…/Image`, Linux 6.6.36, one matching
`init=` selector, three active shell services, all eight protected boot-file
hashes and a new boot ID `e7cf8096-44a0-4bdf-815d-2f1aec4126fb`.
The previous independently observed normal ID was
`f3940c26-ce09-41f5-b53f-fe525a04db06`; the checker required a different ID.
The expected system/profile/kernel and hashes came from the committed
[ordinary-boot baseline](../../../boot-verification/coherent-ordinary-boot/postboot.json),
with that previous normal ID supplied from the
[first recovery](../power-swap-recovery-2026-10-02/postflight.json).

The helper and expected data were streamed only into `/run` over an exclusive
115200-baud `/dev/ttyACM0` session holding `/tmp/k230-board.lock`. The exact
helper SHA256 is `86bcf6f2c175d44d27f68015a9cc5a1ad7731ad50b6bbf3347859a4840cc7df7`. Command:

```sh
/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3 -I /run/k230-mainline-normal-state.py postflight FRESH_32_HEX_TOKEN
```

Only a complete standalone fresh-token identity marker was accepted. No
normal boot-file, persistent profile or stage-1 mutation was performed by
this recovery check. The selected normal boot configuration survives the
power cycle; this is not an installed mainline system.

The coordinator requested compositor `output * dpms on` and `card_shell home`,
then used the exact installed Rust shell executable `3hy6h165…` with
`--surface hide` to hide transient surfaces. [output-state.json](output-state.json)
records DSI-1 active/powered, 568×1232 at 52.190 Hz, transform normal.
[home.png](home.png) is a reviewed full native `grim` capture from the running
Wayland session. [home-panel.jpg](home-panel.jpg) is a reviewed camera
observation of the illuminated physical panel; the camera frame covers only
part of the panel, while the native image shows the full frame. Camera command:

```sh
ffmpeg -nostdin -hide_banner -loglevel error -f v4l2 -input_format mjpeg -video_size 1280x720 -i /dev/video0 -vf 'crop=600:530:680:190,transpose=2,transpose=2' -frames:v 1 -q:v 2 -y "$HOME/tmp/k230-reset-recovery/second-home-panel.jpg"
```

Home was requested through IPC. These are physical recovery, serial identity,
native capture and camera evidence, not a new real-finger test. The prior
normal-boot navigation acceptance remains separately recorded in
[operator-navigation.json](../../../boot-verification/coherent-ordinary-boot/operator-navigation.json).
This recovery does not identify why the candidate probe stopped, establish
partition/IRQ state, or satisfy mainline root-login/touch task 5b.5.
