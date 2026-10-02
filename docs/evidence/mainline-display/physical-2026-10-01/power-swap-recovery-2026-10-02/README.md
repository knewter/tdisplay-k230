# Normal-system recovery after the initrd shell diagnostic

The operator reported “power swapped it” on 2026-10-02. The subsequent
exclusive serial check passed at 2026-10-02T06:12:40.448015+00:00. The exact
normal system and persistent profile are `p1a1hz9n8s4g8qyr55ffl3dzbnjgqwr8`;
the booted kernel is the selected vendor Linux 6.6.36. Its single `init=`
selector matches that system. `shell`, `shell-ui` and `theme-helper` are
active. All eight protected boot/selector SHA256 hashes match the committed
[ordinary-boot baseline](../../../boot-verification/coherent-ordinary-boot/postboot.json).
The boot ID is new: `f3940c26-ce09-41f5-b53f-fe525a04db06`.

## Command and artifacts

The coordinator held `/tmp/k230-board.lock` and opened `/dev/ttyACM0`
exclusively at 115200 baud. From source revision
`53513c7a814ad211c2a32c4a7bc8da95a9bee0ae`, the unchanged
`tools/mainline-drm-normal-state.py` and expected identities/hashes from the
baseline were streamed only into `/run`; the expected `trial_from_boot_id`
was `44014e29-0795-42a5-8a5b-d4ab326bf72c`. The board invocation was:

```sh
/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3   -I /run/k230-mainline-normal-state.py postflight FRESH_32_HEX_TOKEN
```

The checker SHA256 is `86bcf6f2c175d44d27f68015a9cc5a1ad7731ad50b6bbf3347859a4840cc7df7`.
A complete standalone fresh-token marker was required; command echo and
incomplete output were not accepted. [postflight.json](postflight.json)
contains only the allowlisted observation, with no raw console output or
network secrets. Raw captures remain protected outside the repository.

The initial camera observation was dark. Read-only Sway output inspection
reported DSI-1, 568×1232 at 52.190 Hz and power on; darkness alone did not
establish a failed boot. The coordinator then requested `output * dpms on`
and `card_shell home`, and hid transient shell surfaces using the exact
installed Rust client `3hy6h165ii649z6vjzjd36jwg16d37rc` with `--surface hide`.
[output-state.json](output-state.json) records the post-command output state.
No boot-file, profile selection, or application deployment was performed.

[home.png](home.png) is a reviewed native `grim` capture from the board's
Wayland session after these injected commands. [home-panel.jpg](home-panel.jpg)
is a reviewed host-camera observation of the illuminated physical panel:

```sh
ffmpeg -nostdin -hide_banner -loglevel error -f v4l2 -input_format mjpeg   -video_size 1280x720 -i /dev/video0   -vf 'crop=750:560:530:160,transpose=2,transpose=2'   -frames:v 1 -q:v 2 -y "$HOME/tmp/k230-reset-recovery/home-panel.jpg"
```

## Limits and next gate

This proves restoration to the normal system after the temporary mainline
trial, including a new boot and unchanged protected selection. It does not
prove the corrected `rdinit` diagnostic ran, explain the preceding UART
silence, or establish mainline root login or touch behavior. Home was
requested through IPC; these captures are not real-finger acceptance and do
not prove Home was visible without that request. Task 5b.5 remains open.
The next mainline trial uses the corrected volatile PATH and absolute reboot
command only after a new board reservation; the normal system remains selected.
