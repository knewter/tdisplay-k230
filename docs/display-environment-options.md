# What can draw on this screen

Investigated 2026-09-20 on `solomon` (x86_64-linux, 32 cores, 125 GiB RAM),
against the nixpkgs pin in `flake.lock`
(`20b1ddd1aa5ace70c9468305030aa4f9ef79671b`).

The question is which display environment this board can actually run, given
that it has a 568x1232 portrait AMOLED, a touch panel, two C908 cores, 1 GiB of
RAM, and **no GPU driver of any kind**. Josh named Hyprland first and SXMO as
the fallback. Neither survives contact with the constraints, and the reasons
are different for each.

Two kinds of claim appear below and they are not interchangeable:

- **Read in source.** A file in an upstream tree, cited by path and line. This
  is grounding under the house rules.
- **Measured here.** A `nix build --dry-run` against the pinned nixpkgs, run on
  this host with a warm store that already contains the built k230 closure
  (`/nix/store/lzg30ba…-nixos-system-nixos-26.11.20260919.20b1ddd`). Every
  build number in this document is therefore an *incremental* cost on top of
  that 1.2 GiB closure, not a from-scratch number.

Nothing here has run on the board. Nothing here has run at all. The panel does
not come up under Linux yet; that is `the-screen-comes-up-under-linux`.

---

## 1. The GPU situation, stated precisely

The K230's "2.5D" block has no Mesa driver and no Vulkan driver. What the
kernel will expose, if `the-screen-comes-up-under-linux` succeeds, is a DRM/KMS
device: a CRTC, a MIPI-DSI encoder, and the RM69A10 panel behind
`panel-canaan-universal`. Buffers come from `DRM_IOCTL_MODE_CREATE_DUMB` — plain
CPU-visible memory the display controller can scan out. There is no render
node, no GBM device, no EGL, no GL.

So the question for every candidate is the same: **can it composite into a
dumb buffer with the CPU?**

### The two software paths, and why only one is cheap

There are genuinely two ways to get pixels without a GPU:

**(a) A CPU compositor with no GL at all.** wlroots' Pixman renderer is this.
Pixman is a 2D rasteriser — blits, blends, transforms — with no shader model
and no GL API surface. No Mesa, no LLVM.

**(b) Mesa's software GL.** `llvmpipe` (LLVM-JIT'd) or `softpipe`
(interpreted), reached through EGL with the `kms_swrast` DRI driver. This
produces a real GLES context over dumb buffers, so a GL-only compositor can be
made to start. The pinned nixpkgs does build these for riscv64 — the mesa
derivation's meson flags include `-Dgallium-drivers=…,llvmpipe,…,softpipe,…`
and `-Dclang-libdir=/nix/store/…-clang-riscv64-unknown-linux-gnu-21.1.8-lib/lib`.

Path (b) is not a free escape hatch. It drags a riscv64 LLVM 21 and the whole
of Mesa into the closure — `nix build --dry-run` for `pkgsCross.riscv64.mesa`
reports 4 derivations to build and **575.2 MiB to download, 2.4 GiB unpacked**.
And it puts a JIT compiler and a full GL implementation between a 1.6 GHz
in-order core and 700,000 pixels. Nobody has measured llvmpipe on a C908 and
this document is not going to pretend otherwise; what can be said with
confidence is that it costs more than every other option combined, to produce
the slowest result.

Path (a) is what everything below is judged against.

---

## 2. Hyprland — not viable

**Hyprland requires OpenGL ES 3 at build time and has no software renderer.**

From `hyprland-0.56.2/CMakeLists.txt`:

```
129:  set(GLES_VERSION "GLES3")
130:  find_package(OpenGL REQUIRED COMPONENTS ${GLES_VERSION})
…
529:  target_link_libraries(hyprland_lib PUBLIC OpenGL::EGL OpenGL::GLES3 …)
```

`REQUIRED` — the build fails without it. Hyprland's only renderer is
`src/render/OpenGL.cpp` (`CHyprOpenGLImpl`). Pixman appears in the Hyprland
tree, but only as region arithmetic (`pixman_box32` in `scissor()` at
`src/render/OpenGL.cpp:1020`), never as a rasteriser. There is no
`WLR_RENDERER=pixman` to set, because since 0.41 Hyprland does not use wlroots
at all: it uses its own backend library, **aquamarine**, whose
`CMakeLists.txt:22` reads `find_package(OpenGL REQUIRED COMPONENTS "GLES3")`
and whose `src/backend/drm/Renderer.cpp` is a GLES shader pipeline. Aquamarine
does carry `src/allocator/DRMDumb.cpp`, so it can *allocate* dumb buffers — but
it still renders into them with GL.

