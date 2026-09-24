# Minimal Qt Quick probe: host prebuild checkpoint

Observed 2026-09-23 at source `3d3d915fc57fffd0c328a70ebdb2b9b7e6512665`
plus the opt-in source checkpoint in this worktree. This is evaluation of the
target derivation, not a successful cross-build or board observation.

```text
qmlformat nix/qtquick-software-probe/Probe.qml    PASS host parser
qmllint nix/qtquick-software-probe/Probe.qml      PASS host parser
nix eval --impure --raw --expr 'let f = builtins.getFlake (toString ./.); p = f.inputs.nixpkgs.legacyPackages.x86_64-linux.pkgsCross.riscv64; in (p.callPackage ./nix/qtquick-software-probe/default.nix {}).drvPath'
  PASS target derivation evaluation
nix build --dry-run --no-link --impure --expr 'let f = builtins.getFlake (toString ./.); p = f.inputs.nixpkgs.legacyPackages.x86_64-linux.pkgsCross.riscv64; in p.callPackage ./nix/qtquick-software-probe/default.nix {}'
  PASS evaluation only; 40 derivations would build at this checkpoint
```

Pinned nixpkgs currently resolves Qt 6.11.2. The dry-run includes Qt SVG,
ShaderTools, XCB and Vulkan-loader dependencies despite the probe's requested
software path and its Base/Declarative/Wayland direct inputs. Their presence
does not prove a GPU context is required or used. The actual output, unique
closure bytes, configure/QV4/cache mode, build duration, runtime buffer path,
input behavior and cost are all still unmeasured. Task 1.1 remains open until
the narrow real build and evidence complete.
