## 1. Host implementation and build

- [ ] 1.1 Implement the read-only native status helper and narrow wrapper routing; compare its capability output with the unchanged Python oracle, including fresh successive reads, malformed/missing data, rounding, permission/unavailable states and keyboard failure/deadline cleanup. Host proof: `python3 -m unittest tests.test_settings_status tests.test_device_settings` plus strict compiler warnings. Commit source and results under `docs/evidence/shade-status/host/`.
- [ ] 1.2 Cross-build the installed wrapper/helper and matching landscape system, recording derivation/source/output hashes and unchanged kernel/compositor/Rust identities. Build proof under the existing build lock: `nix build .#handheld-settings` then `nix build .#nixosConfigurations.k230-mainline-drm-shell-landscape-hdmi.config.system.build.toplevel`. Host build is not deployment proof.

## 2. Board qualification

- [ ] 2.1 Acquire board lease; record current/booted/persistent systems, protected boot/rollback identities, root capacity and owned disposable-file review. Establish adequate safe deployment space before transfer. Hardware proof: timestamped protected-SSH preflight with `statvfs`, scoped ownership/hash/backup checks and exact cleanup/transfer commands; do not delete unrelated files or run broad GC. Leave this task open if storage prevents safe deployment.
- [ ] 2.2 Qualify the matching userspace candidate with same UI/kernel/output/recorder and bounded three-pull before/after workload; verify native helper cost/identity, fresh external brightness/state and unchanged safe action behavior. Commit exact commands, timing results/all tails/losses/observer limits and restored normal controls under `docs/evidence/shade-status/board/`. Hardware software/injected evidence over protected SSH; not glass/optical proof.
- [ ] 2.3 Obtain the operator's real top-drawer pulls on the candidate and record the exact acceptance/correction without inferring unperformed timing. Physical proof: timestamped operator report tied to the matching installed candidate; host or injected results do not pass it.
- [ ] 2.4 Promote accepted userspace persistently, verify ordinary startup and exact installed wrapper/helper/system with unchanged kernel/compositor/Rust/landscape, clean only owned copied temporary files and release reservations. Hardware proof: committed exact promotion/startup command and final protected-SSH identity/control/rollback/capacity query.

## 3. Publication

- [ ] 3.1 Commit named proof, validate `openspec validate the-notification-shade-reads-settings-without-cold-starts --strict`, run `python3 tools/blob-scan.py --no-vendor`, land/push and inspect successful matching CI/exact Pages. Archive with no main-spec edits only after all seven tasks pass; keep other jank/portrait tasks open.