So Hyprland could only run on Mesa's llvmpipe, i.e. path (b) above.

**And the build cost is the worst of any candidate by a wide margin.** Measured:

| what | derivations to build | to fetch (unpacked) |
| --- | --- | --- |
| `pkgsCross.riscv64.hyprland` alone | 159 | 2.2 GiB |
| k230 closure + `hyprland` + `foot` | 184 | 2.2 GiB |

The 159 includes, for riscv64: **Qt 6** — `qtbase`, `qtdeclarative`,
`qtwayland`, `qtsvg`, `qtshadertools`, `qtlanguageserver` — pulled in by
`hyprland-qtutils`, which drags `libpq`, `mariadb-connector-c`, `unixodbc` and
`psqlodbc` behind it. It also includes `glslang` (a SPIR-V compiler, on a board
with no shader hardware), `librsvg` with its vendored Rust crates, and `libjxl`.

Worst of all, it includes `riscv64-unknown-linux-gnu-gcc-16.2.0` and its
wrappers — **a second full GCC cross-bootstrap**, because nixpkgs builds
Hyprland with `gcc16Stdenv` while the rest of this closure is on GCC 15.3.0.
`docs/evidence/cross-build.txt` already records what that costs: the musl
bootstrap needed for the initrd was "the largest single cost in the first
build" and roughly 45 minutes of the 73.

Hyprland is a compositor for people with a GPU, a lot of RAM, and animations
they want to look at. This board has a 4.1" screen, two in-order cores, and no
GPU. **Recommend against, without reservation.** If the answer to "but I want
Hyprland" is "then run Mesa llvmpipe", the honest reply is that we would be
adding 2.4 GiB of LLVM and Mesa, plus a third cross toolchain, to make a
compositor that exists to draw blurred rounded corners run at some unmeasured
frame rate on a phone-sized panel.

---

## 3. wlroots with the Pixman renderer — this is the path

wlroots 0.20.2 ships a Pixman software renderer and, crucially, a DRM
**dumb-buffer allocator**, so the whole pipeline can run with no GBM and no
render node.

**Renderer selection**, `wlroots-0.20.2/render/wlr_renderer.c:220-228`:

```c
	static const char *renderer_options[] = {
		"auto",
		"gles2",
		"vulkan",
		"pixman",
		NULL
	};

	const char *renderer_name = renderer_options[env_parse_switch("WLR_RENDERER", renderer_options)];
```

`WLR_RENDERER=pixman` is a supported, first-class selection, not a debug hook.

**Allocator selection**, `wlroots-0.20.2/render/allocator/allocator.c:98-152`.
`wlr_allocator_autocreate()` tries GBM first, but only when
`(backend_caps & WLR_BUFFER_CAP_DMABUF) && (renderer_caps & WLR_BUFFER_CAP_DMABUF)`.
The Pixman renderer advertises `WLR_BUFFER_CAP_DATA_PTR`, not DMABUF
(`render/pixman/renderer.c:196-204` returns formats only for
`buffer_caps & WLR_BUFFER_CAP_DATA_PTR`), so the GBM branch is skipped and
control reaches:

```c
	uint32_t drm_caps = WLR_BUFFER_CAP_DMABUF | WLR_BUFFER_CAP_DATA_PTR;
	if ((backend_caps & drm_caps) && (renderer_caps & drm_caps)
			&& drm_fd >= 0 && drmIsMaster(drm_fd)) {
		wlr_log(WLR_DEBUG, "Trying to create drm dumb allocator");
```

The condition is a DRM fd on which we are master. **No render node is
required.** `include/render/allocator/drm_dumb.h` confirms what it makes:
`wlr_drm_dumb_allocator_create(int fd)`, producing `wlr_drm_dumb_buffer`s with
a `void *data` pointer for the CPU to write into.

That is exactly the shape of the device the K230 will expose. It is the single
most important finding in this document.

