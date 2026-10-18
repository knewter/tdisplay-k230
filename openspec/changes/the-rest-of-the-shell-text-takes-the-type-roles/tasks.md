## 1. Home

- [ ] 1.1 Home app and folder labels in the Caption role, with cells sized to
  hold them at each step and persisted layouts reflowed. Verify with `cargo
  test --offline --manifest-path nix/rust-shell-client/Cargo.toml --tests`
  (updating `home-*.png` baselines deliberately). Host class.
- [ ] 1.2 Battery and Weather widget captions on the Caption role with its
  floor at a Home-sized cell. Host renders at four steps in both
  orientations. Host class.

## 2. The rest of the shell

- [ ] 2.1 The Shade's audio stream and output rows and the notification
  source line on the roles. Host class.
- [ ] 2.2 The Wi-Fi pages, the Help page, the theme grid and the recovery
  menu on the roles. Host class.

## 3. Board

- [ ] 3.1 Native `grim` captures of Home, a folder, the Shade with audio
  streams, Wi-Fi and Help at 100% and 200% on the landscape panel. Board
  class.
- [ ] 3.2 The operator's look on glass. Board class; stays open until the
  operator has looked.
