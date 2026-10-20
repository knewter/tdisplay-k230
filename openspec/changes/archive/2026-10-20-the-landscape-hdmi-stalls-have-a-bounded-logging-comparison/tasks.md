## 1. Tooling and guards (host proof)

- [x] 1.1 Implement the bounded trial/restore protocol and strict A/B/B/A report. Test unknown/unsafe ExecStart arguments, owned-file conflicts, restoration on failure, missing frame coverage, mixed runtime/config/geometry, incorrect actual logging flags, and workload/order mismatch. Proof: `python3 tools/landscape-hdmi-logging.py --self-test`; retain command output and hashes under `docs/evidence/landscape-hdmi-logging/host/`.

## 2. Logging comparison (physical-board diagnostic; no glass claim)

- [x] 2.1 Reserve the board and run four one-Foot workloads on the exact installed source, with DEBUG/INFO/INFO/DEBUG logging, 30 s settling after each restart, and 24 direct-IPC drags per run. Arm independent restoration before any override. Proof on board: `python3 tools/landscape-hdmi-logging.py --board-run --source-revision 221bbcf34a276a939356e5a6af9bfb124af9896a --expected-system /nix/store/j30yag05ic9k68n9dzbzindgf4ardp08-nixos-system-nixos-26.11.20260919.20b1ddd --expected-executable-sha256 9464072ac100e77500c7b6113920d2c2ed14e022612eddbc38a037ce9b006670 --output <new-private-trial-directory>`; commit only allowlisted logs and safe context, preserving any failures.
- [x] 2.2 Produce the strict report and measured conclusion, including per-run p95/p99/max, over-100 ms samples, dispatch/submission/presentation boundaries, log volume and limitations. Proof: `python3 tools/landscape-hdmi-logging.py --report <copied-trial-directory> --output <report.json>`. If stalls remain at INFO, record their boundary and the remaining profiling question without claiming a renderer fix or causality from absent evidence.
- [x] 2.3 Restore original logging/service, normal Home, original 1280×800 normal output and persistent system; verify both services, no owned drop-in/timer, no virtual test devices and expected startup Foot. Proof: the tool's `restore.json` and final cleanup check under the same board lease. Stop the restore timer only after successful restoration; retain diagnostic/recovery limits.

## 3. Publication

- [x] 3.1 Run `openspec validate the-landscape-hdmi-stalls-have-a-bounded-logging-comparison --strict`, commit proved source/evidence and push master; verify CI and exact revision at `https://knewter.github.io/tdisplay-k230/work/`. Archive only after all above proof is committed. No main-spec delta or portrait acceptance is implied.

Evidence: `docs/evidence/landscape-hdmi-logging/README.md`. DEBUG reduction did not eliminate the stalls; no default or renderer change is justified by this comparison alone.
