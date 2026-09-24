# Bounded normal-service VG-Lite broker trial preparation

Task 2.5 remains **UNVERIFIED on the board**. This checkpoint adds a root-only
operator runner for the already source-built opt-in compositor and broker. It
does not activate the NixOS option, alter `/dev/vg_lite` permissions, flash an
image, or change the Pixman default. The normal-service access design is in
`docs/research/vglite-service-access.md`.

The runner verifies the normal `shell` and `seatd` units and the expected
configuration, refuses an existing broker or runtime unit, then copies itself
to a new root-only evidence directory. It arms an independent root systemd
recovery timer **before** installing any runtime unit. Three token-marked
files in `/run/systemd/system` create the private socket, the restricted root
broker and an override of `shell.service`. The service keeps its normal
systemd user, working directory, seatd dependency, configuration and controls;
only its executable and renderer/broker environment change. The MainPID must
resolve to the exact opt-in unwrapped Sway binary. Recovery stops the trial
shell and broker, removes only units carrying the token, reloads systemd,
starts normal `shell.service`, and checks that the original ExecStart identity
and seatd are restored. A stale timer token cannot remove another trial's
units. The trial duration is 30–180 seconds, with recovery at duration + 30.
Every runtime unit write, service call and state update checks the live token
and phase under the recovery lock. Recovery closes the phase before changing
services, so a watchdog firing mid-install or just before compositor start
cannot be followed by a stale activation or state update.

The root-only `state.json` preserves UTC start/restore times, boot ID, normal
system path, original command, source/store paths and SHA256 for runner,
broker, wrapper, compositor and config. It also records observed MainPID,
Yama scope, `/proc/<pid>/fd` owner, broker grants to that PID, GPU full-frame
count and Pixman replay count. No unrestricted journal is exported. The
fixed-schema values are observations, not proof of client isolation or pixel
correctness by themselves.

## Operator command after review and closure import

The board coordinator owns the board lock and stages the **committed** runner
and broker source, plus the opt-in compositor closure. The following command
uses the previously host-built service wrapper/unwrapped Sway identities from
`docs/evidence/vglite-service-access-host.md` and the normal configuration
recorded in the card-shell board evidence. Confirm every path is installed and
that the source hashes match the reviewed commit before using it. Each run
requires a fresh output suffix; the runner refuses reuse.

```sh
broker=$(nix-store --add /var/lib/k230/vglite-service-tools/broker.py)
/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3 \
  /var/lib/k230/vglite-service-tools/vglite-normal-service-trial.py \
  --output /var/lib/k230/vglite-service-trial-gpu-1 \
  --wrapper /nix/store/3rgdggbm2qds0g7x16zh9yyb4yshs1xd-sway/bin/sway \
  --unwrapped /nix/store/bn4kknllz69447c1m2w4lgd2xa4dkplk-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --broker "$broker" \
  --python /nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3 \
  --config /nix/store/7amq3c8lnlvg82la2g4zxhiik716fgq9-k230-sway.conf \
  --seconds 90
```

For a same-allocation forced-Pixman control, repeat with a fresh output
`...-pixman-1` and append `--force-pixman`. It keeps `WLR_RENDERER=vglite`
and sets `K230_VGLITE_ALLOW_UNPROVEN_CACHE=0`, matching the earlier scene
diagnostics. These commands are **pending**; no board execution is claimed.
The earlier wrapper store paths were not present in this host workspace at
preparation time, so the operator must import and verify them before running.

The source and fake-system lifecycle proof is:

```sh
python3 tests/vglite/test_normal_service_trial.py
python3 tests/vglite/test_broker.py
openspec validate the-shell-trials-vglite-composition --strict
./tools/blob-scan.py --no-vendor
```

The new lifecycle suite passed 10/10 checks; existing broker policy tests passed
7/7. Strict OpenSpec validation, blob scan and Python compilation also passed
on the host. The lifecycle suite executes the watchdog's actual `--restore`
entry point against a fake system manager, including partial setup failure,
foreign-unit refusal and Pixman restoration. It does not model driver behavior
or systemd credentials on the board. The suite also injects watchdog recovery
between unit writes and before compositor start to check closure of stale work.

For task 2.5 to close, the reserved operator must additionally retain the
normal-service broker grant/denial checks, direct device/proc-fd/ptrace denial
for another `shell` process, pre/post-exec fd and mapping checks for a
Sway-launched app, repeated GPU and forced-Pixman scene output, shell restart
with a grant only to the new MainPID, and failure/restoration evidence listed
in `docs/research/vglite-service-access.md`. A root scene diagnostic or the
runner's aggregate counters cannot substitute for those checks.
