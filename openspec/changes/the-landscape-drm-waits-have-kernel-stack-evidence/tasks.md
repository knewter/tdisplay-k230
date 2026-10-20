## 1. Host tooling

- [x] 1.1 Implement isolated bounded stack triggers, safe symbol export, strict stack/syscall/scheduler/frame association and ownership cleanup. Test address/payload rejection, unresolved frames, lost/missing/ambiguous stack records, trigger ownership/exhaustion, clock/loss and gzip identity. Proof: `python3 tools/landscape-drm-wait.py --self-test`; commit log/source hashes under `docs/evidence/landscape-drm-wait/host/`.

## 2. Reserved-board diagnostic (no physical contact claim)

- [x] 2.1 Qualify stack capture on a harmless sleeping Python process on the installed kernel, with bounded trigger, matching mono markers, no loss, symbol-only public records and unchanged global tracing after independent cleanup. Proof on the board: `python3 tools/landscape-drm-wait.py --board-smoke --output <new-private-directory>`.
- [ ] 2.2 Capture one untraced and one stack-traced 24-drag direct-IPC workload on source221/j30, unchanged PID/DEBUG/ordinary Foot/1280×800 normal. Permit only one extra traced attempt if the first has no >100 ms sample. Proof on the board: `python3 tools/landscape-drm-wait.py --board-run --source-revision 221bbcf34a276a939356e5a6af9bfb124af9896a --expected-system /nix/store/j30yag05ic9k68n9dzbzindgf4ardp08-nixos-system-nixos-26.11.20260919.20b1ddd --expected-executable-sha256 9464072ac100e77500c7b6113920d2c2ed14e022612eddbc38a037ce9b006670 --smoke <qualified-smoke-directory> --output <new-private-trial-directory>`. Preserve all attempts/rejections; arm cleanup before kernel mutation.
- [ ] 2.3 Produce strict zero-loss/clock/coverage and stack-correlated report with tracing overhead, observed wait chains and explicit limits/candidate interpretation. Retain an inconclusive result when bounded capture does not identify a wait. Proof: `python3 tools/landscape-drm-wait.py --report <copied-safe-trial-directory> --output <report.json>`; commit safe records, hashes and commands.
- [ ] 2.4 Verify owned trigger/instance/timer removed, global controls unchanged, Home/benchmark stopped, normal landscape/source/system/DEBUG/services and no virtual devices; release the board after verified cleanup. Proof: timestamped controller cleanup/final-state records under the same board reservation; no image/physical/portrait claim.

## 3. Publication

- [ ] 3.1 Validate `openspec validate the-landscape-drm-waits-have-kernel-stack-evidence --strict`, commit proved tooling/evidence/inventory, push master and verify CI plus exact revision at `https://knewter.github.io/tdisplay-k230/work/`. Archive only with committed proof for all tasks; no capability/main-spec delta or performance/default fix is implied.
