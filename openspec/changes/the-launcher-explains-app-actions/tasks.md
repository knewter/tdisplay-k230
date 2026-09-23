## 1. Catalog policy and host behavior
- [ ] 1.1 Define the curated ID/action policy in the launcher/catalog source; retain GLib discovery/launch and built-ins. Verify with `python3 tests/test_desktop_catalog.py`.
- [ ] 1.2 Add host fixtures for endpoint suppression/demotion, unknown entry retention, refresh, page bounds, and failed-launch Back recovery. Verify with `python3 tests/test_launcher_navigation.py && python3 tests/test_desktop_catalog.py`.
## 2. Image and physical acceptance
- [ ] 2.1 Build the launcher only after builder coordination. Verify with `nix build .#touch-launcher`.
- [ ] 2.2 On the board, capture real-finger Apps discovery and a failed launch with no raw path text using `python3 tools/capture-feature.py launcher-curation --provenance real-touch --duration 30 --description 'Curated Apps catalog and recovery' --output-dir docs/evidence/launcher-curation`; inspect target geometry/readability before marking complete.