One caveat, and it is the main technical risk: this needs the kernel's DRM
driver to support `CREATE_DUMB` and to give us a modesetting node. A driver
that only registers an fbdev, or a KMS driver without dumb-buffer support,
breaks the whole approach. **Unverified** — the panel does not come up yet.

wlroots can also be built with the GL renderer compiled out entirely
(`meson.options`: `option('renderers', type: 'array', choices: ['auto','gles2','vulkan'], value: ['auto'])`
and `option('allocators', …choices: ['auto','gbm','udmabuf'])`), which would
remove libglvnd and libgbm from the picture. Measured: this did not change the
count of riscv64 derivations that must be built locally, because those libraries
substitute from cache. It is a closure-size tidy-up, not a build-time saving.

---

## 4. Candidates, measured

All numbers are `nix build --dry-run` of a NixOS `toplevel` built from this
repo's own `nix/k230.nix` + `nix/hardware.nix` plus the listed packages, on a
warm store containing the baseline closure. The baseline itself reports zero
derivations to build, so these are pure deltas.

Every wlroots-based row has Xwayland disabled — `wlroots.override { enableXWayland = false; }`.
That single override is worth **55 derivations**: plain
`pkgsCross.riscv64.wlroots` needs 85 local builds and 500 MiB of fetches, and
with Xwayland off it needs 30 and 210 MiB. Xwayland drags in GTK 3, CUPS,
Avahi, at-spi2-core and dconf. There is no X11 application we want on a 4.1"
touchscreen, so this is free.

| stack | local riscv64 builds | fetched (unpacked) |
| --- | ---: | ---: |
| baseline k230 closure (already built) | 0 | 0 |
| `buffybox` (LVGL, direct to DRM) | 27 | 213 MiB |
| `kmscon` | 29 | 112 MiB |
| `cage` + `foot` | 60 | 274 MiB |
| **`cage` + `foot` + `wvkbd`** | **68** | **292 MiB** |
| **`sway` + `foot` + `wvkbd`** | **89** | **875 MiB** |
| `sway` + `foot` + `wvkbd` + `bemenu` + `mako` | 108 | 1.0 GiB |
| `dwl` + `foot` + `wvkbd` | 112 | 513 MiB |
| `labwc` + `foot` | 117 | 709 MiB |
| `hyprland` + `foot` | 184 | 2.2 GiB |
| `weston` (nixpkgs defaults, standalone) | 288 | 3.8 GiB |
| `phosh` | 530 | — |
| `mesa` (for reference: the cost of software GL) | 4 | 2.4 GiB |

### Reading the table

**Sway's extra 21 derivations over cage** are almost all font and image
plumbing rather than the compositor: `librsvg` with its vendored Rust crates,
`gdk-pixbuf`, `libjxl`, `openexr`, `libwebp`, plus GTK 3 and its CUPS/Avahi tail
arriving through `mako` and `bemenu`. `sway-unwrapped` itself is one derivation.
Dropping `mako` and `bemenu` saves 19 builds and 125 MiB.

**Weston is a trap in nixpkgs.** Weston 16.0.0 does still have the Pixman
renderer — `libweston/pixman-renderer.c` is compiled into libweston core
(`libweston/meson.build:41`), `WESTON_RENDERER_PIXMAN = 2` is in the public
header at `include/libweston/libweston.h:2565`, and `man/weston.ini.man:198-215`
documents `renderer=pixman` with `use-pixman=true` as its deprecated spelling.
So Weston would work. But nixpkgs builds it with `-Dbackend-rdp=true`,
`-Dbackend-vnc=true`, `-Drenderer-vulkan=true`, `-Dshell-lua=true`,
`-Dxwayland=true`, which pulls FreeRDP, GStreamer, FFmpeg, PipeWire, GTK 4 and
libcamera: 288 derivations. Getting Weston down to size means carrying a
package override that fights the nixpkgs default on every bump. Rejected on
maintenance cost, not on technical merit.

**Cage is the cheapest real compositor and cannot be the answer.** `cage` has
no layer-shell support at all — `grep -rn 'layer_shell' cage-0.3.1/` returns
nothing; the source tree is `cage.c output.c seat.c view.c xdg_shell.c
xwayland.c` and that is all of it. Every Wayland on-screen keyboard, status bar
and notification daemon is a `wlr-layer-shell` client. On a handheld with no
physical keyboard, a compositor that cannot host an OSK is a dead end.

