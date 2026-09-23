## 1. Contract and fixtures
- [ ] 1.1 Add shared state IDs/copy keys and visible recovery mapping without moving video/card lifecycle ownership. Verify with `python3 tests/test_launcher_navigation.py && python3 tests/test_window_catalog.py && python3 tests/test_video_session.py`.
- [ ] 1.2 Add fixture cases for Home disclosure, loading, empty, stale, failed launch, denied action, Stop, EOF, and cancelled paths; assert no raw path/secret is rendered. Verify with the same three host tests.
## 2. Runtime and physical acceptance
- [ ] 2.1 Build changed narrow userspace derivations after builder coordination. Verify with `nix build .#touch-launcher`.
- [ ] 2.2 Capture real-finger Home and recovery/error readability after the image is deployed: `python3 tools/capture-feature.py recovery-routes --provenance real-touch --duration 30 --description 'Visible Home and recovery routes' --output-dir docs/evidence/recovery-routes`. Keep board evidence separate from host state fixtures.
