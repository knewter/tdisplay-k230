# Mainline boot splash on the board, 2026-10-12

Hardware gates 2.1-2.4 of `the-mainline-kernel-keeps-the-boot-splash`, run
on the one board in place (no second card: the operator answered "In place
is fine"), with warm reboots standing in for power-on (the operator answered
"Warm reboot is enough"). Every film below is a **warm reboot**, not a cold
power-on. Camera: the bench webcam (`/dev/video0`, MJPEG 1280x720, 30 fps),
which now views the panel from its long edge at a grazing angle; the far
half of the panel is outside the frame.

System under test: `k230-mainline-drm-shell-splash`, toplevel
`/nix/store/kc3iyr4cnjlswa87kkpi81qgc1is6hli-nixos-system-nixos-26.11.20260919.20b1ddd`,
bundle `/nix/store/kjlnrxv8vdk92lh84w2bkd1v0mx456hy-k230-coherent-shell-boot-files`
(source `impl/mainline-splash-2026-10-12` `a03999c3`). Its Image and initrd are
byte-identical to the previously installed `298a2bf6` system; it differs in
the device tree (`framebuffer@10000000`, `0x400000`, `no-map`), in bootargs
(no `console=tty0`) and in carrying `logo.xrgb` (SHA-256 `6c7a3608…a3af`).
U-Boot is the card's existing source-built stage 1 with patches 0004/0005.

Raw serial logs and films stay off-repo (private); this directory holds
sanitized excerpts, single frames and the scripts that produced every figure.

## Sequence

| Step | Tool | Result |
| --- | --- | --- |
| Preflight, stage, one-shot candidate boot | `coherent-shell-board-*` pipeline | `preflight.json`, `host-inspection.json`; PASS |
| Candidate runtime | `runtime-check.py candidate` | `candidate-runtime.json`; PASS |
| U-Boot hold with ArUco target logo (film2) | `tools/splash-uboot-session.py hold` | 2.2 measurement |
| U-Boot hold + framebuffer poke (film3) | `… hold --poke` | liveness, `uboot-hold-poke-serial-excerpt.txt` |
| Idle-kernel boot (film6) | `… idle` | 2.1 photo, 2.3, `idle-kernel-serial-excerpt.txt` |
| Install as default, ordinary autoboot (film7) | `coherent-shell-board-boot.py --install` | `deployment-authorization.json`, `ordinary-runtime.json`; PASS; 2.4 |

The candidate-boot film (film1) from the one-shot boot is the second 2.4 film.

## 2.1 Splash on the glass before `Starting kernel`

`splash-at-uboot-before-kernel.jpg` is film6 at session t = 17.99 s. The
session transcript (`idle-kernel-serial-excerpt.txt`, same clock, film start
2.01 s before the session) shows U-Boot printing
`2799104 bytes read … RM69A10 direct XRGB8888 logo.xrgb full-screen OSD4`
before the autoboot prompt, the boot files loading from t = 13.3 s, `bootm`
sent at t = 26.26 s, and only then `Starting kernel ...`. The photograph is
taken while U-Boot is still loading, 8 s before `bootm`.

Deviation: the task names `./tools/capture-boot.py`; the capture here is
`tools/splash-uboot-session.py`, which also timestamps every console line on
the host clock that the film start is recorded against.

## 2.2 Motion of the U-Boot-lit image

U-Boot drives the panel with `{3, 97, 0x17, 0x87}` at 49.5 MHz (patch 0004,
the values `dsi-hsfreqrange-hardcoded.md` measured). The logo was temporarily
replaced by `tools/panel-target.py`'s target converted with
`target-to-xrgb.py` (SHA-256 `e2bb5820…bd60`), the board held at `K230#`, and
the panel filmed (`aruco-target-at-uboot-prompt.jpg`).

`tools/panel-measure.py` could not register: only markers 0 and 1 are in the
current camera frame (it needs three). Its `--record` mode also fixes the
exposure at 200, which made the first attempt too dark to find any marker.
So the measurement uses `camera-px-motion.py`: the same `norm1`/`shift`
routine on an unregistered camera-pixel strip across the barcode field, as
the 0x87 rows of `dsi-hsfreqrange-hardcoded.md` were measured (camera px,
fixed camera, no registration). A static object in the same clip is the
camera's noise floor.

| film2, t = 15..50 s at `K230#` (1050 frames) | U-Boot target, strip y330:360 x560:1010 | control: keyboard, y60:120 x330:640 | 0x87 run 2 (earlier doc) |
| --- | --- | --- | --- |
| motion std | **0.01 px** | 0.02 px | 0.02 px |
| span | **0.10 px** | 0.15 px | 0.09 px |
| frame-to-frame mean | **0.01 px** | 0.03 px | 0.00 px |
| frame-to-frame max | **0.06 px** | 0.14 px | 0.04 px |
| jumps > 2 px | 0 | 0 | 0 |
| brightness range | 100..100% | 99..102% | 100..100% |

The U-Boot image's motion is at the 0x87 run-2 level and below the static
keyboard's apparent motion, i.e. below what this camera can resolve.
Frozen-panel check (the failure the earlier document warns about): in film3
`mw.l 0x10000000 0xffffffff 0x1bbc0` at the U-Boot prompt (t = 38.28 s)
turns the top 200 rows white by t = 38.52 s (`fb-poke-before.jpg`,
`fb-poke-after.jpg`), and `md.l` reads the change back; the panel is
scanning the splash buffer live. The original logo was restored and its
hash checked before the next boot.

## 2.3 Idle kernel, nothing opening the display

