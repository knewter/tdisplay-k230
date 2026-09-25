# Bottom-~50px flicker during animation: hypothesis list for board experiments

User report (real glass, 568x1232 RM69A10 @ 52.19 Hz): the bottom ~50 px band
of the panel flickers while the screen *animates* -- during bottom-edge
app-switch dragging and while the overview/app-switcher is shown. The user is
explicit the band is **not** shaped like app icons; it reads as a banding/
tearing artifact, not mis-rendered content.

While investigating this, a genuine but *separate* compositor-scene bug
turned up and was fixed on this same branch: `home_layer_sync` (`nix/
card-shell/adapter.c`) only ran from `card_shell`'s own state-machine
transitions, so an unrelated Sway focus change while the overview stayed
open could re-enable Home's layer without `shell.active` ever changing --
see `openspec/changes/the-overview-hides-the-home-screen/tasks.md` section
6 and `tests/test_card_shell_home_layer_self_heal.py`. That is a real,
independent defect (content-shaped, would show Home's own grid/dock), not
the hardware-level banding this document investigates, and it does not
change any hypothesis below.

## What the compositor side already rules out

`grim` bursts of the bottom 80 px strip taken while the overview is held open
via IPC (`swaymsg card_shell enter`, no further input) are pixel-identical
frame to frame -- see the coordinator's prior capture. That is a **static**
scene: nothing re-renders once settled, so it cannot exercise a race that
only exists while the compositor is actually producing a new frame every
~19.2 ms. It does not clear the render or scanout path during animation.

## Relevant grounding already in this repo

- `docs/evidence/drm-info.txt`: driver `canaan-drm` ("Canaan K230 DRM driver")
  1.0.0 20230501, dumb buffers only (`/dev/dri/renderD*` absent), imported via
  PRIME as usual for wlroots' DRM backend. `DRM_CAP_CRTC_IN_VBLANK_EVENT = 1`,
  `DRM_CAP_ATOMIC_ASYNC_PAGE_FLIP` **not supported**, `DRM_CAP_ASYNC_PAGE_FLIP
  = 0`. Primary plane format list omits `XRGB8888` (wlroots' default); the
  system runs Pixman software rendering at `render_bit_depth 6` -> RGB565
  (`nix/shell.nix`, `output DSI-1 ... render_bit_depth 6`).
- `docs/evidence/flicker-after-headroom-revert.md`: a **different**,
  already-investigated flicker symptom (whole-frame vertical roll, steady
  state, no animation) was traced to the RM69A10 being a DSI **command-mode**
  panel with its own GRAM: the init sequence issues `35 00` (`SET_TEAR_ON`)
  but nothing in this driver stack consumes the Tearing-Effect (TE) signal.
  That investigation's conclusion was explicitly "not tearing" **for that
  symptom** (a uniform modulo-height roll), but it establishes as fact that
  **this panel's host-side write and the panel's own internal scan are not
  synchronized by TE today**. A different symptom (a torn/unstable band
  rather than a clean roll) from the same unsynchronized-write root cause is
  plausible under different timing conditions (e.g. CPU render duration
  varying frame to frame during an animation, rather than the steady low-load
  case that investigation measured).
- No kernel or DRM patch in this repo wires TE (`grep -rl "tear\|te-gpio"
  nix/kernel* nix/patches/*.patch` matches only the Sway-side frame-timing
  and splash patches, none of which touch TE).
- `nix/patches/wlroots-vglite-dumb-stride.patch` shows this exact vendor
  driver has already had one dumb-buffer stride/alignment surprise, but it is
  gated on `WLR_RENDERER=vglite` and does not apply to the default `pixman`
  renderer path this system actually ships.

## Prioritised hypotheses and board-side experiments

Ordered by (a) how directly each is supported by the grounding above, and
(b) how cheap the experiment is. **None of steps 1-2 need a rebuild.**

### 1. Confirm with the existing telemetry pipeline first (no rebuild, ~5 min)

This compositor already has a mature, reviewed benchmark/telemetry path built
exactly for "how long does rendering take, and were frames presented on the
expected cadence" (`nix/card-shell/telemetry.c`, `tools/card-shell-benchmark.py`,
documented in `nix/card-shell/README.md`'s "Benchmark IPC" section). Run it
against the *real* reported gesture before touching anything else:

```
swaymsg card_shell benchmark physical
# perform the exact reported gesture: a bottom-edge app switch, and
# separately, opening the app switcher by a real swipe; wait 3s before/after
swaymsg card_shell benchmark-stop
journalctl -u <sway-service> | grep K230_CARD_BENCH > telemetry.log
python3 tools/card-shell-benchmark.py --input telemetry.log --renderer pixman
```

Read `tracking_present_interval_ms` (spacing between successive *presented*
frames while dragging -- this is DRM/vblank feedback, not a guess) and
`frame_update_cpu_ms` (Pixman scene-build + commit-submit CPU time per
frame) in the JSON report:

- **If `tracking_present_interval_ms` stays close to 19.2 ms (budget p95
  33.334 ms / max 100 ms passes cleanly)** and `frame_update_cpu_ms` is well
  under 16.7 ms: the compositor is submitting frames on a clean, on-time
  cadence. That **rules out** "the CPU render is slow and racing scanout"
  and points squarely at the panel/driver side (hypotheses 3-4 below) --
  exactly what the pixel-identical IPC capture already suggested, now
  confirmed for the *animating* case too.
- **If `frame_update_cpu_ms` is at or above ~16-19 ms** (i.e. Pixman
  sometimes takes longer than one refresh period to build+submit a frame):
  that supports hypothesis 2 (host-side render occasionally overruns the
  frame budget). Note the caveat in the tool's own `limits`: presentation
  timestamps are DRM backend feedback, not proof of what the panel actually
  displayed -- this stage only tells you whether the compositor missed its
  own deadline, not whether the glass tore.

This single run should reorder the rest of this list with real numbers
before any hardware toggle is flipped.

### 2. Host render occasionally overruns the ~19.2 ms budget (no rebuild)

The panel refreshes at 52.19 Hz (~19.2 ms/frame). This is a CPU/Pixman
software-rendering compositor, and this project already has a whole set of
in-flight branches (`perf/card-scaled-cache`, `measure/card-render-cost`,
`perf/card-mirror-order`, `perf/theme-background-decode`, ...) tracking that
full-screen card-shell animation frames are expensive to render. If a frame's
build+commit occasionally exceeds one refresh period, the next commit lands
after scanout has already started reading the previous buffer for that
period.

Experimental toggle: `swaymsg output DSI-1 max_render_time 12` (render each
frame starting ~12 ms before wlroots' predicted deadline, rather than sway's
default "start as late as possible" latency-minimising schedule), then repeat
the gesture and watch the panel. If the band goes away or gets markedly
rarer, this supports "occasional CPU overrun, no headroom" as (part of) the
cause; revert with `swaymsg output DSI-1 max_render_time off`.
Cross-check against hypothesis 1's `frame_update_cpu_ms` numbers, since
`max_render_time` only changes *when* rendering starts, not whether a
genuinely slow frame finishes in time.

### 3. K230 DRM driver's flip-done/vblank signalling is not trustworthy (no rebuild for the toggle; needs a session restart, not a package rebuild)

`docs/evidence/drm-info.txt` shows atomic KMS and `DRM_CAP_CRTC_IN_VBLANK_EVENT`
are both advertised, but this is an early vendor driver (`canaan-drm` "1.0.0
20230501") with no render node and dumb-buffer-only allocation -- exactly the
profile of a driver whose atomic commit / vblank-event path has not been
exercised much. If the driver signals "flip complete" to wlroots before the
hardware has actually finished scanning out the previous buffer (or before
the *next* buffer is safely presentable), wlroots could legitimately believe
it is safe to recycle/write a buffer that is still on-glass, producing
exactly a band of stale/torn pixels that only shows up when frames are
produced back-to-back (i.e. during animation, never in the static IPC
capture).

Experimental toggle: `WLR_DRM_NO_ATOMIC=1` in the compositor's environment,
then restart the Sway session (no rebuild) and repeat the gesture. This
forces wlroots onto the legacy `drmModePageFlip` KMS path, whose page-flip
completion semantics are a different code path in both wlroots and the
vendor driver than the atomic commit path. If the band changes character or
disappears, that isolates the bug to the atomic-commit/vblank-event path
specifically (a very plausible immature-driver bug class). If it is
identical, legacy and atomic share whatever is wrong (more likely a deeper
issue such as hypothesis 4).

### 4. The command-mode panel's own scan is not synchronized to host writes at all (TE never wired) -- same root cause already found for the whole-frame-roll symptom

Per `docs/evidence/flicker-after-headroom-revert.md`, `SET_TEAR_ON` is sent
but nothing consumes the panel's TE line, so the panel's internal GRAM scan
and the host's writes into that GRAM already run on independent, unsynced
clocks. At idle/steady state that showed up as a slow, uniform roll. Under
per-frame CPU render-time jitter (animation), the same lack of
synchronization could plausibly show up instead as a locally unstable band
near wherever the write "catches up to or is caught by" the panel's own scan
position for that instant -- which would look like flicker rather than a
clean roll, and would be worse exactly when render timing is least uniform
(i.e. during animation), matching the report.

This is a real hardware/driver gap, not a toggle: fixing it needs the panel
driver to actually wait for (or schedule around) the TE GPIO/interrupt,
which is display/panel work, not something flippable from the compositor
today. It can be **supported or weakened** by combining hypothesis 1's
present-interval numbers (clean cadence at the DRM-feedback level) with
direct visual correlation: if the band's position/character does not track
`frame_update_cpu_ms` variance at all (i.e. it happens identically even
during the *cheapest*, fastest-rendering frames of a gesture), that argues
against hypothesis 2/3 and toward this one -- a free-running panel-side
scan that doesn't care how fast the host writes.

### 5. Lower priority / weaker support

- **`allow_tearing`**: Sway's own tearing path (`output_can_tear` in
  `sway/desktop/output.c`) only applies to a `wlr` *fullscreen* container
  with `output->allow_tearing` set **and** the view itself opted in via the
  tearing-control protocol. Neither is set anywhere in this repo
  (`nix/shell.nix`'s `swayConfig` has no `allow_tearing` line), and
  card-shell's own "ordinary maximized" cards are floating, not `wlr`
  fullscreen. This mechanism is very unlikely to be engaged at all today;
  worth a one-line confirmation (`swaymsg output DSI-1 allow_tearing no`,
  which should already be a no-op) rather than a real suspect.
- **`WLR_SCENE_DISABLE_DIRECT_SCANOUT=1`**: worth trying if 1-4 are
  inconclusive. Direct scanout (handing a single eligible client buffer
  straight to the KMS primary plane, bypassing Pixman composition) is a
  different code path from full composition, and eligibility flips on/off
  frame to frame exactly at the boundaries of an animation (a maximized
  card is eligible when static, not while multiple scene layers are
  animating over it), which is a classic source of visible hitches if one
  of the two paths has a driver-side bug the other doesn't. No rebuild;
  session restart only.
- **`WLR_DRM_NO_MODIFIERS=1`**: worth trying only if 1-4 point at a
  structured/banded corruption consistent with a stride or modifier
  mismatch specifically (the `wlroots-vglite-dumb-stride.patch` history
  shows this vendor driver has had at least one such surprise, though on a
  different, currently-inactive renderer path). No rebuild; session restart
  only.

## What each experiment would mean, summarised

| Toggle | If band disappears/improves | If band unchanged |
| --- | --- | --- |
| Read `tracking_present_interval_ms`/`frame_update_cpu_ms` from a `physical` benchmark run | n/a (diagnostic, not a fix) | n/a |
| `max_render_time 12` (then `off`) | Host render sometimes has no headroom before its deadline (hyp. 2) | CPU timing isn't the (whole) story |
| `WLR_DRM_NO_ATOMIC=1` | Bug is specific to the atomic commit/vblank-event path (hyp. 3) | Legacy and atomic share the bug, or it's not driver-flip-path-specific |
| `WLR_SCENE_DISABLE_DIRECT_SCANOUT=1` | Direct-scanout/composited path transition was the trigger | Not a direct-scanout artifact |
| `WLR_DRM_NO_MODIFIERS=1` | Modifier/stride mismatch on this driver | Not a modifier issue |
| (no toggle) optical correlation with `frame_update_cpu_ms` per-frame | Band tracks render-time variance -> hyp. 2/3 | Band is present even on the cheapest frames -> hyp. 4 (TE/free-running panel scan), display/panel work, not a compositor toggle |

## Explicitly not done here

No DRM, KMS, panel, or wlroots render-path code was changed to "fix" this.
Nothing here has been run on the board; every toggle above is proposed, not
verified. This file records hypotheses and the commands to test them so the
coordinator's webcam-equipped board session can gather evidence efficiently,
per `.skills/k230-spec-change/SKILL.md`'s grounding order: an observation on
the board outranks everything in this file.
