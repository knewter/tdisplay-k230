## Context

See proposal.md — Why. The full comparison, with every measurement and every
source citation, is `docs/display-environment-options.md`; this document
records only what shapes the approach.

**The layer this work lands in is Nix and userspace.** Nothing here touches
stage 1, the kernel, or the device tree. That is deliberate and it is the
cleanest seam this project has: `the-screen-comes-up-under-linux` owns
everything down to and including `/dev/dri/card0` and `/dev/input/event*`; this
change owns everything above them. If a problem turns out to need a device tree
property — a swapped touch axis, a plane format — it belongs on the other side
of that line and gets fixed there, not worked around here.

What constrains the approach:

- **No GPU driver, and none coming.** The K230's 2.5D block has no Mesa GL or
  Vulkan driver. The kernel exposes a card node with dumb buffers and no render
  node. The measured closure contains `mesa-libgbm`, a generic buffer-manager
  library linked by wlroots but unused by Pixman's allocator; that is not a GL
  runtime and does not change the CPU/dumb-buffer rendering path.
- **wlroots already handles exactly this case.** Its Pixman renderer needs no
  GL, and its DRM dumb allocator needs no GBM and no render node. It even
  selects Pixman on its own when `drmGetRenderDeviceNameFromFd()` returns NULL
  (`render/wlr_renderer.c:268`).
- **Every riscv64 package is compiled.** `docs/evidence/cross-build.txt`: the
  existing 1.2 GiB closure took 353 local derivations and 73 minutes, of which
  a single extra cross toolchain was the largest cost. Package choice here is a
  build-time decision as much as a runtime one.
- **1 GiB of RAM and two in-order cores.** A compositor that is fine on a
  laptop is not automatically fine here, and a full frame at 568x1232 in
  ARGB8888 is 2.8 MiB the CPU has to touch.
- **The panel is portrait natively.** 568x1232, and the touch controller
  reports in the same space. Every rotation we do not do is per-pixel CPU work
  we do not pay for.

## Goals / Non-Goals

**Goals:**

- Pick one compositor and be able to say, from source, why it can run here.
- Get the cheapest possible *first light* — does a Wayland session start on
  this DRM device at all — before spending the full build.
- Leave the Dozer shell decision untouched, including leaving the door open to
  a shell that has no compositor under it.

