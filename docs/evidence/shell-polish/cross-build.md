# Shell polish configuration cross-builds

Source revision: `376f08632152d03963bd47a86ae9b352e357d271`. This is the visual source change before the coordinator combines it with newer theme-picker damage/cache work. These are **host cross-build gates only**; this worker accessed no board or serial port. No installation, panel observation or real-glass gesture result is asserted.

The generic `.#handheld-shell-rust` output uses a different package graph from the running coherent image. These invocations instead use the exact coherent configuration package set. The reserved slot used one Nix job and four build cores.

```sh
# REPOSITORY_URL points at this repository's local Git checkout.
REPOSITORY_URL=git+file:///path/to/tdisplay-k230
nix build --impure --expr "let f=builtins.getFlake \"$REPOSITORY_URL?rev=376f08632152d03963bd47a86ae9b352e357d271\"; p=f.nixosConfigurations.k230-coherent-shell.pkgs; in p.callPackage (f.outPath + \"/nix/rust-shell-client\") {}" \
  --no-link --print-out-paths --max-jobs 1 --cores 4
nix build --impure --expr "let f=builtins.getFlake \"$REPOSITORY_URL?rev=376f08632152d03963bd47a86ae9b352e357d271\"; p=f.nixosConfigurations.k230-coherent-shell.pkgs; in p.callPackage (f.outPath + \"/nix/card-shell.nix\") { swayUnwrapped=p.sway-unwrapped; }" \
  --no-link --print-out-paths --max-jobs 1 --cores 4
```

## Rust client

Successful build finished 2026-10-01 by 17:52:52 UTC. Derivation `/nix/store/2fr3mx476v4qc4526qwvgynlpch16cb6-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0.drv` produced:

`/nix/store/rqqmzkwnj45xvrm84cd7hzmdjylnw46v-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0`

`file` identifies ELF64 RISC-V, RVC and the double-float ABI with the configured glibc lp64d loader. `nix path-info -Sh` reports a 124.2 MiB runtime closure. The built binary's `RUNPATH` uses the following configuration-derived references; no host loader/library substitution was made:

```text
/nix/store/syg6xw4x296w82267qnvrd3nn0cp6j31-glibc-riscv64-unknown-linux-gnu-2.42-84
/nix/store/dx7ljr01359zlgn8n5an7x4hp1gz43n1-glib-riscv64-unknown-linux-gnu-2.88.3
/nix/store/rf3qfj0avdldwajfmd85ds4mhk45b1mi-cairo-riscv64-unknown-linux-gnu-1.18.4
/nix/store/smihzglwj1w9kw5f8yqvmamxvzv0rrx1-pango-riscv64-unknown-linux-gnu-1.57.1
/nix/store/wssz267qail8ngf0w7lx4alq0lkgl66s-riscv64-unknown-linux-gnu-gcc-15.3.0-lib
/nix/store/64d5qg2v2jhd2p4bjj961x9k9cs0i17b-librsvg-riscv64-unknown-linux-gnu-2.62.3
/nix/store/xwb2a8bjiawhsc15qvhwm75mzscimw7h-libxkbcommon-riscv64-unknown-linux-gnu-1.13.2
```

## Compositor

Successful build finished 2026-10-01 by 17:56:48 UTC. It produced:

`/nix/store/gp9gv2nh0zf4bgryk8qp4dbprnfycya2-k230-card-shell`

The underlying source-built Sway output is `/nix/store/g7xzwwvr3x05mlmsab5jn5kn1sl41wjb-sway-unwrapped-riscv64-unknown-linux-gnu-1.12`. Its `bin/sway` is ELF64 RISC-V, RVC and the double-float ABI with the same configured glibc loader. `nix path-info -Sh` reports a 195.2 MiB runtime closure for the card-shell output.

The raw successful build outputs are preserved as [Rust build log](rust-cross-build.txt) and [compositor build log](card-cross-build.txt). They record only source-derived derivation/store paths and success, with no runtime configuration.

## Remaining gate

The coordinator must build the combined latest source, install the paired artifacts on the reserved board, capture native Home/drawer/overview/Settings/shade/theme-picker images in dark and light appearances, and record real glass and mouse navigation. After installing the combined reviewed outputs, a concrete operator inspection is `./tools/console.py /dev/ttyACM0 --wait=3 "pgrep -a k230-shell-rust; pgrep -a sway"`; native captures must be collected in the shell user's active Wayland session with `grim` and matched to the recorded source/build identity. Use `python3 tools/capture-feature.py shell-polish-dark --output-dir docs/evidence/shell-polish/physical --provenance real-touch --duration 30 --description "Real-glass dark theme Home, drawer, overview, Settings, shade and theme picker review"` for camera evidence, repeating for the light appearance. Inspection/camera commands alone do not prove that the named gestures occurred; record the actual observed gestures and limits. Task 6.4 remains unchecked. Host PNGs and cross-built binaries do not establish physical contrast, motion cadence, focus, gestures or deployment.
