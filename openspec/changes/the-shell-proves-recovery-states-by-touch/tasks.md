## 1. Touch entry to the window list
- [ ] 1.1 Choose and implement a touch route to `AppMenu` that does not conflict with the drawer's long-press drag to Home. Record the rejected alternatives in `design.md`. Host proof: `cargo test --manifest-path nix/rust-shell-client/Cargo.toml`.
## 2. Build
- [ ] 2.1 Build after builder coordination. Build proof (not board proof): `nix build .#handheld-shell-rust`.
## 3. Physical acceptance
- [ ] 3.1 (moved from `the-rust-shell-explains-stale-denied-and-ended-states` 3.1) After deployment, capture real-finger recovery/error readability: `python3 tools/capture-feature.py recovery-routes --provenance real-touch --duration 30 --description 'Recovery routes for stale, denied, and ended states' --output-dir docs/evidence/recovery-routes`. The capture covers the empty and stale window list, the denied Settings action, and video stopped and cancelled. Serial-triggered setup (closing a window, refusing brightness writes, stopping the video session) is recorded as such. Hardware proof; stays open until the capture exists.