**Non-Goals (design level, beyond the proposal's):**

- Broad desktop customization. The bounded touch bar is part of making the
  cable-free session usable: Apps, Windows/Home, Keyboard, and System only.
  Keybinding suites, gesture bindings, theming, notifications, and a general
  application catalogue remain follow-on work.
- Packaging SXMO. It is absent from nixpkgs and its scripts assume a
  PostmarketOS-shaped system; if we want it later, sway being in place is the
  prerequisite, not an obstacle.
- Deciding anything about Wi-Fi, so that the board being headless-networkable
  and the board being usable stay independent questions.

## Decisions

**Wayland, not X11.** The X11 path on a GPU-less board is
`xf86-video-modesetting` with a shadow framebuffer — it works, and it is
strictly more machinery for strictly less. It also means an X server, an input
driver stack, and a second window-system vocabulary in a repository that has
none. Rejected. Note this also rejects SXMO's dwm variant by construction.

**wlroots with the Pixman renderer, not Mesa's software GL.** Both reach
pixels. Path (b) — llvmpipe via `kms_swrast` — genuinely works on riscv64 now
(Mesa >= 24.2 forces ORCJIT on architectures LLVM's MCJIT never supported, and
riscv64's default gallium driver list includes llvmpipe and softpipe), so this
is a real choice rather than a forced one. It is rejected on cost: `mesa` for
riscv64 is 2.4 GiB unpacked and brings LLVM 21, to put a JIT and a full GL
implementation between two 1.6 GHz in-order cores and 700,000 pixels. Pixman is
a 2D rasteriser with no GL API surface at all, and emersion's introduction of
it said plainly that it "should be significantly faster than our previous
llvmpipe-based fallback". We would be paying 2.4 GiB to go slower.

**sway, not cage.** Cage is cheaper — 68 derivations against 89 — and it was
the initial favourite. It is disqualified by one fact: `grep -rn 'layer_shell'`
over the cage source tree returns nothing. Its entire source is `cage.c
output.c seat.c view.c xdg_shell.c xwayland.c`. Every Wayland on-screen
keyboard is a `wlr-layer-shell` client, and a board with no physical keyboard
needs one. Cage survives as the smoke test in task group 2, where "does a
Pixman compositor start on this device" is the only question being asked.

**sway, not dwl, labwc, river or Weston.** dwl is configured by editing
`config.h` and recompiling, which under Nix means an overlay per keybinding;
it also measured *more* expensive than sway (112 against 89). labwc is a
desktop stacking paradigm — title bars and a root menu — on a 568-pixel-wide
screen, and also more expensive. Weston is the one that is genuinely close:
`renderer=pixman` is documented, `drm_fb_create_dumb()` is right there in
`libweston/backend-drm/fb.c`, its GBM code is behind `#ifdef BUILD_DRM_GBM`,
and `kiosk-shell` suits a handheld. It loses on packaging, not merit: nixpkgs
builds Weston with RDP, VNC, Vulkan, Lua and Xwayland enabled — 288
derivations, 3.8 GiB — and trimming it means an override that fights the
nixpkgs default at every bump. **Weston is the recorded fallback**: if sway
fails for a reason that is sway's fault rather than the hardware's, a trimmed
Weston is the next thing to try.

**sway also because SXMO is sway.** Josh named SXMO as the fallback. Its
Wayland variant — `swmo` — is sway with `wvkbd`, `wofi`, `wob`, `foot` and the
`lisgd` gesture daemon on top, and sxmo.org recommends it over the dwm variant.
Choosing sway costs nothing against that fallback and is a prerequisite for it.
What we are declining is SXMO's *packaging*, which does not exist in nixpkgs at
all (no `sxmo-utils`, no module; the two third-party attempts are unmaintained
since 2024 and 2022), and its assumption of a phone — modem, proximity sensor,
a power button that raises the menu — none of which this board has.

**Use an i3bar click menu for the few controls the board needs.** `swaybar`
already turns a touchscreen release inside a status block into a JSON click
event, which is the same proven path used to toggle wvkbd. A `status_command`
can retain a small page state without a new GUI toolkit or a launcher whose
touch behaviour has not been established. Four 128-pixel blocks, leaving room
for swaybar's text padding, in a 56-pixel
bar give Apps, Windows/Home, Keyboard, and System visible targets. Apps starts
or focuses a readable `foot` terminal and a `htop` monitor. Windows pages
through actual sway containers and has Home, which uses the terminal presence
check so closing every terminal does not strand the user.
System changes to a confirmation page before its narrowly-authorized
`systemctl reboot` or `systemctl poweroff`, and Cancel returns to the main
page. This is SXMO-inspired interaction, not SXMO packaging.

The menu implementation can be exercised with `evemu` and `/dev/uinput`, but
that only proves injected input reached swaybar. It does not prove a finger
lands on the expected control through the GT9895 and panel glass; the latter
stays a photographed board claim.

**Hyprland is rejected on two independent grounds, either sufficient.**
First, it cannot run without GL: `CMakeLists.txt:129-130` makes GLES3 a
`REQUIRED` build dependency, its only renderer is `src/render/OpenGL.cpp`, and
since 0.41 it uses aquamarine rather than wlroots so there is no
`WLR_RENDERER` knob to turn. Aquamarine's `DRMDumb.cpp` is a cursor-plane
fallback, not a render path — `Backend.cpp` builds `CGBMAllocator` as the
primary allocator or logs "Cannot open backend: no allocator available".
Second, the build: 184 derivations and 2.2 GiB, including Qt 6 (through
`hyprland-qtutils`, which drags `libpq`, `mariadb-connector-c` and `unixodbc`),
`glslang` on a board with no shaders, and a full second GCC cross-bootstrap
because nixpkgs builds it with `gcc16Stdenv` against this closure's 15.3.0.
It could be made to run on llvmpipe — aquamarine issue #370 describes exactly
that on the display-only `qxl` driver, complete with a 425 MB log from
uncached EGL retries. That is the best case and it is not good enough.

**Disable Xwayland.** Worth 55 of wlroots' 85 derivations on its own, and it
removes GTK 3, CUPS, Avahi, at-spi2-core and dconf from the closure. The cost
is that no X11 application can run on this board. On a 4.1" touchscreen with no
keyboard that is not a cost. Recorded here because it is easy to hit later and
hard to diagnose from "the application did not start".

**Set `WLR_RENDERER=pixman` explicitly even though wlroots would pick it.**
`render/wlr_renderer.c:268` selects Pixman automatically when the backend's DRM
fd has no render node, which is this board. Setting it anyway turns a silent
fallback into a stated intention: if someone later adds a GPU driver, the
declaration is visible and deliberate rather than a behaviour that quietly
changed underneath us.

**Do not rotate the output.** The panel is portrait natively and the controller
reports in the same space, so the correct configuration is `transform normal`
and nothing else. With Pixman, a non-normal transform is a per-pixel CPU
rotation on every composite. If the axes turn out wrong, fix them in the device
tree (`touchscreen-swapped-x-y`, `touchscreen-inverted-x/-y`) — which means
fixing them in `the-screen-comes-up-under-linux`'s territory — or failing that
with a libinput calibration matrix. **Never both**: an output transform and a
calibration matrix compose, and a double rotation looks exactly like broken
hardware.

**Write `map_to_output` explicitly rather than trusting the heuristic.**
sway auto-maps a built-in touch device to a built-in output
(`sway/input/seat.c:723-730`), and `get_builtin_output_name()` at lines 654-668
looks for exactly one output named `eDP-*`, `LVDS-*` or **`DSI-*`** — which a
MIPI-DSI panel will be. So it will very likely work with no configuration. One
explicit line removes the dependency on that, and it matters because a touch
device that is *not* mapped to an output gets no transform applied at all,
which is the mechanism behind every "I rotated the screen and touch went 90
degrees off" report.

## Risks / Trade-offs

- **The kernel's DRM driver does not support dumb buffers, or registers only an
  fbdev.** → The entire approach collapses; wlroots has nothing to allocate
  from. Mitigation: this is checked *first*, in task group 1, with `drm_info`
  and a `modetest` capability dump, before a single compositor package is
  built. Canaan's own DRM reference describes `DRM_IOCTL_MODE_CREATE_DUMB` on
  `/dev/dri/card0`, which is encouraging — but vendor documentation grounds
  nothing on this board, as the Wi-Fi radio already demonstrated.
- **The primary plane does not advertise XRGB8888.** wlroots' DRM backend
  prefers it; Canaan's documentation lists the OSD plane formats as `AR24,
  AR12, AR15, RG24, RG16`, which includes ARGB8888 and RGB565 but not `XR24`.
  → Presents as a compositor that starts and then fails to commit a frame.
  Mitigation: the same `drm_info` dump in task group 1 answers it, and the fix
  is small once it is not a mystery.
- **Pixman at 568x1232 on two C908s is too slow to be pleasant.** → This is the
  risk with no mitigation and no prior art; nobody has published a number for
  pixman composite throughput on this core. It is measured in task group 4 and
  recorded whatever it says. If it is bad, the answer is fewer surfaces — a
  direct DRM/KMS Dozer shell with no compositor — not more GL.
- **sway's built-in touch auto-mapping does not fire**, because the GT9895's
  udev `ID_PATH` does not start with `platform-`. → Touch works but lands in
  the wrong place. Caught by the explicit `map_to_output`, and visible in
  `swaymsg -t get_inputs`.
- **The build is longer than estimated.** 89 derivations includes `librsvg`
  with vendored Rust crates and the GTK 3 tail behind `mako`. → Mitigation:
  the cage smoke test at 68 derivations comes first and answers the risky
  question cheaply; and `mako` and `bemenu` are separable, worth 19
  derivations, if the shell needs to land sooner.
- **Adding a compositor undoes the closure minimality
  `system/nixos-config` requires.** → It does, and knowingly. The measured
  delta is committed so the increase is a recorded decision rather than drift.

## Open Questions

- Which on-screen keyboard: `wvkbd` (layer-shell, what SXMO uses) or
  `squeekboard` (also packaged). Both cross-compile at the pin. This changes a
  task's contents, not the approach, and is answerable once there is a screen
  to look at one on.
- Whether `foot` or the kernel console remains the thing on screen at boot.
  Answerable after task group 3 and it does not affect the specs.
