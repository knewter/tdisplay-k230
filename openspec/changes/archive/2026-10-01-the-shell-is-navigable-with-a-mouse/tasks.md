## 1. Publish the navigation scope

- [x] 1.1 Validate and land the proposal early on master. Proof: `openspec validate the-shell-is-navigable-with-a-mouse --strict`.

## 2. Complete the input routes

- [x] 2.1 Implement compositor pointer streams, clickable/tappable Home footer, screen-edge drags and centered-window expansion. Proof: `python3 -m unittest discover -s tests -p 'test_card_shell_pointer_navigation.py'` against the built compositor (headless injected input).
- [x] 2.2 Add bounded Rust shell axis handling and normal Sway four-finger outward binding. Proof: `cargo test --manifest-path nix/rust-shell-client/Cargo.toml --lib` and `cargo check --manifest-path nix/rust-shell-client/Cargo.toml --bin k230-shell-rust` (host only).
- [x] 2.3 Cross-build the actual HDMI system closure. Proof: `nix build .#nixosConfigurations.k230-coherent-shell-hdmi-trial.config.system.build.toplevel --no-link --print-out-paths --max-jobs 2 --cores 8`.

## 3. Navigation audit and deployment

- [x] 3.1 Exercise a pointer navigation matrix for app, overview, Home, drawer, shade, Settings, theme and Wi-Fi routes, including scrolling and keeping apps alive. Commit commands, objective outcomes, captures and remaining gaps under `docs/evidence/the-shell-is-navigable-with-a-mouse/`. Proof: `python3 tests/shell_pointer_navigation.py --help` followed by its recorded headless or reserved-board invocation. Evidence class must name injection versus real glass.
- [x] 3.2 Install the built closure on the reserved physical board and verify exact profile, active services and native captures. Proof: `./tools/console.py /dev/ttyACM0 --wait=3 "readlink /run/current-system; systemctl is-active shell shell-ui k230-touch-trackpad"`, plus recorded pointer interactions. No flash required.
- [x] 3.3 Record the operator's 2026-10-01 mouse-navigation acceptance. Prior actual-board/headless pointer matrix remains committed. Additional photographs and exhaustive gesture rechecks are waived; this does not claim an individually observed four-finger pinch sequence.

- [x] 3.4 Land tested source/evidence, push master and confirm exact site revision and media publication. Proof: recorded Pages run and published revision at `https://knewter.github.io/tdisplay-k230/work/`. Do not archive while physical gates remain open.

## 4. Panel acceptance navigation and edge-tap corrections

- [x] 4.1 Implement Home handle tap/click to overview and defer shell edge ownership until tap/drag intent is known, preserving ordinary drawer activation. Proof: `python3 -m unittest discover -s tests -p 'test_card_shell_pointer_navigation.py'` and the recorded actual-compositor native-touch edge regression (including compact-keyboard pairing), plus the matching full HDMI system cross-build. Host injection is not physical proof.
- [x] 4.2 Deploy the matching userspace closure on the reserved board; simulate header and drawer-search Backspace taps through native touch dispatch, verify Home → overview retains window IDs, and record exact system/executable identities. Preserve gestures and recovery. No flash/kernel/DT change.
- [x] 4.3 Record the earlier real-finger acceptance of the edge-tap/Search correction and Home handle, plus current mouse-navigation acceptance. Retain installed-board edge-control evidence. No additional photograph or repeated glass test is required.

- [x] 4.4 Validate, land source/evidence, push master and inspect exact publication. Keep task 3.3's HDMI recognition/photograph gate open until performed.

Task 4.1 exact cross-build and headless input proof: `docs/evidence/the-shell-is-navigable-with-a-mouse/edge-controls-host/README.md`. Fixture protocol checks are distinct from task 4.2 actual-board key semantics and task 4.3 real-glass acceptance.

Task 4.2 installed board identity and native uinput header/Backspace/Home checks: `docs/evidence/the-shell-is-navigable-with-a-mouse/edge-controls-board/README.md`. Real-glass 4.3 remains open.

Task 4.4 successful exact-revision Pages build/deploy and published revision check: `docs/evidence/the-shell-is-navigable-with-a-mouse/edge-controls-board/publication.json`. Physical tasks 3.3 and 4.3 remain open.

## Accepted closeout, 2026-10-01

The updated completed tasks describe actual acceptance, waivers and scope
transfer, not execution of the superseded protocols. See `docs/evidence/proposal-closeout/2026-10-01/mouse.md`.
Historical checkpoint notes above that say physical gates remain open are
superseded by this record. Quantitative or individually unreported results
are not promoted to physical proof.

Proof: `openspec validate the-shell-is-navigable-with-a-mouse --strict`; committed operator report;
`python3 scripts/render_work_board.py --working-tree --output <snapshot.json>`.
