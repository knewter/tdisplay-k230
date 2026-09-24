# Normal-service isolation checker: host preparation

This is source and host-fixture preparation for OpenSpec task 2.5. The checker
has **not** run on the board, and the task remains open. The opt-in service
is not activated by this commit. The privileged runner and broker contracts
are described in [the normal-service trial README](README.md) and
[`docs/research/vglite-service-access.md`](../../research/vglite-service-access.md).

`tools/vglite-service-isolation-check.py` runs only as root inside an observed,
token-matched trial. The runner now accepts an immutable store copy via
`--isolation-checker` and an optional `--restart-once`. It calls the checker
first for the original MainPID, then stops and starts `shell.service` under
the runner's existing restoration lock and token. It requires the old PID to
exit, observes a new exact Sway MainPID, and calls the checker again. Its
deadline remains tied to the original watchdog arm; it does not start another
service controller or extend the independent recovery timer. If the watchdog
restores the ordinary Pixman shell during either checker or between stop and
start, the phase guard prevents a stale activation or result write. Reports
are root-only and failure reports preserve only a fixed error type, not raw
journal text or paths.

The checker covers the following concrete parts of the
[access contract](../../research/vglite-service-access.md):

| Contract item | This checker observes | Limit |
| --- | --- | --- |
| MainPID authorization | `shell.service` MainPID, exact unwrapped executable, all four shell UIDs, zero effective caps, PPid 1, no tracer, root-owned `/proc/<pid>/fd`, Yama 1–3, one matching device fd | Requires a real trial process; host fixtures are not proof |
| Same-UID isolation | Fresh shell-UID, no-new-privileges child sends `VG1` to the broker and requires EOF/no descriptor; direct device open, compositor proc-fd duplication, and `PTRACE_SEIZE` each require permission denial | A missing broker/socket/device is a failure, not a denial |
| App launch inheritance | Uses Sway IPC `exec --` to launch the committed checker as an app child; verifies socket peer UID, ancestry to MainPID, zero caps, no device fd and no named `/dev/vg_lite` mapping after exec | **Pre-exec child fd/mapping state remains UNVERIFIED.** Anonymous vendor mappings cannot be classified from a postexec path scan alone |
| Restart grant | Requires initial broker grant only to initial MainPID and, after coordinated restart, exactly one grant each to old and new MainPID plus denial entries; old PID must have exited | Does not prove scene pixels or force-Pixman control |

The pre-exec gap needs a separate reviewed diagnostic design. One bounded
option is an opt-in compositor launch-path audit hook that records fd and
mapping state after its existing `pthread_atfork` child handler but before
`execve`, using only a fixed event protocol to a root collector. It must not
open `/dev/vg_lite`, add a broker exception, or grant ordinary children GPU
access. The alternative is a separately reviewed, bounded fork/exec tracer
with guaranteed detach before the watchdog deadline. Neither is implemented
or claimed here. Repeated GPU scene, forced-Pixman fallback, recovery and
physical board evidence remain separate task 2.5 gates.

After reviewing the source and importing the opt-in compositor closure, the
reserved board operator stages the **committed** checker and runner as
root-owned files, then adds the checker to the Nix store. Use a new output
directory and the same reviewed `--wrapper`, `--unwrapped`, `--broker`,
`--python` and `--config` values from [the trial README](README.md):

```sh
checker=$(nix-store --add /var/lib/k230/vglite-service-tools/vglite-service-isolation-check.py)
/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3 \
  /var/lib/k230/vglite-service-tools/vglite-normal-service-trial.py \
  --output /var/lib/k230/vglite-service-trial-isolation-1 \
  --wrapper <reviewed-wrapper-store-file> \
  --unwrapped <reviewed-unwrapped-sway-store-file> \
  --broker <reviewed-broker-store-file> \
  --python <reviewed-python-store-file> \
  --config <reviewed-normal-sway-config-store-file> \
  --isolation-checker "$checker" --restart-once --seconds 120
```

The placeholders deliberately require the current candidate identities;
the historical paths in the earlier README are not evidence that those
outputs are installed. The operator verifies the staged source hash against
the reviewed commit before running, captures the private serial/controller
log and `state.json` plus both `isolation-*.json` files after restoration,
then checks the ordinary Pixman shell and seatd. Run the separate
`--force-pixman` and scene trials with fresh outputs; no checker result
substitutes for them. The runner's own `--restore` entry point and timer own
recovery if any check fails.

Host command performed here:

```sh
python3 tests/vglite/test_service_isolation_check.py &&
python3 tests/vglite/test_normal_service_trial.py &&
openspec validate the-shell-trials-vglite-composition --strict
```

The checker suite exercised broker grant cardinality, denial aggregation,
Sway-child IPC fixture, and stale trial tokens. The runner suite exercised
successful fake restart and watchdog interruptions during checker execution
and between service stop/start. These are host fixtures; no physical denial,
GPU mapping, broker grant or restoration is established by them.
