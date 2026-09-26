# Backdrop blur / shader-effect feasibility

Source and host-benchmark checkpoint, 2026-09-25, branch
`fix/shade-backdrop-fade` (base `d88c8fe3`, after the eased-fade commit
`8bbd3b83`). No board or QEMU run performed for this note. It answers
whether the shade/overview backdrop this branch just fixed (see that
commit) could reasonably grow a blur, and whether shader-style effects are
viable on this hardware at all.

## 1. What the renderer actually is

There is no GLES/EGL/Vulkan stack on this board at all, and this is a
hardware/driver fact, not a missing-package one:
`docs/display-environment-options.md` (source/host checkpoint, 2026-09-20,
physically confirmed 2026-09-22) states it directly: the K230's VG-Lite
block "is not a Mesa/DRI driver and does not create a DRM render node, GBM
device, EGL, GL, or Vulkan API. Its vendor API is a single-context
`/dev/vg_lite` ioctl interface." The only other way to get a GL context is
Mesa's software `llvmpipe`/`softpipe` over `kms_swrast`, which the same
document rules out as strictly worse than direct Pixman: it pulls in a
riscv64 LLVM JIT (2.4 GiB unpacked) and "puts a JIT compiler and a full GL
implementation between a 1.6 GHz in-order core and 700,000 pixels." Sway on
this board runs its stock Pixman renderer (CPU, RGB565, 568x1232) today, and
that document's own physical measurement is the shell's frame budget: 254
board-measured whole-scene composites, **median 14.00 ms, p95 15.59 ms**,
against a measured ~19.16 ms/refresh (52.19 Hz) output
(`docs/evidence/shell-performance.txt`). So "cheap" here means "small
compared to a ~14-19 ms envelope on a single 1.6 GHz in-order C908 hart" --
this board is also confirmed single-hart today
(`docs/research/second-core-feasibility.md`: the pinned device tree
declares only `cpu@0`, and `docs/evidence/cpu-readiness.txt` shows `nproc`
sees one processor). There is no second core to offload work onto right
now; anything computed live competes with the same hart that has to keep
compositing and servicing touch.

## 2. VG-Lite's actual native operations

`docs/research/vglite-wlroots-source-audit.md` and
`docs/evidence/vglite-compositor-audit.md` are a from-source, host-tested
audit of the experimental (opt-in, non-default) wlroots VG-Lite renderer
fork. Its "Current eligibility" section is the ground truth for what the
GC8000UL block can be asked to do through this path:

- **Rect fill**: opaque solid colors only. Alpha rectangles replay with
  Pixman -- i.e. today's flat translucent dim fill (and this branch's eased
  version of it) is *not* GPU-eligible even now.
- **Texture blit**: CPU-accessible XRGB8888/ARGB8888 sources only (no
  arbitrary dma-buf); integer nearest upscale, or unscaled bilinear
  (identical sampling). Downscale, fractional scale, partial clips, and any
  color-metadata/opacity beyond fully-opaque premultiplied all replay with
  Pixman.
- **No blur, convolution, or shader stage of any kind** is exposed anywhere
  in this audit. VG-Lite here is a blit/fill/compositing engine, not a
  general-purpose or filter-capable GPU; there is nothing resembling a
  hardware box/Gaussian kernel to call into.
- It is not the default renderer (`WLR_RENDERER=vglite` plus an explicit
  `K230_VGLITE_ALLOW_UNPROVEN_CACHE=1` are both required just to attempt GPU
  submission), and board evidence already on file
  (`docs/evidence/vglite-decision-diagnostics.md`) shows a real Sway
  session still falling back to Pixman replays for ordinary scene content
  (default `GAMMA22`/sRGB color metadata on ordinary Wayland surfaces is
  unconditionally ineligible). Physical RGBA/alpha correctness, cache
  ownership and scanout ownership remain open OpenSpec tasks, not shipped
  behavior.

