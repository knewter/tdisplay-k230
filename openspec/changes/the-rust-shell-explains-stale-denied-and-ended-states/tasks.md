## 1. Contract and host tests
- [x] 1.1 Add shared state IDs/copy keys and recovery mapping for loading, empty, stale, denied action, video Stop, EOF, cancelled in `nix/rust-shell-client`, without moving video/card lifecycle ownership. Host proof: `cargo test --manifest-path nix/rust-shell-client/Cargo.toml`.
- [x] 1.2 Add test cases for each state asserting the named recovery action and that no raw path, GLib text, or secret is rendered. Host proof: `cargo test --manifest-path nix/rust-shell-client/Cargo.toml`.
- [ ] 1.3 Render the video Stop, end-of-file and cancelled copy from `recovery::RecoveryState::{VideoStopped, VideoEnded, VideoCancelled}` on a surface the person sees when `nix/video-session.py` playback stops, ends or is cancelled. Today the terminal window closes and nothing is shown. Choose the owner first: the session keeps its window open with the copy, or the shell observes the session's end. Host proof: a test asserting each end reason produces its state's copy and action.
## 2. Build
- [x] 2.1 Build the client after builder coordination. Build proof (not board proof): `nix build .#handheld-shell-rust`.
## 3. Physical acceptance
- [ ] 3.1 Capture real-finger recovery/error readability after the image is deployed: `python3 tools/capture-feature.py recovery-routes --provenance real-touch --duration 30 --description 'Recovery routes for stale, denied, and ended states' --output-dir docs/evidence/recovery-routes`. Hardware proof; keep separate from host fixtures. Stays open until this capture exists.
