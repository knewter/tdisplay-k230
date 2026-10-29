## 1. Design check (board, read-only)

- [ ] 1.1 Settle the privileged path and persistence. Record on the board
  whether `timedatectl` and polkit are present, what `/etc/localtime` points
  at, and whether `timedatectl set-timezone` fails with the current
  configuration. Then update design.md's Decisions. Proof (board, read-only):
  the console transcript under `docs/evidence/time-zone/board/`.

## 2. Host

- [ ] 2.1 Implement the Nix change and the privileged path chosen in 1.1.
  Proof (host build):
  `nix build .#nixosConfigurations.k230-mainline-drm-shell-landscape-hdmi.config.system.build.toplevel`.
- [ ] 2.2 Add the zone list and the network-time switch to the Date & time
  page. Proof (host): `cargo test --offline --lib` in `nix/rust-shell-client`,
  and renders at 100% and 200% under `docs/evidence/time-zone/host/`.

## 3. Board (hardware-only)

- [ ] 3.1 Test-activate the build. Change the zone and network time with
  injected touch, and record `timedatectl` and a grim capture. Then run
  `switch-to-configuration test` and reboot, and record both again. Confirm
  that the shell user cannot set anything else through the path. Proof
  (board, injected): `docs/evidence/time-zone/board/`.
- [ ] 3.2 Glass: the operator changes the zone and reads the clocks. Physical
  proof: a timestamped operator report tied to the installed build.

## 4. Closeout

- [ ] 4.1 Archive once 3.2 is done. Proof:
  `openspec validate settings-sets-the-time-zone-and-network-time --strict`.