`tools/splash-uboot-session.py idle` loaded the staged candidate's files from
`mmc 1:2` (each size and CRC32 checked), imported its bootargs, appended
`systemd.mask=shell.service systemd.mask=seatd.service
systemd.mask=k230-drm-splash.service` for that boot only, and booted.
A first idle run without the third mask showed `k230-drm-splash` (the
Linux-side static splash owner) opening DRM at 45.2 s, so it was repeated.
At the serial root prompt, and again after a 90 s hold
(`idle-kernel-serial-excerpt.txt`):

- `/proc/device-tree/chosen` lists `canaan,stage1-splash` (`FLAG_PRESENT`);
- `[    2.812261] canaan-drm display-subsystem: [drm:canaan_drm_bind] stage 1 splash: leaving fbdev unset`;
- `reserved mem: 0x0000000010000000..0x00000000103fffff (4096 KiB) nomap non-reusable framebuffer@10000000`;
- no `canaan_panel`, `canaan-panel` or VO/DSI preserve line at all -- no
  panel prepare without a DRM client;
- `ls /dev/fb0` fails; `shell`, `seatd`, `k230-drm-splash` inactive; no
  process holds a `/dev/dri` descriptor (`DRM_CLIENTS_LISTED` with no
  `DRM_CLIENT` line).

`splash-at-idle-kernel-prompt.jpg` is film6 at session t = 147.99 s, during
the hold at that prompt: the logo is still on the glass. Film6 classifies
the logo continuously from 11.43 s to 204.77 s (the reboot), with only
1-2-frame `other` blips at reflection sweeps.

## 2.4 Frame timings, splash to the compositor's first frame

`frame-classes.py` reduces the panel box of each frame to an edge map and
correlates it with a logo and a shell reference frame from the same film
(room reflections sweep the glass and make brightness useless; see
`film*-classes.txt`).

| Film (warm reboot) | logo first | logo last | compositor first frame | between |
| --- | --- | --- | --- | --- |
| film1, one-shot candidate boot | 16.37 s | 80.93 s | 80.97 s | none |
| film7, installed ordinary autoboot | 42.43 s | 121.93 s | 121.97 s | none |

Across the Linux takeover by `k230-drm-splash` (kernel t = 45.2 s,
mid-span) the image does not change: the first Linux frame is the logo.
Most non-logo classifications inside the spans are the intact logo under a
moving reflection or a camera refocus (film7 49.43, 63-64, 69, 105.6 s;
film1 21.23 s). **Some are not** -- see "Transient scanout glitches" below.
The switch to the
compositor is a single 33 ms frame step (`handoff-film1-strip.jpg`,
`handoff-film7-strip.jpg`). The compositor's first frame is the shell's
near-black navy background; the terminal prompt draws on it ~0.7 s later
(film7 122.70 s; film1 101.2 s, which an earlier brightness reading had
mistaken for the handoff). In film7 the whole picture, including the
keyboard and USB plug off the panel, dims 5-7% at 122.03-122.6 s: that is
the camera's auto-exposure, not the panel.

Limit: a camera cannot tell a black frame from the compositor's near-black
background, so "no dark frame" is shown as: no intermediate state between
the last logo frame and the compositor's first frame at 30 fps, plus the
kernel's own `preserving VO/DSI to first plane update` lines.

## Transient scanout glitches on the splash system (open)

Every splash-kernel boot filmed shows the stage-1 image glitching for 1-4
frames during early userspace, with the scene static (film7 75.0 s: keyboard
phase-correlation shift 0.00 px while the panel box shifts):

| Film | Film time | What the frame shows | Kernel time (approx.) |
| --- | --- | --- | --- |
| film1 | 43.30, 44.10 s | logo doubled/smeared | ~17 s (initrd activation, 16.5-19.3 s) |
| film6 | 56.70-56.73, 57.90-58.00 s | logo wrapped along the panel ("230K") | ~27-28 s |
| film7 | 75.00-75.03, 76.00-76.07 s | logo displaced and garbled | ~26.5-27.5 s |

Kernel times are film time minus an estimated kernel start (film1/film6
from the `bootm` stamp plus ~1.3 s; film7 from the compositor's first frame
at 121.97 s against sway reading its config at kernel 72.6 s), so they are
good to about +-2 s. The ~27 s windows fall inside `Load Kernel Modules`
and udev coldplug in the real root (25.9-29.9 s); no kernel message falls on
a glitch. The image always recovers on the next frames and is never
corrupted afterwards, which points at a scanout/sync disturbance rather
than at the reserved buffer being written. These are not dark frames, so
the 2.4 criterion as written is met, but they are visible: the operator
reported "the display flickers sometimes. real close to perfect". Cause not
established; task 4.1 of the change keeps it open.

## Ordinary kernel without the reservation (the flicker the operator saw)

After the U-Boot holds, the board autobooted the then-installed `298a2bf6`
system, whose device tree has no splash reservation, with `logo.xrgb` now on
`/boot`. In films 2 and 3 that kernel tears the stage-1 image on single
frames (film2 58.9, 84.3-88.9 s; film3 65.3, 90.7-95.5 s;
`unreserved-kernel-tear-film2-strip.jpg`) and leaves noise on the glass
(film6 260 s) until its compositor draws. Neither splash-kernel boot shows
any such frame. Installing the splash system as the default (film7, 5418
frames) removed it; the operator had reported "the display flickers
sometimes" during these trials.

## Not shown

Cold power-on (operator accepted warm reboot); a second card; ArUco-registered
panel-row figures (camera out of the bench geometry); any touch or finger
observation.
