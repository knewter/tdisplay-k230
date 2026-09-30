## 1. Publish the navigation scope

- [x] 1.1 Validate and land the proposal early on master. Proof: `openspec validate the-shell-is-navigable-with-a-mouse --strict`.

## 2. Complete the input routes

- [x] 2.1 Implement compositor pointer streams, clickable/tappable Home footer, screen-edge drags and centered-window expansion. Proof: `python3 -m unittest discover -s tests -p 'test_card_shell_pointer_navigation.py'` against the built compositor (headless injected input).
- [x] 2.2 Add bounded Rust shell axis handling and normal Sway four-finger outward binding. Proof: `cargo test --manifest-path nix/rust-shell-client/Cargo.toml --lib` and `cargo check --manifest-path nix/rust-shell-client/Cargo.toml --bin k230-shell-rust` (host only).
- [x] 2.3 Cross-build the actual HDMI system closure. Proof: `nix build .#nixosConfigurations.k230-coherent-shell-hdmi-trial.config.system.build.toplevel --no-link --print-out-paths --max-jobs 2 --cores 8`.

## 3. Navigation audit and deployment

- [x] 3.1 Exercise a pointer navigation matrix for app, overview, Home, drawer, shade, Settings, theme and Wi-Fi routes, including scrolling and keeping apps alive. Commit commands, objective outcomes, captures and remaining gaps under `docs/evidence/the-shell-is-navigable-with-a-mouse/`. Proof: `python3 tests/shell_pointer_navigation.py --help` followed by its recorded headless or reserved-board invocation. Evidence class must name injection versus real glass.
- [x] 3.2 Install the built closure on the reserved physical board and verify exact profile, active services and native captures. Proof: `./tools/console.py /dev/ttyACM0 --wait=3 "readlink /run/current-system; systemctl is-active shell shell-ui k230-touch-trackpad"`, plus recorded pointer interactions. No flash required.
- [ ] 3.3 Physical operator acceptance: tap Home in panel-touch mode, click/edge-drag in HDMI trackpad mode and four-finger inward/outward pinch. Record physical observation and photograph. Keep unchecked until actually performed.
- [ ] 3.4 Land tested source/evidence, push master and confirm exact site revision and media publication. Proof: recorded Pages run and published revision at `https://knewter.github.io/tdisplay-k230/work/`. Do not archive while physical gates remain open.