Net: even setting aside that a blurred backdrop is inherently translucent
(and therefore Pixman-only under this fork's own rules), there is no blur
primitive to reach for on this chip at all. Any blur has to be software,
on the CPU, using Pixman/plain code -- exactly the renderer already in
production.

## 3. Cost of the three strategies

All host numbers below are **measured on this development machine (AMD
Ryzen 9 5950X, single thread, `rustc -O`)**, a throwaway standalone
benchmark (`box_blur_horizontal`/`vertical`, 3-pass separable box blur,
plus a hand-written bilinear upscale), not compiled into the crate or
committed. They are then scaled by a labeled, honest *estimate* -- not a
measurement -- of **20-40x slower** for a single-issue, in-order 1.6 GHz
C908 core versus a ~4.5 GHz out-of-order desktop core on this kind of
scalar, memory-bound, branchy pixel loop. That multiplier is not derived
from any board measurement of this workload; it is the kind of ratio
commonly seen between a small in-order embedded core and a modern
desktop core on non-vectorized integer code, offered so the conclusion
below is checkable, not so the number is treated as calibrated.

Host results:

```
full 568x1232 3-pass box blur (radius 8):                    128.6 ms/iter
downscaled 94x205 3-pass box blur (radius 2):                  1.11 ms/iter
bilinear upscale 94x205 -> 568x1232:                           5.81 ms/iter
full 568x1232 3-pass box blur (radius 3, per-frame stand-in): 59.05 ms/iter
```

**(a) Bake the wallpaper once per theme change, cache it, cross-fade.**
The blur computation is entirely off the interactive path (it runs once,
at the same time the existing wallpaper decode/cache already runs --
see `nix/rust-shell-client/src/background_decode.rs` and
`docs/evidence/omarchy-themes/rust-background-decode-host.md`, which
already accepts comparable one-shot latency for a theme apply). Using the
same downscale-blur-upscale pipeline as (b) rather than a naive full-res
blur, that one-time bake is ~7 ms host, **an estimated ~0.14-0.28 s on the
board** -- trivial next to a theme apply that already writes a wallpaper
cache to disk. The only thing that runs *every frame* is a straight alpha
cross-fade between two already-decoded, already-cached bitmaps (sharp and
blurred), driven by this branch's own `tray_backdrop_alpha` fraction --
the same class of operation (one full-panel image composite) the board's
existing 14 ms whole-scene budget already contains routinely. **Estimated
live cost: comparable to the current flat-fill backdrop, well under 1 ms
of the ~14-19 ms frame budget; effectively free relative to what already
ships.**

**(b) Live downscaled blur of the current app snapshot at drag-start.**
Downscale 6x + 3-pass box blur + bilinear upscale back to full panel size:
~7 ms host total, an estimated **~0.15-0.3 s one-time hit** exactly at
gesture start, on the same single hart that has to keep servicing the
drag. That is a real, likely-noticeable stutter right where the finger
first moves -- 8-15 dropped refresh intervals -- unless it can be computed
ahead of the touch-down rather than in response to it. This board has no
second core available today to hide that behind (see section 1); the
"pre-blur speculatively during idle, swap in when ready" trick this
codebase already uses elsewhere for theme pre-render
(`RendererCache::render_candidate_overlay`/`adopt_prerendered_overlay`) is
the only way to make this safe, and it still leaves a window where the
first frame(s) of a drag show the un-blurred fallback.

**(c) True per-frame live blur.** Not viable, and not close: even a
*lighter* radius-3 full-resolution 3-pass blur measured **59 ms/iter on a
5950X**, i.e. an estimated **~1.2-2.4 seconds per frame** on the board --
60-125x the ~19 ms refresh budget on a core that also has to do everything
else. There is no plausible radius/quality reduction that closes a two
order-of-magnitude gap.

## 4. Where "blur what's behind" actually has to live

This is the finding that most changes the recommendation. The shade's
top-edge drag is a **global** gesture, armed from within any foreground
card/app, not only from Home: `nix/card-shell/adapter.c`'s touch-down
handler arms `shell.shade_gesture` whenever a touch starts inside the top
edge band and no launcher/keyboard/other contact owns input --
independent of which card is currently maximized
(`nix/card-shell/adapter.c` around the `shade_gesture` touch-down site).

The Rust shell client (`nix/rust-shell-client`) only ever owns its own
overlay surface's pixels -- see `protocol.rs`'s own doc: "this model owns
only overlay pixels and a reversible settle from current state." Today's
dim/fade backdrop works uniformly regardless of what is behind it *only*
because it is pure alpha transparency, composited by Sway/wlroots itself
(`nix/card-shell/adapter.c`) against whatever surface is beneath -- Home's
wallpaper, or a live app card, it does not matter, because the client
never reads those pixels; the compositor's scene graph does the blending.

A blur cannot work that way. Blurring requires reading the actual pixels
of whatever is behind the overlay, and:

- When Home is behind the shade, the Rust client itself is also the thing
  that rendered Home's wallpaper (`draw_wallpaper`/`background_decode.rs`),
  so it can bake and cross-fade to a blurred variant of its own bitmap
  entirely client-side -- this is exactly strategy (a), and it is genuinely
  cheap and self-contained.
- When any other app/card is behind the shade, its pixels belong to a
  different Wayland surface, owned by a different process, composited by
  Sway -- the Rust client has no access to them at all. Blurring that case
  can only happen in the compositor (`nix/card-shell/adapter.c`), and would
  require either a live per-frame blur of the composited framebuffer
  (ruled out in section 3c) or a one-time compositor-side snapshot/capture at
  gesture-start fed through the same downscale-blur-upscale pipeline as
  (b), with the same ~0.15-0.3 s one-time-hit risk and no second core to
  hide it behind.

So "blur the backdrop" is really two different features with very
different costs: trivial over Home, and a real (if bounded) compositor
project everywhere else. Scoping a prototype to "blur only works when
Home happens to be behind the shade, and silently stays a flat dim
everywhere else" would be a visibly inconsistent, easy-to-misjudge-as-done
feature to ship as a first cut.

## 5. Recommendation

Do not build a live/per-frame blur (3c rules it out cleanly). Do not chase
VG-Lite for this (no blur primitive exists on that path, and it is not
even eligible for the alpha content this backdrop already is, section 2). If
this is wanted, the only strategy worth spending time on is (a): bake a
blurred wallpaper variant into the existing `background_decode.rs` cache
alongside the sharp one, keyed the same way, and cross-fade between them
in `nix/rust-shell-client/src/render.rs`'s `apply_tray_backdrop` using the
already-eased `tray_backdrop_alpha` fraction from this branch -- Rust
client only, no compositor change, no per-frame blur, estimated well under
1 ms of live cost. It would need to be explicit that it only applies while
Home is the layer behind the shade; over any other app it would need to
keep today's flat, eased dim (correct and consistent, not a regression)
rather than attempt an incorrect or missing blur. Extending it to "blur
whatever's actually behind" is a separate, materially bigger
compositor-side change (one-time framebuffer snapshot + async blur, ideally
off a second core this board does not currently expose to Linux) and is
not recommended as a follow-on to this fix.

No prototype branch was created: the only cheap, self-contained case (a)
is scoped to Home-only, and a prototype that silently doesn't blur over
apps risked reading as a finished feature rather than the half-scope it
is. This note is the deliverable for that half; a Home-only prototype can
be requested explicitly if wanted.
