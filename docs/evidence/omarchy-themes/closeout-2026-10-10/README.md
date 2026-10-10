# Theme closeout audit — 2026-10-10

The theme parent is 19/25 complete and remains open. [Actual host checks](host-checks.json)
record the named reboot-protocol suite (22 passed) and rendering suite
(7 passed), with logs, timestamps and source identity. This is host proof;
no board or build slot was reserved, and no physical result was obtained.

Worktree `/home/jadams/tmp/k230-theme-closeout-2026-10-10`, branch
`closeout/themes-2026-10-10`, base `645ea9162dba21096ca9a8fa28ba2a6aa22e7a77`.
Owned scope: this change's planning, closeout evidence, board checklist and
its work-board override; any later policy implementation stays in this branch.

## Remaining gates

| Task | What remains | Evidence needed |
| --- | --- | --- |
| 3.1 | Applicable hover/focus/border and typography/spacing consumer gaps identified in the 102-field inventory | Named rendering checks and reviewed production captures; unavailable classification alone is not completion |
| 5.3b | Real-finger dark/light/community theme selection and cancel | Camera video plus matching native captures; previous injected activation already passed separately |
| 5.4 | Static-background combined CPU/RSS, decode/presentation, card costs and restoration | Reserved-board `tools/handheld-theme-trial.py --workload backgrounds` with a pinned candidate/workload; exact preflight is in the trial operator procedure |
| 5.5 | Remembered theme/wallpaper, fresh-home default and unavailable-source boot/recovery | Policy decision, then reserved-board begin/reboot/resume procedure and reviewed glass; true fresh HOME remains distinct |
| 6.1/6.2 | Complete compatibility publication and archive | All implementation and physical gates above, followed by exact-revision CI/Pages |

The [reboot protocol](../reboot-protocol/README.md) exists and its host
checks pass. The design explicitly retains a generation independently of a
removed clone, but the spec's boot scenario and trial require the default.
Changing either policy requires resolving that contradiction; this audit
does not select an answer or reinterpret the failing arm as passing.

The already authorized 2026-09-28 scope split moved video, overlays and fit
modes into `the-background-chooser-supports-fill-solid-and-video`. Its task
3.3 preserves the full paired static/video workload, covered-video pause,
restoration and budget gate before animated defaults. The parent still owns
its static physical workload. The live parent task and board checklist now
reflect that ownership; historical audit notes remain historical.

No task checkbox or UNVERIFIED requirement was closed. The card performance
acceptance does not supply theme workload timings or waive these gates.
