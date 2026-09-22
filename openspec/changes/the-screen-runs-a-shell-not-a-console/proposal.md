## Why

After `the-screen-comes-up-under-linux` the panel is lit and the kernel console
is on it. A person holding the board can read boot messages and, if they have a
serial cable, type. What they cannot do is touch anything. There is no window,
no keyboard, nothing to press — the screen is an output device and the touch
panel emits events nobody listens to.

That is the gap between a board that displays and a board you can use. Dozer is
a Crux application with swappable shells, and nothing can be a shell here until
something owns the screen, owns the touch events, and can put a second
application on top of the first.

The prerequisite `the-screen-comes-up-under-linux` is now archived and supplies
the DRM, panel, and touch interfaces this change consumes. The shell remains a
hardware-facing change: first-light, physical touch accuracy, and unattended
boot still require the board and are tracked in this change's tasks and
evidence.

## What Changes

- **A Wayland compositor runs on the panel, rendering entirely on the CPU.**
  There is no GPU driver for the K230's 2.5D block, so this is not a matter of
  choosing a fast compositor and accepting slow frames — it decides which
  compositors can start at all. wlroots has a Pixman software renderer and a
  DRM dumb-buffer allocator, so it needs neither Mesa nor a render node.
- **An on-screen keyboard, so the board is usable with no cable.**
  `the-screen-comes-up-under-linux` removed the need for a serial cable to
  *read*. This removes it to *type*.
- **Touch drives the shell, not just the input subsystem.** A touch already
  producing `evtest` output is not a touch that activates a button. That is a
  separate claim and it gets separate evidence.
- **The cable-free session has practical touch controls.** A persistent,
  finger-sized bar exposes Apps, Windows/Home, Keyboard, and System. Its
  launcher can start or return to the terminal and a system monitor; System
  makes reboot and power-off deliberate two-tap operations with Cancel. This
  is the small SXMO-inspired part that fits this board, without adopting SXMO.
- **Hyprland is ruled out, in writing, with the measurement behind it.**
  Josh named it first and it is the wrong tool here; recording why costs one
  paragraph and saves the next person the same week.
- **The build cost is treated as a requirement, not a footnote.** Every package
  this change adds is compiled for riscv64. `docs/display-environment-options.md`
  measures each candidate; the chosen stack has a number and the number is part
  of what gets proven.

**Non-goals.**

- **Any GPU or GL path, including Mesa's `llvmpipe`.** Software GL would cost
  2.4 GiB of Mesa and LLVM to produce the slowest option available. If Pixman
  turns out to be too slow, that is a finding to record, not a reason to reach
  for llvmpipe inside this change.
- **Dozer itself or AtomVM.** This change
  delivers the surface a shell sits on. What sits on it is still deliberately
  undecided, and this change must not decide it. A terminal and system monitor
  are session utilities, not a choice of Dozer application shell.
- **Adopting SXMO as a distribution.** Its Wayland variant is sway underneath,
  which this change gives us anyway; packaging its shell scripts is its own
  proposal if anyone still wants it afterwards.
- **A display manager, greeter, multi-user login, or session management beyond
  starting one compositor at boot.** One user, one seat, one screen.
- **Rotation, scaling, fractional DPI, or animations.** The panel is portrait
  and the compositor will use it portrait.
- **Power management, suspend, or idle blanking.** Worth having; not here. The
  confirmed reboot and power-off controls are session escape hatches, not
  power policy.

**Needs the physical board.** QEMU's `k230` machine models no display pipeline,
so no claim about a compositor on this panel can be proven under emulation. One
part *can* proceed without hardware: whether the stack cross-compiles at all,
and what it costs, is a build-host claim and is separated into its own task
group so it can be answered while the board is in pieces.

## Capabilities

### New Capabilities

- `runtime/shell`: what owns the screen and the touch panel once the system is
  up — the compositor, how it renders without a GPU, how a person types, and
  what a touch actually does.

### Modified Capabilities

None. `display/panel` and `display/touch` are introduced by
`the-screen-comes-up-under-linux` and this change consumes them without
changing their requirements: it needs a framebuffer at 568x1232 and touch
events in panel coordinates, which is exactly what they already promise.

## Impact

Adds a NixOS module under `nix/` for the compositor stack and its session, and
the packages it needs to the system closure. It also carries the small kernel
configuration required by the existing NixOS firewall backend; it does not
change the device tree or display/touch drivers.

**Build cost, measured on `solomon` against the pinned nixpkgs, including the
touch-menu utilities** (`docs/evidence/shell-build.txt`): the final enabled
closure is 1,280,679,016 bytes (1221.0 MiB), a +110.2 MiB / +95-path delta
against the 1109.9 MiB baseline. The complete build sequence took 2705 seconds
(45 minutes) and built about 235 derivations across its resumed stages. The
final menu increment, including `htop`, `jq`, `gnused`, `grim`, and regenerated
image/configuration paths, added 22 derivations and 8.0 MiB unpacked. These are
build-host measurements; they do not establish runtime performance.

The original candidate comparison remains useful as a historical estimate,
but the measured final closure and build sequence above are the claim for this
change (`docs/display-environment-options.md`):

| stack | riscv64 derivations to build | to fetch (unpacked) |
| --- | ---: | ---: |
| `cage` + `foot` + `wvkbd` (smoke test) | 68 | 292 MiB |
| `sway` + `foot` + `wvkbd` (the shell) | 89 | 875 MiB |
| `hyprland` + `foot` (rejected) | 184 | 2.2 GiB |

Disabling Xwayland is worth 55 of those derivations on its own and removes GTK
3, CUPS and Avahi from the closure. This change takes that override, which means
no X11 application can ever run on this board without revisiting the decision.

No new toolchain. The sway stack builds on the GCC 15.3.0 cross-compiler the
closure already uses; Hyprland would have required a second full GCC
cross-bootstrap, which is a large part of why it is rejected.

**Consumes the interfaces from `the-screen-comes-up-under-linux`.** That change
is archived, but the board-facing dependency remains: without a DRM device that
supports dumb buffers, the compositor has nothing to allocate from, and without
touch events it has nothing to route.
