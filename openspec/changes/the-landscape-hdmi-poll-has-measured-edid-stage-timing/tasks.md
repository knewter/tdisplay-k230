## 1. Probe tooling

- [x] 1.1 Implement bounded isolated function-only capture, privacy/schema/clock/loss/ownership guards and source-defined EDID stages. Host proof: `python3 tools/landscape-hdmi-detect.py --self-test`.

## 2. Hardware observation

- [x] 2.1 Qualify harmless 50ms controller-sleep smoke with source/kernel/system and cleanup records. Hardware proof: protected SSH `python3 <probe-dir>/landscape-hdmi-detect.py --board-smoke --output <probe-dir>/smoke-a`.
- [ ] 2.2 Record exactly one 35s idle observation on pinned source221/j30/DEBUG/landscape, requiring >=3 complete EDID stage intervals. Hardware proof: protected SSH `python3 <probe-dir>/landscape-hdmi-detect.py --board-run --smoke <probe-dir>/smoke-a --expected-system <pinned-j30-system> --expected-executable-sha256 9464072ac100e77500c7b6113920d2c2ed14e022612eddbc38a037ce9b006670 --output <probe-dir>/trial-a`; preserve command, exit status and rejections.
- [ ] 2.3 Commit sanitized records, source grounding and stage report with entry-boundary/instrumentation limits. Proof: `python3 tools/landscape-hdmi-detect.py --report docs/evidence/landscape-hdmi-detect/board/trial-a --output docs/evidence/landscape-hdmi-detect/board/report.json`.
- [ ] 2.4 Verify owned instance/timer removal, unchanged root controls/options/filter hashes and runtime/output, active services, idle terminal and no virtual inputs; release board. Hardware proof: timestamped protected-SSH final-state query committed with its command.

## 3. Publication

- [ ] 3.1 Validate, land, push, verify CI/exact workboard revision and commit publication proof before archive. Proof: `openspec validate the-landscape-hdmi-poll-has-measured-edid-stage-timing --strict`, `python3 tools/blob-scan.py --no-vendor`, and CI/HTTP revision evidence. No delta/main specs changes.
