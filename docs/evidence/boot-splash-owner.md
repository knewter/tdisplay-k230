# Plymouth cost audit

This is the laptop-side audit for `the-screen-lights-before-linux` task 5.1.
It evaluates the pinned nixpkgs and the current shell configuration without
enabling Plymouth in `nix/hardware.nix` and without building a package.

The design budget is no more than the shell's measured **89 local riscv64
derivations / 875 MiB fetched-unpacked** delta. The comparison method is the
one in `docs/display-environment-options.md`: evaluate the complete k230
system with the existing shell enabled, then run `nix build --dry-run` against
the candidate system. The baseline `nix build --dry-run .#toplevel` produced
no output on this host because its paths are already present.

The reproducible candidate expression is
`tools/k230-plymouth-eval.nix`. It composes the same `k230.nix`,
`hardware.nix`, and `shell.nix` modules as the flake, then enables Plymouth
with the built-in `spinner` theme. `spinner` is the minimal theme baseline:
it is supplied by the Plymouth package itself and needs no extra theme
package. Commands used from the repository root:

```text
nix eval --impure --expr 'import ./tools/k230-plymouth-eval.nix'
nix build --dry-run --impure --expr 'import ./tools/k230-plymouth-eval.nix'
```

The initial evaluation (before the helper was narrowed to `spinner`) produced
`/nix/store/x4jjd44s91yrhnx40rjy9l7w9vcz85az-nixos-system-nixos-26.11.20260919.20b1ddd.drv`.
After the native media work changed the warm store, the exact committed
helper was rerun at **2026-09-22T18:08:06Z**. It produced
`/nix/store/yxclgzsb8v2qhg34mz4ldlzak86pdb9k-nixos-system-nixos-26.11.20260919.20b1ddd.drv`.
That rerun's dry-run summary was:

```text
76 derivations will be built
83 paths will be fetched
481.5 MiB download
897.3 MiB unpacked
```

The counts are unchanged between those two evaluations; only the toplevel
derivation path changed. The 76 derivations include the riscv64 Plymouth build and its generated initrd
units, plugins, themes, fonts, and transitive closure. The 83 fetched paths
are mostly development inputs and image/font libraries. These figures are
incremental against the warm store used by the shell measurement; they are not
a from-scratch closure.

Applying the written rule to the required metric: **Plymouth is over the
recorded budget by 22.3 MiB and should take the minimal DRM splash fallback.**
The 76-derivation count is within 89, but the fetched-unpacked figure is the
binding comparison and 897.3 MiB is greater than 875 MiB. This is a dry-run
budget verdict; it does not claim a final installed closure size.

The final closure byte count remains unknown because `nix build --dry-run`
reports fetched unpacked sizes, not the output sizes of derivations that would
be built. That uncertainty does not change the dry-run verdict, since the
design rule explicitly budgets the fetched-unpacked metric.

The pinned NixOS module supports the requested integration. With the current
configuration it evaluates to `boot.initrd.systemd.enable = true`, theme
`spinner`, the default `plymouth-riscv64-unknown-linux-gnu-26.134.222` package,
and no extra theme package. The module places `plymouthd`, its renderer and
theme files, fonts, and systemd units in the initrd, starts Plymouth from
`initrd-switch-root.target`/`sysinit.target`, and provides the corresponding
quit/switch-root units. That establishes a supported integration path; it does
not prove that this panel's early DRM device is available or that the splash
hands off without a dark frame.

No image, kernel, hardware, or Wi-Fi state was changed. Task 5.2 should not be
started under the design rule; task 5.3 is the documented fallback and task
5.4 remains a hardware claim.

## Task 5.3 implementation boundary

The selected fallback is a small libdrm owner in the main system. It opens the
primary node, enables universal-plane enumeration, finds a connected connector,
preferred mode, CRTC, and matching primary plane, then creates a dumb buffer.
The source asset is immutable
`logo.xrgb` in the Nix store. The K230 primary plane does not advertise XR24,
so the default path converts its B,G,R,X bytes to RG16; AR24 is available only
when the discovered primary plane advertises it. There is no animation because
this program only bridges the static stage-1 frame until the shell begins.

On shell handoff the owner drops DRM master on `SIGUSR1` but retains its file
descriptor and framebuffer. It polls the CRTC until a non-zero successor
framebuffer replaces its own, then removes only that replaced framebuffer and
its dumb allocation, without issuing a CRTC clear. Until a successor appears
it retains the active objects; service stop is the only other exit path. This
arrangement avoids treating close-time framebuffer lifetime as a handoff
mechanism. It still does **not** prove that the panel
will remain lit: DRM object lifetime after file release and Sway's first
modeset are driver-dependent. Task 5.4 must film the transition before any
continuity claim is made. The service is present only when both
`k230.panelConsole` is false and the shell is enabled; the daily no-logo
console image keeps its current path. A shell restart accepts an already
dropped master or an inactive optional owner, since neither can retain DRM
master, but refuses to start after its bounded wait if an active owner never
reaches `scanout`.


The splash-enabled toplevel build passed on 2026-09-22 with
`k230.panelConsole = false`:
`/nix/store/m39vc96iaw7s5vlyxmlxa9a027kkizag-nixos-system-nixos-26.11.20260919.20b1ddd`.
[Build and installed unit evidence](splash-owner-build.txt) records the exact
command, the built unit, its immutable program, and the shell's release hook.
Task 5.3's build claim is complete; physical handoff task 5.4 remains open.
