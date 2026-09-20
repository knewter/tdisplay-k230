# Tasks

Every proving command below is a **QEMU or build-host claim**. None of them say
anything about the board — QEMU's `k230` machine models no panel, no touch, no
radio and no SD layout.

## 1. The host can cross-compile riscv64 at all

- [x] 1.1 Pin nixpkgs in a `flake.nix` and cross-build one trivial package to prove the toolchain resolves. Verify with `nix build --no-link .#checks.x86_64-linux.cross-hello` and record the store path
- [x] 1.2 Measure and record what a cross-build costs on this host, so a long first build is recognisable as normal. Verify by committing the measured wall-clock time to `docs/evidence/cross-build.txt`

## 2. A minimal riscv64 NixOS closure

- [x] 2.1 Declare a `nixosConfigurations.k230` with `buildPlatform = x86_64-linux` and `hostPlatform = riscv64-linux`, a serial console at 115200 8N1, and no graphical stack. Verify with `nix eval .#nixosConfigurations.k230.config.system.build.toplevel.drvPath`
- [ ] 2.2 Build the closure. Verify with `nix build .#nixosConfigurations.k230.config.system.build.toplevel`
- [ ] 2.3 Record every derivation that refused to cross-compile and had to be emulated, with what it cost. Verify by committing that list to `docs/evidence/cross-build.txt`; if the list is empty, say so explicitly

## 3. It boots under QEMU

- [ ] 3.1 Add `tools/qemu-k230.sh` that boots the built system under `qemu-system-riscv64 -machine k230` with the console on stdio. Verify by running it and reaching a prompt
- [ ] 3.2 Capture the full boot to a committed transcript. Verify with `./tools/qemu-k230.sh | tee docs/evidence/qemu-boot.txt` and confirm the transcript ends at an interactive prompt

## 4. The stage-1 seam is real

- [ ] 4.1 Declare stage 1 as a vendored input in the flake with nothing building U-Boot or OpenSBI, and comment why. Verify with `nix eval` showing the vendored attribute exists, and `grep -riE 'u-?boot|opensbi' nix/ flake.nix` showing no derivation compiles either
- [ ] 4.2 Ground `system/nixos-config`'s stage-1 requirement against the committed QEMU transcript and the flake, and resolve or restate the `UNVERIFIED` markers in both delta specs. Verify with `openspec validate a-riscv-nixos-closure-cross-builds`