Cage remains useful as the **first-light smoke test**: it is 68 derivations and
it answers "does a Wayland compositor start on this DRM device with
`WLR_RENDERER=pixman`" without committing to anything.

**dwl** is `dwm` for Wayland — genuinely tiny and wlroots-based, so Pixman
applies. It is configured by editing `config.h` and recompiling, which under
Nix means a patch or an overlay for every keybinding change, and it measured
*more* expensive than sway-minus-extras anyway (112 vs 89) because nixpkgs
builds it against `wlroots_0_19` and Xwayland stayed in. Not worth it.

**labwc** is a competent stacking wlroots compositor, but it is a desktop
paradigm — title bars, a root menu, window decorations — on a 568-pixel-wide
screen, and it measured more expensive than sway.

---

## 5. SXMO — what it actually is, and why it is not a shortcut

SXMO ("Simple X Mobile", from sxmo.org) is not a compositor. It is a large
collection of POSIX shell scripts (`sxmo-utils`) that glue together existing
programs into a phone UI: menus via `dmenu`/`bemenu`, an on-screen keyboard via
`svkbd`/`wvkbd`, a terminal, a status bar, and hooks for calls, SMS and modem
state. It ships **two variants**:

- **sxmo-dwm** — X11, with a patched `dwm` as the window manager and `svkbd`
  as the keyboard.
- **sxmo-sway** — Wayland, with a patched **sway** as the compositor,
  `wvkbd` as the keyboard, plus `bemenu`, `wob` and friends.

The Wayland variant is the one SXMO points people at. **So SXMO's fallback
position is sway.** Choosing sway does not close the SXMO door; it opens it.

What makes SXMO unusable as a drop-in here:

- **It is not in nixpkgs.** Measured against the pin: every attribute name
  matching `.*[sS]xmo.*` — the empty list. There is no `sxmo-utils`, no NixOS
  module, nothing. Adopting SXMO means packaging a shell-script distribution
  and writing the module from scratch, and SXMO's scripts assume a
  PostmarketOS-shaped system (specific service names, specific paths,
  `/etc/profile.d` hooks) rather than a Nix store.
- **Its X11 variant is out on the same grounds as Hyprland, differently.**
  X11 on this board means `xf86-video-modesetting` doing software composition
  through the shadow framebuffer — possible, but it is strictly more machinery
  than the Wayland path for strictly less.
- **It assumes a phone**, with a modem, a proximity sensor, a power button that
  generates the menu event, and hardware volume keys. This board has none of
  those. A large part of what SXMO is would be inert.

SXMO is worth keeping as a **source of designs** — its gesture vocabulary and
its menu-driven interaction model are exactly right for a screen this shape —
without taking the distribution. The parts we would actually use (`wvkbd`,
`bemenu`, sway) are in nixpkgs already and are in the sway row of the table.

---

## 6. Genuinely lightweight, non-compositor options

Worth naming because a compositor may be more machinery than a single-purpose
handheld needs.

**buffybox** (27 derivations, 213 MiB) — PostmarketOS's LVGL-based suite:
`unl0kr` (an unlock UI) and `buffyboard` (an on-screen keyboard that types into
the *kernel console* via uinput). It renders LVGL directly to DRM dumb buffers
or fbdev, with no compositor and no Wayland at all. It is the cheapest thing in
the table that puts a touch-driven UI on the screen, and it is an existence
proof that LVGL-on-DRM works as a shipping configuration. Note that LVGL itself
is not packaged in nixpkgs — `.*lvgl.*` matches nothing at the pin — so using
LVGL directly means vendoring it.

**A direct DRM/KMS Dozer shell.** Dozer is a Crux application: a Rust core
behind a serialised FFI boundary with swappable shells. The lightest possible
shell for this board is a Rust binary that opens `/dev/dri/card0`, creates a
dumb buffer, rasterises into it with `tiny-skia` or `softbuffer`, and reads
touch from `libinput` or raw evdev. No compositor, no Wayland, no IPC, one
process. The closure cost is a Rust toolchain plus nothing.

