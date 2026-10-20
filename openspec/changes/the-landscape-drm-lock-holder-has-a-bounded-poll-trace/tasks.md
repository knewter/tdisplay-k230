## 1. Tooling

- [x] 1.1 Implement isolated selected-function capture, strict sanitized exports, interval qualification and negative fixtures. Host proof: `python3 tools/landscape-drm-holder.py --self-test`.

## 2. Board measurement

- [ ] 2.1 Qualify bounded idle poll smoke on the unchanged board. Hardware proof: protected SSH invocation of `python3 <probe-dir>/landscape-drm-holder.py --board-smoke --output <probe-dir>/smoke-a`; commit command, source identities, clock/loss checks and cleanup.
- [ ] 2.2 Run paired baseline/traced 24-drag workloads, at most one traced retry if no >100ms sample. Hardware proof: protected SSH invocation of `python3 <probe-dir>/landscape-drm-holder.py --board-run --source-revision 221bbcf34a276a939356e5a6af9bfb124af9896a --expected-system <pinned-j30-system> --expected-executable-sha256 9464072ac100e77500c7b6113920d2c2ed14e022612eddbc38a037ce9b006670 --smoke <probe-dir>/smoke-a --output <probe-dir>/trial-a`; retain actual exit status and rejected attempts.
- [ ] 2.3 Commit sanitized exports, source-grounded overlap report and instrumentation limits. Proof: `python3 tools/landscape-drm-holder.py --report docs/evidence/landscape-drm-holder/board/trial-a --output docs/evidence/landscape-drm-holder/board/report.json`, with strict stream/hash/clock/loss/864-input checks.
- [ ] 2.4 Verify normal board state and release reservation. Hardware proof: timestamped final protected-SSH query of owned instance/timer absence, unchanged global controls and runtime/output, Home, services, idle terminal and no injected devices.

## 3. Publication

- [ ] 3.1 Validate, land and push evidence; verify CI success and exact published workboard revision. Proof: `openspec validate the-landscape-drm-lock-holder-has-a-bounded-poll-trace --strict`, `python3 tools/blob-scan.py --no-vendor`, and committed CI/HTTP revision evidence. Archive only after all tasks pass.
