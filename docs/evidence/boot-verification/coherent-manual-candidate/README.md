# Matching coherent shell: temporary physical boot

2026-10-01. Evidence classes: **reserved physical-board serial boot**, native
Wayland capture, and camera observation. **Real-finger navigation and ordinary
autoboot remain unverified.** This is not a persistent installation.

The selected `p1a1hz…` system and its `03zyl0…` vendor kernel boot successfully
through the same CR-only manual-loading mechanism used in the earlier trial.
`serial-result.json` records each exact loaded file's bytes, SHA256 and in-memory
CRC32, then the actual command line, selected system/kernel links, unchanged
persistent profile, boot ID and all three active shell services. The load CRC
is the proof of which Image was executed; a `/run/booted-system/kernel` link
alone cannot distinguish manually loaded kernels.

```
python3 tools/coherent-shell-board-stage.py prepare /var/lib/k230/coherent-boot/p1a1hz9n8s4g8qyr55ffl3dzbnjgqwr8-20261001
python3 tools/coherent-shell-board-boot.py \
  --candidate /nix/store/pnci1pzsca9f45mfyakcrzyk7yx2ad42-k230-coherent-shell-boot-files \
  --state ~/tmp/k230-coherent-boot-board/state.json \
  --output ~/tmp/k230-coherent-boot-board/candidate
python3 tests/test_coherent_shell_board_boot.py
python3 tests/test_rvv_board_boot.py
```

The first command runs **on the board**, after the four inspected boot files,
closure path list, manifest and stage tool have been delivered over the private
runtime transport. The other commands run on the host. `staged-state.json` is
the captured board preparation report. All 1,158 selected-system closure paths
are registered on the board, checked against its recursive closure, and
protected by a GC root. All eight normal boot/selector files were copied to
`<stage>/backup` on the existing root filesystem before the trial. Original
profile, stage 1, root layout and boot files were preserved. The bootstrap
`/nix-path-registration` file remained absent.

The controller inspected `bootcmd`, `blinux` and `preboot` without `saveenv`;
the response hash is recorded and its raw contents stay in the private console
log. Five loads from root partition `mmc 1:2` were checked before volatile env
import and `bootm 0x8000000 0x9000000 0x8400000`. The unchanged OpenSBI wrapper
was loaded from the protected backup. `controller-used.py` is the exact source
snapshot whose SHA256 matches the report; it is provenance, not a standalone
entrypoint. The landed tool additionally rejects a changed profile, mismatching
kernel/init identity or inactive shell services, all of which match in this
actual report. Five staged-plan tests and five shared UART-protocol tests pass.

After boot, explicitly hiding the transient Rust surface and issuing
`swaymsg 'card_shell home'` produced visible Home. A second on-board `stage.py
check` passed before `grim` capture: the normal files/profile and registered
closure were still intact. The earlier ambiguous dark-panel result was not
reproduced here. This does **not** identify its root cause or establish a kernel
driver defect.

![Native Home after matching-kernel boot](home.png)

![Photographed visible Home on the panel](home-panel.jpg)

The camera photograph shows the visible part of the panel; the device extends
outside the camera frame. Its exact capture command was:

```
ffmpeg -nostdin -hide_banner -loglevel error -f v4l2 -input_format mjpeg \
  -video_size 1280x720 -i /dev/video0 \
  -vf 'crop=750:530:530:185,transpose=2,transpose=2' \
  -frames:v 1 -q:v 2 -y ~/tmp/k230-coherent-boot-board/candidate-home-panel.jpg
```

Both images were reviewed before committing. They show the remembered Home
layout and wallpaper, but do not certify every theme/background option.

**Next:** real-finger Home/All-apps/Overview/Terminal checks are pending with
the operator. Repeat the same controller with `--baseline` to compare the
protected working system, return to the candidate, and qualify persistent
installation followed by an untouched ordinary reboot. Tasks 2.1–3.3 stay open.
While normal files remain unchanged, `reboot` from Linux returns to the original
normal boot; `--baseline` provides the same protected manual fallback. A failed
post-jump kernel that cannot reach serial requires a power reset to that intact
normal path. The controller resets automatically if a load fails in U-Boot.
