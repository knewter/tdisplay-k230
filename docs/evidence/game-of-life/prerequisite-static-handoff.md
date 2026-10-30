# Task 1.1: the static splash-to-Linux prerequisite

Assessment written 2026-10-30 from committed evidence only. No board action,
no camera, no new capture. Every statement below cites the file that holds it.

## The defect this change waits on

`docs/evidence/boot-splash-handoff.md` (2026-09-22, vendor-kernel daily
image, a hand-started Sway as the first DRM client): the stage-1 logo survived
to the Linux prompt, but "the first Sway modeset still produces incorrect
physical geometry/colors" (System wrapped to the left, bar/title colours
changed). A controlled repeat showed it was intermittent, and the owner route
of that day was recorded as "not a fix".

## The separate repair

The repair lives in archived change
`openspec/changes/archive/2026-10-20-the-mainline-kernel-keeps-the-boot-splash`
(tasks all ticked) and its evidence under `docs/evidence/mainline-boot-splash/`:

| Item | What it changed or showed | Evidence class |
| --- | --- | --- |
| 1.1, 1.2 | `reserved-memory` for the splash scanout on the mainline tree; the mainline panel/DRM driver already leaves a flagged panel alone | host build |
| 2.1-2.4 | warm-reboot boots on the mainline image: logo on the glass at the U-Boot prompt and the idle-kernel prompt; `k230-drm-splash` owner takes over with the logo unchanged; compositor first frame is a single 33 ms step after the last logo frame, nothing in between | camera film (2026-10-12), `board/README.md` |
| 3.1 | default image is the splash image (`panelConsole = false`) | `nix eval` |
| 4.1-4.3 | stage-1 DMA-request correction `0x40` to `0x4f` removed the brief garbled-logo frames; two clean filmed warm boots; every first-120 s frame qualified to at most +-75.244 ms against kernel time | camera film (2026-10-20), `dma-request-trial-2026-10-20/final/README.md` |

## Does it satisfy 1.1?

Partly, and the gap is specific.

Shown by the committed films: on the mainline default image the first
Linux frame is the logo, no wrapped, doubled or garbled logo frame was filmed
between the splash appearing and the compositor's first frame (final film:
8993 frames, no gaps), and the stage-1 image is no longer disturbed by the
installed kernel. The owner-based route the 2026-09-22 notes called
unproven is the one now in use, and the wrapped-logo-after-first-modeset case
of the 2026-09-22 repeat (`splash-phases/repeat-owner.jpg`) is not seen in any
2026-10-12 or 2026-10-20 film.

Not shown, and not inferable:

1. **The first compositor frame is near-black on the camera.** The films
   classify it by the shell's near-black navy background
   (`board/README.md` 2.4), and a frame of the final film around the
   handoff (frame 2989, 82.9 s) is dark. No committed camera frame compares
   the *geometry and colours of the shell controls after the first Sway
   modeset on the mainline image* with a native `grim` capture, the
   comparison that exposed the original defect (System wrapped left, colour
   shift).
2. The 2026-10-29 glass checklist (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`)
   is an operator report of shell behaviour, not a before/after of the boot
   handoff.
3. Every handoff film is a warm reboot with USB attached. Cold power-on and
   battery-only boots are explicitly out of the archived change's claims.
4. The 2026-09-22 defect was intermittent. Two clean filmed boots on the
   repaired image bound, but do not eliminate, a recurrence rate.

## Verdict recorded here

Task 1.1 stays **open**. What is missing is one physical before/after
observation of the shell's control order and colours after the first Sway
modeset of a normal splash boot on the current default image: a camera frame
(or the operator's own report on glass) set beside a native `grim` frame,
repeated on enough boots to say something about an intermittent fault. The
webcam is not to be used in this session, so the operator or coordinator
must decide either to supply that observation or to accept the films above as
sufficient and say so in writing.

Consequences already honoured by this change: the Linux continuation is off
unless `k230.bootLife.enable` is set, the stage-1 variant is a separate,
build-only attribute (`.#uboot-k230-boot-life`) that no image or install path
references, and no continuity claim is made anywhere.
