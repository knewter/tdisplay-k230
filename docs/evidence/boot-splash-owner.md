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
