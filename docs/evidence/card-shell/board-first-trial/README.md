# First product card trial: acceptance remains open

Physical board, 2026-09-23, completed at 15:48:24 UTC. Source package
`935e02155cac7374de10b5db6e642d9479c500b3` (landed as `f514478`),
`/nix/store/ii5g7635wldnk7jsrfp18ism634w5y70-k230-card-shell`.
Session/acceptance tools: `14a60a9`. Temporary non-root product session using
the installed normal configuration, DSI-1 568x1232, scale one, Pixman RGB565.
Input came from the distinctly named virtual touchscreen; no real-finger,
camera, optical latency, image integration, or polished UX claim follows.

## Reproduction and raw observations

Use the reserved-board procedure in
[`../../../research/card-shell-board-tools.md`](../../../research/card-shell-board-tools.md)
with the original tool revision and explicit `--inject-script` for this run.
The offline collector exports allowlisted data and verifies screenshot hashes.
`acceptance.json`, `manifest.json`, client logs and `telemetry.log` are retained
without upgrading statuses. Two preparation refusals are summarized in
`setup-refusals.json`; both restored the normal service before correction.

Ten assertions were observed: one-card parent/child liveness, the selected
card's liveness with two clients, native RGB565/Pixman, explicit close refusal,
separate timeout retaining the client, accepted close removing the other client,
Terminal, Windows/Home, keyboard content reservation, and restored focus.
Three failed: the neighboring client's liveness, upward throw close request,
and Monitor. The persistent Close button subsequently exercised refusal; it
does not rescue the failed throw assertion.

The coordinator inspected native captures. `private.png` and `unavailable.png`
hide the selected app content and replace its title. `two-live.png` exposes
only the neighboring card's border: its parent and child content are outside
the panel, so demanding callbacks there was an invalid visibility assumption.
`apps.png` still shows the previous app, while `monitor.png` shows the launcher:
the sequence did not consistently wait for launcher startup. These are retained
failed captures, not screenshots to advertise those routes as accepted.
`during-drag.png` does not establish movement merely because of its filename.
The refusing floating fixture also obscures most of the newly focused Terminal;
the keyboard and System Back captures do not visually demonstrate their named
outcomes. IPC focus/workspace changes alone do not establish those visual gates.
The repeat explicitly terminates only the verified synthetic refusing client
after its close test, before exercising normal controls.

## Timing rejection and corrections

The unchanged parser rejects the raw telemetry with **input precedes session
start** (exit 2; `benchmark-rejection.txt`). The producer emitted its session
timestamp on card entry, 3.925 and 4.333 microseconds after the first input's
timestamp. The correction uses the existing monotonic benchmark-arm timestamp
as session start, while still recording card count when the deck becomes active.
A host test compiles the actual producer and exercises input-before-phase order.
Historical telemetry is not rewritten to manufacture a passing budget report.

Measured consecutive motion gaps in the old process-per-event injector were:

| Mapped clients | Minimum | Median | Maximum |
| --- | --- | --- | --- |
| 1 | 111.943 ms | 191.552 ms | 270.419 ms |
| 2 | 103.827 ms | 197.227 ms | 325.671 ms |

The requested 10 ms sleep was not the delivery cadence. The replacement writes
one native input-event packet per step in one process and uses absolute timing.
The repeat must measure actual delivery; requested timing is still not evidence.
The throw policy and all declared performance thresholds remain unchanged.
The revised two-client check holds both surfaces on-screen, and normal controls
receive startup settling time before the next action. None of these corrections
is a claim that a repeat has passed.

## Recovery and remaining gates

The product and input services stopped and the normal shell restarted.
A separate injected regression at 15:56 UTC passed normal services, Apps
Next/Previous, keyboard toggling while retaining Apps, Terminal, and Apps Back.
Installed image remained
`/nix/store/nz82q373yj1hp2k4qm85xa3c328jli8j-nixos-system-nixos-26.11.20260919.20b1ddd`;
boot ID remained `9407bae0-fe1a-4a05-8062-edbe8a110859`. `restoration.json` retains
the result. No flash or reboot occurred.

Product tasks 4.2 and 5.2 remain open. A corrected repeat needs complete
interaction evidence and a valid measured budget report; default image/QEMU
integration, physical gestures and optical review remain separate gates.

## Host checks for the corrections

`python3 tests/test_card_shell_board_tools.py`: 21 checks passed, including
native packet layout/contact release, failed writes and invalid coordinates.
`python3 tests/test_card_shell_telemetry.py`: actual producer entry-order test
passed. `python3 tools/card-shell-benchmark.py --self-test`: 18 parser checks
passed. Strict proposal validation, blob inventory and site build passed.
The corrected cross-build and repeat board acceptance were still pending when
this diagnostic record was landed. No task was marked complete by these checks.
