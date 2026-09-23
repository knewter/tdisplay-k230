# Diagnostic client isolation prerequisite on the board

On 2026-09-23 the coordinator ran the committed
`tests/vglite/check_root_trial_credentials.py --user shell` as root through the
reserved board console, using the installed Python 3.14.7. The source was
`141b6aa`, integrated as `5628a18`; its companion
`tools/vglite-root-scene-trial.py` was copied alongside it under `/run`. The
transfer's MD5 matched on the board. Installed system and boot ID are recorded
in `docs/evidence/final-shell-image/installed-status.txt`.

[Actual test output](result.txt) reports success. The transient system-manager
client ran as UID 1000, GID 995, with `NoNewPrivs=1` and zero effective
capabilities. Actual socket peer credentials matched. It connected to the
shared Unix socket but was denied access to root-private IPC, a regular-file
GPU fixture and the root test process's held fixture descriptor through
`/proc`. The client exited zero; its runtime was 747ms. The final cleanup's
unit-not-loaded message follows `--collect` removing the already-completed
transient unit and was not a test failure.

This test opened **no DRM or VG-Lite device**, launched no compositor and did
not stop the normal shell. `shell` and `seatd` remained active afterwards.
It closes only the diagnostic harness's real multi-UID credential prerequisite,
which the unprivileged development host could not exercise. Actual GPU access,
GPU rendering/cache correctness, panel output, diagnostic-session restoration,
and normal-service compositor-only access remain **UNVERIFIED**.
