# U-Boot motion measurement attempt

The 30-second U-Boot target recording could not be registered: the unchanged
`tools/panel-measure.py` found only markers 0 and 1, below its minimum of
three. [Measurement output](measurement.txt) is a failed measurement, not a
zero-motion result. Splash task 3.7 remains open.

## Provenance and procedure

The board runs the corrected initial-scene diagnostic image from source
`12c1b0e`, integrated as opt-in code in master `61dcc90`. Its system is
`/nix/store/24h4sb1msncgbasnwl3ckdlxqf9v2g6r-nixos-system-nixos-26.11.20260919.20b1ddd`.
No image flash or readback was performed for this trial.

The deterministic default grayscale array from `tools/panel-target.py`
(seed 20260921) was encoded as B,G,R,X, with X=255, for the existing U-Boot
568x1232 raw-logo path. The RGB565 bytes emitted by that tool are unsuitable
for this loader. The XRGB target is 2,799,104 bytes, SHA-256
`e2bb58206db1083d8078b5ea8cd83d86569eca9aca950b8d60bac9432e3ebd60`.
[Transfer log](install-target.txt) records the board-side digest check before
installation. The [capture script](capture-uboot.py.txt) uses the repository's
serial Session helper to reboot and stop at U-Boot, without saving an altered
environment.

[Serial transcript](console.txt) records the direct XRGB logo load and
`UBOOT_MOTION_TARGET_READY` before the camera starts. The
[video](20260922T224020Z-uboot-motion-target.mp4) and
[physical frame at five seconds](uboot-target-physical.png) show the target
while U-Boot is held. `Starting kernel` occurs after recording ends.
Camera focus was 90, manual exposure 200; [camera settings](camera-controls.txt)
record the full controls. This is a warm reset with USB attached.

Analysis command, exit 1:

```sh
python3 tools/panel-measure.py --video docs/evidence/splash-uboot-motion/20260922T224020Z-uboot-motion-target.mp4 --label 'U-Boot 61dcc90 candidate, fixed ArUco registration'
```

## Focus investigation

The same generated target PNG was displayed through a temporary Linux
`swaybg` process while the terminal and bar were hidden. This is an optics
check, not another U-Boot measurement. The fixed-focus stills detected:

| Focus | Marker IDs |
| --- | --- |
| 0 | none |
| 30 | 2 |
| 50 | 1, 2 |
| 55 | 1 |
| 60 | 0, 1 |
| 65 | 0, 1 |
| 70 | 0, 1 |
| 90 | 0, 1 |

See [coarse detection](focus-detection.json),
[fine detection](focus-fine-detection.json), and `focus-*.png`.
No tested fixed focus resolved three markers. The steep view and reflection
over the far-right marker limit registration. Combining positions from
changing focus settings would introduce a different calibration and is not
used to manufacture a passing result. The next valid measurement needs a
less oblique, less reflective physical camera/board arrangement.

Even a registered result would be in **panel rows**. The old
`dsi-hsfreqrange-hardcoded.md` A/B table is in **raw camera pixels** under a
fixed earlier geometry. They cannot be numerically compared. A new Linux
0x87 reference with the same target and rig is needed for a like-for-like
comparison; no PHY sweep is justified by this failed optical registration.

The [keyboard at focus 30](keyboard-focus-30.png) shows lower-panel key rows
and labels more clearly than the original focus 90 recordings. Focus 50
retains more terminal detail but less sharp keyboard text. This supports a
follow-up keyboard visibility recording, not finger-input accuracy or a
calibrated full-panel geometry claim.

## Restored state

The serial transcript records restoration of the immutable logo with SHA-256
`6c7a36086297597b359657ab53925ee0725e5201461484d543cbd950f5baa3af` and active
shell, seatd and firewall. The focus scripts stop only their own temporary
`swaybg`, restore the bar, and bring back the terminal. The follow-up
`keyboard-visible-layout.txt` in `../splash-initial-scene-ready/` restores the
terminal to tiling after scratchpad use. Camera focus/exposure return to
90/250. Keyboard visibility signals and cleanup are recorded in
`keyboard-optics-show.txt` and `keyboard-optics-restore.txt`.
No home backup, application default, or persistent boot configuration changed.