This is a real option and it should not be dismissed as exotic — it is what
`buffybox` does, in Rust instead of C. Its cost is that there is no window
system, so no second application, no terminal over the top, no
`grim`-style screenshots for evidence, and no off-the-shelf keyboard. That is
why it is not the recommendation: during bring-up we want a terminal on the
panel more than we want minimalism.

**kmscon** (29 derivations, 112 MiB) is a KMS terminal emulator, not a UI. It
would give a nicer console on the panel than the kernel's, and nothing else.
Mentioned for completeness.

---

## 7. Touch on a portrait panel

The panel is 568x1232 — portrait natively. The GT9895 reports in the panel's own
coordinate space. So in the simplest configuration — one output, no rotation —
**no transform is needed at all**, and a touch lands where it is seen. This is
the configuration to aim for, and it is a reason not to rotate the output.

The mechanisms, when something is wrong:

- **Output transform.** `sway-output(5)` (`sway/sway-output.5.scd:107`):
  `output <name> transform <transform> [clockwise|anticlockwise]`, with `90`,
  `180`, `270` and the `flipped-*` variants. wlroots applies the transform to
  touch input as well as to output, so rotating the output *should* keep touch
  aligned. With the Pixman renderer the rotation is done on the CPU for every
  frame, which on a C908 is a cost we would be paying for nothing.
- **Mapping an input device to an output.** `sway-input(5)`
  (`sway/sway-input.5.scd:110`): `input <identifier> map_to_output <identifier>`
  — "Only meaningful if the device is a pointer, touch, or drawing tablet
  device." Underneath this is wlroots' `wlr_cursor_map_input_to_output()`
  (`include/wlr/types/wlr_cursor.h:202`). With a single output it is a no-op,
  but writing it explicitly means a second output — an HDMI dongle, a nested
  session — does not silently steal the touches.
- **Calibration.** `sway-input(5):140`: `input <identifier> calibration_matrix
  <6 space-separated floating point values>`, a libinput calibration matrix.
  This is the fix for axes that are swapped or mirrored — the classic
  "touch works but is upside down" failure. It can also be set at the udev
  level via `LIBINPUT_CALIBRATION_MATRIX`, which is the right place if the
  fix belongs to the hardware rather than to one compositor's config.

The failure mode to design the evidence around: touch that reports coordinates
but reports them rotated or mirrored looks like working touch in a log and like
broken hardware to a person. `the-screen-comes-up-under-linux` already requires
an `evtest` session showing a *deliberate movement* rather than a tap, for
exactly this reason. A shell change should require the same thing one layer up:
a touch must activate the thing under the finger.

An on-screen keyboard needs `wlr-layer-shell` (`wvkbd` is a layer-shell client),
and it needs the compositor to support the `virtual-keyboard-v1` protocol to
inject the keystrokes. sway supports both. cage supports neither.

---

## 8. Conclusion

- **Hyprland: no.** GLES3 is a hard build requirement
  (`CMakeLists.txt:129-130`), there is no software renderer, and the riscv64
  build costs 184 derivations including Qt 6 and a second GCC cross-bootstrap.
- **SXMO: not as a distribution, yes as a design source.** It is absent from
  nixpkgs entirely, and its Wayland variant is sway underneath anyway.
- **sway + wlroots with `WLR_RENDERER=pixman`, Xwayland disabled**, is the
  recommendation: **89 riscv64 derivations and 875 MiB of substituted paths** on
  top of the existing closure, for sway, `foot` and `wvkbd`. It has layer-shell
  (so an on-screen keyboard), `map_to_output` and `calibration_matrix` for
  touch, a NixOS module, and it is the compositor SXMO would want if we ever go
  there.
- **cage is the smoke test**, at 68 derivations, to answer "does a Pixman
  wlroots compositor start on this DRM device" before spending the rest.
- **The direct-to-DRM Dozer shell stays on the table** as the endgame, once
  there is something to show and the terminal is no longer needed on the panel.

The wall-clock cost is not yet measured. For scale, `docs/evidence/cross-build.txt`
records 353 local derivations in 73 minutes on this host in an oversubscribed
run, of which roughly 45 minutes was a single GCC/musl bootstrap. The sway stack
needs no new toolchain, so 89 derivations of ordinary C, Rust (`librsvg`) and
Meson packages should land well inside an hour. Measuring it is a task, not a
guess.
