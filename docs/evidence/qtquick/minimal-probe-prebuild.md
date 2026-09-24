# Minimal Qt Quick probe: interrupted cross-build checkpoint

Observed 2026-09-23 at source `3d3d915fc57fffd0c328a70ebdb2b9b7e6512665`
plus the opt-in source checkpoint in this worktree. This records source
evaluation and a deliberately interrupted target build, not a successful
probe cross-build or board observation.

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
does not prove a GPU context is required or used.

The exact command
`nix build .#qtquick-software-probe --max-jobs 1 --cores 4 --no-link --print-out-paths`
started at about 2026-09-23 22:36:35 -0500 against target derivation
`/nix/store/x6gpkh020snxwwvfz4fb6bwyzgdh1b5x-qtquick-software-probe-riscv64-unknown-linux-gnu-0.1.drv`.
After about 18 minutes, the coordinator prioritized goal-critical card and
Rust builds. At 22:55:10 -0500 this task sent SIGINT to **only its own Nix
client process** at a dependency boundary. The client exited and logged
`error: interrupted by the user`; this is **INTERRUPTED**, not a failed Qt
compile. The private full log is `/tmp/k230-qtquick-probe-build.log`.

The first dry-run listed 40 target derivations. A fresh dry-run after the
interrupt listed 12 remaining, so 28 are already satisfied in the local
store. The remainder includes the interrupted psqlODBC dependency and Qt Base,
ShaderTools, QML Language Server, SVG, Declarative, Wayland, QML plugin wrapper,
and the probe itself. No target Qt library or probe output has built yet.
Completed dependency outputs are retained by Nix; the exact command can
resume without a source change after the sole build slot is free.

The pinned Qt Declarative 6.11.2 source archive
`/nix/store/wv7whhmb9kmmjh0hcf10bl1w3vkmzvmv-qtdeclarative-everywhere-src-6.11.2.tar.xz`
has `src/qml/configure.cmake` JIT conditions only for i386, x86_64, ARM and
ARM64. That predicts QML JIT OFF on riscv64, but no target configure summary
has been produced. Actual output and unique closure bytes, target QV4/cache
mode, runtime buffer path, input behavior and cost are unmeasured. Task 1.1
remains open until the narrow real build and evidence complete.
