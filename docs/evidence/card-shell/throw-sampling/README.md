# Preserve throw velocity across repeated millisecond timestamps

The policy previously set velocity to zero whenever two consecutive motion
events had the same millisecond timestamp. A valid upward movement followed
by another movement or a duplicate endpoint in that timestamp then failed to
request close. This is independently reproduced in the actual C policy and
the cross-built compositor's native wlroots input path.

The policy now measures those samples from the preceding distinct timestamp.
Coordinates still update on every event. A same-time downward reversal resets
the velocity reference conservatively, and motion with no elapsed interval
cannot throw. A later stationary sample, slow drag and held release continue
to reject close. The 120-pixel displacement, 0.4-pixel/ms speed and 150-ms
release-age thresholds are unchanged, as are dispatch-time close deadlines,
graceful close/refusal behavior and performance budgets.

## Host and native runtime proof

```sh
python3 tests/test_card_shell_state.py
TMPDIR=/mnt/MediaVolume/home/jadams nix build .#card-shell \
  --max-jobs 1 --cores 8 --no-link --print-out-paths
python3 tests/card_shell_runtime.py --native-touch --delayed-touch \
  --sway /nix/store/d7pxj3jviq5ghax97hy98fnqlmhbiy0f-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --client /nix/store/6nskh3ldk3ya7mwxbb258qszrxhw2i61-card-composition-probe-client-0.1/bin/card-composition-probe-client \
  --output NEW_HEADLESS_DIRECTORY
```

All 23 compiled policy cases pass with address/undefined-behavior sanitizers.
Two new case groups cover duplicate and advancing same-time endpoints, a
zero-duration whole movement, same-time reversal, a later stationary sample,
slow movement and held release. The new positive group fails with the original
policy from base `4ba9f58a`; its other 22 cases pass.

`build.json` identifies the built package and source hashes. `headless.json`
records 17 compositor runtime checks and eight independent source-timing
checks, including repeated-timestamp close and reversal/held-release rejection.
This executes the RISC-V compositor under QEMU user emulation with native
Wayland clients and wlroots/cursor/seat routing, not a full Linux guest.

For the runtime negative control, substitute the previous timestamp-corrected
Sway `/nix/store/bggwbi2nx72c494xpjvgyi98yxz3w3c0-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`
in the same command. It passes the preceding timing checks, then fails waiting
for the first same-millisecond motion close request. `negative-control.json`
records that expected exit 1 and the exact runtime-test hash.

## Remaining physical gate

This does not establish the cause of the four intermittent upward-throw misses
in the [RVV comparison](../kernel-rvv/card-cost/README.md). Its input injector's
absolute scheduling deadlines can produce bursts after a delay, but those runs
did not retain the individual gesture source timestamps needed for attribution.
Three unchanged injected board workload repeats now observe all thirteen
interaction checks apiece; see the physical report below.
Real-finger acceptance, default-image integration and all failed card cost
budgets remain open. The normal image has not changed.


## Three physical-board repeats

`board/result.json` records three unchanged `card-shell-acceptance.py` runs on
normal system `gnr36q…`, using published fix revision
`33962837dd8a6dfc20d2ee944f321d45808b11df` and package `mp0bqh…` from `build.json`.
All **39/39 interaction checks were OBSERVED**, including each upward-throw
request, refusal, timeout, accepted close and normal-control route. Each run
verified the running Sway executable and restored normal shell/seatd. These
are injected-input observations, not reviewed new pictures or physical fingers.

The root-only bounded runner is committed as `run-board.py`. Stage it beside
exactly the three published session, acceptance and budget tools; their hashes
are in the board result. The actual command, within a transient root service
with a 1,800-second outer deadline, was:

```sh
python3 /var/lib/k230/card-throw-tools-33962837/run-board.py \
  --board --revision 33962837dd8a6dfc20d2ee944f321d45808b11df \
  --output /var/lib/k230/card-throw-sampling-33962837
```

Each session had the independent root watchdog, a 540-second compositor limit,
and a 480-second acceptance timeout. The three runs retain the same normal
kernel, panel, Pixman renderer, configuration, client, 24 drags per card count,
and existing benchmark producer. `transfer.json` records SHA256 verification
of the 23 named text files; raw process logs and native pictures were excluded.

All six workload budgets still **FAIL**. All reports were reconstructed exactly
from committed telemetry, excluding only the newly generated report timestamp.
`comparison.json` preserves the per-run summary without a speedup claim.

| Repeat | Cards | Frames | Frame CPU p95 / max ms | Tracking p95 ms |
| --- | ---: | ---: | ---: | ---: |
| 1 | 1 | 144 | 16.574 / 49.312 | 57.475 |
| 1 | 2 | 139 | 23.663 / 25.896 | 57.474 |
| 2 | 1 | 138 | 16.511 / 49.612 | 57.478 |
| 2 | 2 | 143 | 23.726 / 25.411 | 57.478 |
| 3 | 1 | 142 | 16.309 / 48.920 | 57.477 |
| 3 | 2 | 150 | 23.843 / 26.934 | 57.478 |

The unchanged CPU limits are p95 16.667 ms / max 33.334 ms; tracking p95 is
33.334 ms. Frame CPU and tracking fail in every workload; the other declared
input/release/memory metrics pass. Reproduce each complete report with:

```sh
python3 tools/card-shell-benchmark.py --board \
  --input docs/evidence/card-shell/throw-sampling/board/run-1/public/telemetry.log \
  --manifest docs/evidence/card-shell/throw-sampling/board/run-1/public/manifest.json \
  --output /tmp/card-throw-repeat-1-budget.json
```

Exit 1 is expected for the retained budget failure; repeat for runs 2 and 3.
`normal-restoration.json` and its serial record independently check the normal
system, shell, seatd, Wi-Fi HTTPS, protected boot/firmware hashes and root layout.
Its `repeat` phase compares against the committed storage baseline; **no reboot
or flash occurred during this trial**, and its boot ID matches the three runs.

Three successful injected repeats support this fix but are not a reliability
estimate or a matched before/after board attribution. The previous failures
remain committed. Card tasks 4.2, 5.1 and 5.3 stay open: repaint/cadence cost,
default-image integration and focused real-finger acceptance still need proof.
