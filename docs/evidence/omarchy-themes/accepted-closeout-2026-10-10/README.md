# Theme acceptance and retained-source recovery — 2026-10-10

At this acceptance checkpoint, the parent change was **22/25 complete**. The operator accepted implemented
behavior and waived further proof collection. Tasks 5.3b, static 5.4 and 5.5
now record that acceptance and disposition instead of claiming new physical
trials. Actual theme consumer implementation (3.1), complete compatibility
publication (6.1) and archive (6.2) remain open.

Worktree `/home/jadams/tmp/k230-theme-closeout-2026-10-10`, branch
`closeout/themes-2026-10-10`, base
`38d370c1a7989b982e04cfd74799542cccd3424e`. Owned paths: this parent's
planning artifacts, reboot trial and tests, theme closeout evidence, its board
checklist section and work-board entry. No board, serial port or build slot
was reserved. This changes the operator tool and acceptance records; the
runtime already implements the retained-cache policy, so no new firmware
build or board installation is needed for this correction.

## Acceptance and limits

The user's project-session reports include:

> it all worked land it

> continue but you dont have to gather that proof ive already confirmed its fine carry on it's all good

The [operator record](operator-report.json) preserves that authorization. It
is broad acceptance of implemented behavior, not a claim that each originally
requested experiment was run. The [superseded requests](superseded-verification.json)
preserve the exact previous tasks. The [previous publication plan](previous-publication-plan.json)
records why 6.1/6.2 were revised while remaining open. Existing
[dark/light board activation](../board-switching/README.md) and
[unchanged community activation](../community-board-fixed/README.md) retain
their original evidence classes.

| Previous collection request | Current disposition | Limits |
| --- | --- | --- |
| Real-finger dark/light/community selection and cancel recording | Implemented behavior accepted; additional collection waived | No new camera recording or per-class cancel observation; specific recordings UNVERIFIED |
| Static combined CPU/RSS, decode/presentation and card costs | Implemented static behavior accepted; additional workload and latency collection waived | No new board workload; unmeasured quantities UNVERIFIED; no numerical budget claim |
| Remembered theme/wallpaper, fresh-home and removed-source boot trial | Protocol corrected and host-checked; additional physical collection waived | No new physical boot, console/panel or full fresh-HOME trial; these individual results UNVERIFIED |

The waiver does not implement missing hover/focus or typography/spacing
consumers, and does not turn unavailable field classifications into full
compatibility. The [102-field inventory](../token-adaptation-inventory.md)
continues to identify these limits. Settings/notifications and additional
background fit modes/overlays/video remain in their existing named successors;
this closeout does not run or close those successor workloads.

## Corrected removed-source policy

Design decision 1 already requires retaining the last working generation
independently of its source clone. `theme_catalog.selected()` exposes no
source id when the clone is missing, while retaining its generation id.
The Rust startup receiver loads the valid selected snapshot before falling
back to the packaged default; the card receiver likewise loads valid active
state. The old boot scenario and reboot-v1 trial incorrectly required a
reset to default when only the clone disappeared.

The delta spec now distinguishes an empty fresh home from removal of a source
whose cached generation remains valid. The former uses the packaged default;
the latter retains its selected appearance and wallpaper. The trial's
unavailable-source arm now requires an absent fixture source and catalog
source id, the same catalog generation, and exact retained generation,
wallpaper fingerprint and preference-byte identity. It still restores the
entire normal state directory and fixture through acknowledged recovery on
completion or failure. Candidate/workload identity and distinct boot-id guards
are preserved.

New trials use `reboot-v2`. An old `reboot-v1` checkpoint is refused before
resume mutation because its acceptance policy differs, but remains recoverable
through the existing manual restoration path. The
[historical v1 procedure](../reboot-protocol/README.md) retains its prior
results; use its setup and recovery instructions with this corrected policy
for any future optional trial.

## Host validation

[Commands, timestamps and source hashes](host-checks.json) record:

- `python3 tests/test_handheld_theme_trial.py`: 25 passed. Covers retained
  generation success, unexpected default reset, removed-source wallpaper
  mutation, catalog generation mismatch, old-protocol refusal with recovery,
  boot/workload/candidate identity guards and complete restoration.
- `python3 tests/test_handheld_theme_rendering.py`: 7 passed. Existing token
  inventory and rendering checks; no new physical or complete consumer claim.
- `python3 tests/test_omarchy_theme_activation.py`: 14 passed. Existing real
  activation fixtures include selection and public paths surviving a removed
  clone; no physical boot is simulated into a claim.
- `openspec validate --all --strict`: all current items pass.
- `git diff --check`: passed.

The trial fixtures inject boot identities, transport and captures on the host.
Public reports remain bounded and exclude private paths/source names. Physical
observation and full fresh HOME remain explicitly UNVERIFIED. These checks
prove the operator protocol and restoration logic, not pixels on glass or
measured performance. The parent stays open for the actual source gaps.

## Publication consistency

The first live-site check found 18/21 on the work card, although OpenSpec
correctly counted 22/25: the site counts top-level checkboxes and four older
completed subtasks were indented. Those entries are now top-level with their
identifiers and scope unchanged, so both projections include all 25 tasks.
This formatting correction does not change implementation or test results.

## Subsequent consumer and archive closeout

The missing consumers were subsequently implemented and cross-built; the
[complete compatibility report](../compatibility-closeout-2026-10-10.md) and
[consumer record](../consumer-closeout-2026-10-10/README.md) record 497 passing
host cases, reviewed captures and exact-revision publication. The parent is now
archived at 25/25. This update does not change the operator statements or
original waived requests preserved here, and does not turn the new cross-build
into a claim of board installation or individual physical verification.
