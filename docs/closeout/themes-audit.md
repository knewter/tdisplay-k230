# Closeout audit: theme swap performance and Omarchy theme loading

2026-09-28. Codex, the prior owner of both changes below, is away for the
week; this audit picks the work up per `AGENTS.md`'s "Close OpenSpec changes
deliberately." Every task below was checked against the actual code, the
actual test suites (run on this host today unless noted), committed
`docs/evidence/**`, git history and the archived changes list. The detailed
citation for each ticked or annotated task lives in the change's own
`tasks.md` under a `Closeout audit (2026-09-28)` note; this document is the
index into those notes, not a replacement for them.

**Neither change is archived by this audit.** Both still have real open
work: reserved-board proof for landed code, host-doable work not yet
written, and genuinely unimplemented scope. Ticking a task here always means
a citation to a real, already-existing test run or board record exists —
nothing was run and marked passing that had not actually passed.

## Classification key

- **(a) done** — code and evidence of the task's own named class already
  exist; ticked in `tasks.md` with a citation.
- **(b) superseded** — a later, user-approved or better-evidenced decision
  replaced this task's premise; marked as such with a citation.
- **(c) host-doable** — no board needed; either done this session, or
  identified precisely and left open because implementing it responsibly
  (new Rust behavior, a new profiling tool) did not fit this audit's own
  budget. Never faked.
- **(d) needs the board (or a real finger)** — code is ready; only a
  physical run is missing. The companion checklist file has the exact
  command.
- **(e) unimplemented scope** — a real feature gap, not a bookkeeping gap.
  Recommended for a successor proposal; not archived away silently.

---

## `the-shell-swaps-themes-without-a-python-stall`

Before this audit: 57 done / 17 open. After: **60 done / 14 open** (7.8,
8.6, 9.5 ticked with citations below; nothing else changed state).

| Task | Class | Citation / next step |
| --- | --- | --- |
| 7.8 (instrumentation for the 7.6(b) latency gap) | (a) done | `nix/rust-shell-client/src/main.rs` lines ~1600-1749 already emit `ms=` on every `optimistic-apply skipped/shown` line; task group 8's own grounding comment quotes the resulting board run (`optimistic-apply shown ms=222.7`). Ticked in `tasks.md` 7.8. |
| 8.6 (board re-check of pre-render) | (a) done (target unmet, recheck itself is the deliverable) | Task group 9's own grounding comment is this recheck (`c6f0237a`/`vq6vkvqz…`): `prerendered=false`, root-caused and fixed by task 9. Ticked per the same convention as 7.4/7.6 (a run that reports a real, negative result is not "not run"). |
| 9.5 (board re-check of footer/status split) | (a) done (target unmet, recheck itself is the deliverable) | Task group 10's own grounding comment is this recheck (`644cd061`/`n44hk9js…`): 161ms vs ~30ms target, double-prerender still present — exactly what motivated task 10's redesign. Ticked on the same convention. |
| 2.3 (board jank capture, before/after `theme-helper.service`) | (d) board | `tools/theme-swap-jank.py --self-test`/`tools/analyze-theme-swap-jank.py --self-test` both pass host-side; the board run itself was never done. See checklist. |
| 3.3b (defer Foot recolour like 3.3a) | (c) host-doable, not attempted | `tools/app_appearance.py`'s OSC recolour is folded into `theme_transaction.py`'s synchronous return contract; the task's own text explains why touching that contract was judged too risky for its own budget. Still open, still safe to leave open — its cost is small and already scoped (opt-in, Foot-session-only). |
| 3.4 (re-run tap-to-visible metric) | (d) board | Depends on 3.3b or can be run to show the partial win from 3.3a alone. See checklist. |
| 6.6 (board re-check: Apply <150ms, `warm=2`) | (d) board | No grounding comment anywhere cites this specific recheck; genuinely not run. See checklist. |
| 10.6b (run the rewritten QEMU harness to a PASS) | (c) host-doable (QEMU, not board), attempted and blocked this session | `.#card-shell` and `.#touch-launcher` build from cache instantly; `nixosConfigurations.k230-coherent-shell.pkgs.sway-unwrapped`/`.#handheld-shell-rust` did not resolve from cache and a bounded (120s) attempt was killed rather than run an uncached, multi-hour riscv64 cross-build unattended in an audit session, per this repo's own single-build-slot convention. Not a code regression; same class of contention `10.6b`'s own note already describes. Re-attempt with a reserved build slot and no timeout. |
| 10.7 (board re-check of tap-to-apply flow, panel fit) | (d) board | Needs dark/light panel observation plus `optimistic-apply stage adopt_ms=...` timing. See checklist. |
| 11.3 (board swipe-cost/memory comparison) | (d) board | `--lib theme_picker`/`--lib theme_thumbnails`/`theme_prerender` all pass host-side; the board comparison itself was never run. See checklist. |
| 13.1 (matched-content profiling harness, `tools/theme-picker-profile.py`) | (c)/(e) substantial, unimplemented | Neither `tools/theme-picker-profile.py` nor `tests/test_theme_picker_profile.py` exist. This is a real new tool (fixtures, identity/PID/generation guards, capture format), not a small fix; not attempted this session given its size relative to this audit's budget. Left open, correctly classified as host-doable in the existing change (no successor proposal needed — it is already scoped here). |
| 13.2 (opt-in cost attribution on top of 13.1) | (c) substantial, unimplemented | Depends on 13.1. Same reasoning. |
| 13.3 (gate speculative neighbour-warm admission during motion) | (c) precisely identified, unimplemented | Read `nix/rust-shell-client/src/theme_ui.rs::poll_prepare_ahead` (lines ~566-624): when `centered` is `None` (mid-drag/coast/settle) the function correctly skips the *dwell-driven* warm-up, but falls straight through to draining `pending_neighbor_warms` regardless of motion state — the neighbour queue is **not** gated on rest the way task 13.3 asks. This is a narrow, well-scoped fix (thread the same "at rest" signal task 3.2/6.5 already compute through to the neighbour-drain branch) but was not made this session, to avoid shipping an unverified behavior change to picker input handling under audit time pressure with no board re-check available. Recommended as the next concrete step here. |
| 13.4 (board comparison of 13.1-13.3) | (d) board | Blocked on 13.1-13.3 landing first. |
| 14.4 (operator real-finger acceptance of finger-tracking) | (d) real finger | Code (14.1-14.3) is done and board-trialled with injected input; only human glass acceptance is missing. See checklist. |
| 15.2 (compositor-stage CPU profile) | (d) board, partially done | 697 CPU-clock samples already captured and reviewed (`docs/evidence/theme-picker/cpu-profile/README.md`); 648 of those samples have unknown callers, and compositor render/commit/present spans plus scheduler correlation are still missing. Needs another board run with better symbolization, not fresh design. |
| 15.3 (board runtime-trace publication) | (d) board | `tests.test_runtime_trace*`/`--lib theme_picker` pass host-side; only one physical capture exists so far (`docs/evidence/theme-picker/runtime-trace/README.md`) and it doesn't yet cover a second interaction as required. |

## `the-shell-loads-omarchy-themes`

Before this audit: 7 done / 17 open. After: **14 done / 11 open** (2.1, 2.2,
2.3, 3.4, 5.1, 5.2, 5.3a ticked; task 5.3 was split into 5.3a/5.3b, which is
why the open count does not simply drop by the number of new ticks). All
ticks below are backed by test runs performed today on this host
(`python3 -m unittest ...`), not assumed from reading code.

| Task | Class | Citation / next step |
| --- | --- | --- |
| 2.1 (compatible `omarchy-theme-set` coordinator) | (a) done | `tools/omarchy-theme-set` → `tools/theme_activate.py`. `python3 -m unittest tests.test_omarchy_theme_activation`: 14/14 pass, covering clone preservation, legacy scratch conversion, path boundaries, unknown-key reporting. Built under the sibling change's task groups 1-6 but never credited here until now. |
| 2.2 (bridge payloads / two-phase transaction) | (a) done | `tools/theme_transaction.py`. `python3 -m unittest tests.test_omarchy_theme_transaction`: 26/26 pass, covering generation ordering, concurrent swaps, failed ack, rollback, update invalidation, source removal. Also exercised live on the board (`docs/evidence/theme-picker/background-selection/README.md`, `.../store-relocation/README.md`, `.../finger-tracking/README.md`). |
| 2.3 (pinned default / fresh-home / persistent selection under `handheld-theme-service`) | (c) mostly done, naming gap | The pinned default (`handheld-theme-default`), the daemon (`theme-helper.service`) and persistent selection (`theme_preferences.py`) all exist and are exercised by the suites above, but no `handheld-theme-service` flake output exists to build, and fresh-home startup has no dedicated test. Left open: rename the proof command to the real outputs, add a fresh-home host test. |
| 3.1 (token consumer / coverage inventory) | (c) partial | Gradient stops/alpha/per-side-widths/references are covered (`tests/test_handheld_theme_rendering.py`, 4/4 pass). Missing: a stated field-coverage inventory, control-state (hover/pressed/disabled) adaptation, font/spacing adaptation, and any reviewed host captures. Host-doable; not attempted this session. |
| 3.2 (drawer/card chrome + icon theme) | (c) partial | `nix/card-shell/appearance.c` already reads/forwards `icon_theme`. No `--surface drawer-card` test flag exists, no dark/light reviewed captures exist. Host-doable; not attempted. |
| 3.3 (Settings/notifications/chooser/keyboard) | (b)+(e) split | Keyboard is done (3.3.k, ticked). Chooser is thoroughly themed already (task group 4/10 of the sibling change). Settings/notifications are real packages, not mockups, but have no verified theme wiring and no `--surface system` test. **Split into the successor proposal `the-settings-and-notifications-surfaces-are-themed`** (drafted this session, validates clean — see below). Parent task 3.3 left open and cross-references the successor; not ticked, since closing 3.3 against the successor needs your authorization. |
| 3.4 (Foot/app appearance adapters) | (a) done | `tools/app_appearance.py`. `python3 -m unittest tests.test_handheld_app_themes`: 9/9 pass, covering safe OSC ordering, session-scoped reload, per-app limitation (a late sync can't undo a newer selection). |
| 4.1 (background previews: memory, discovery, overlays, fit modes) | (c)+(e) split | Per-theme selection memory and lazy bounded thumbnails are done (`theme_preferences.py`, 4.2.r/4.2.r2). **Not done, and real scope**: `background_decode.rs` already implements `FitMode::Crop`/`Fit`/`Center`, but every call site (`theme_thumbnails.rs`, `main.rs`, `theme_ui.rs`) hardcodes `FitMode::Crop` — nothing lets a person choose, and `Fill`/`Solid` modes and user-supplied background overlays don't exist at all. `tests/test_handheld_theme_backgrounds.py` does not exist. Split into the successor proposal `the-background-chooser-supports-fill-solid-and-video` (drafted this session; see below). |
| 4.2 (scroll/swipe/tap with cancel/apply) | (b) superseded in part | The sibling change's task group 10 removed the separate Preview/Apply/Cancel step entirely, per your own verbatim decision ("tap theme in the theme picker, apply immediately"). There is no cancel step left to test. Live scroll/swipe/tap/reduced-motion/recovery behavior is covered by `theme_ui`'s 24-case suite and the responsiveness slices (4.2.r/4.2.r2). Recommend rewording this task rather than closing it silently; left unticked. |
| 4.3 (muted video backgrounds) | (e) unimplemented | `background_decode.rs` states outright it does not decode video. No `.#handheld-wallpaper` output, no test file. Genuine unimplemented scope; split into the same successor proposal as 4.1 above (`the-background-chooser-supports-fill-solid-and-video`, drafted this session). |
| 5.1 (build touch-launcher/card-shell/toplevel) | (a) done, with a scope note | `touch-launcher` and `card-shell` both built (cache hits) today. The plain (non-`coherentShell`) `k230` toplevel — which carries none of this change's surface — was not freshly built; the `coherent-shell` toplevel this feature actually lives under has been built and installed repeatedly per the evidence cited in `tasks.md`. |
| 5.2 (reserved-board trial tool, host-verified first) | (a) done | `tools/handheld-theme-trial.py`. `python3 -m unittest tests.test_handheld_theme_trial`: 8/8 pass. |
| 5.3a (board activation: dark/light/community) | (a) done | `docs/evidence/omarchy-themes/board-switching/README.md` (dark+light Catppuccin, native `grim`, 2026-09-24) and `.../community-board-fixed/README.md` (unchanged Fuchsblau community theme, restoration confirmed, same date). Both injected-input, not real-finger. |
| 5.3b (real-finger chooser/gesture video, cancel behavior) | (d) real finger | Both evidence docs above explicitly disclaim real-finger input. No video exists. Needs the reserved board and an operator's finger. |
| 5.4 (`--workload backgrounds` on the board) | (d)+(e) split | Static arm is host-modeled (`docs/evidence/omarchy-themes/background-workload-host.md`) but not yet run on the board; its own text says so. Video arm is blocked on 4.3 (no video decode exists to test). |
| 5.5 (`--workload reboot`) | (c) unimplemented tool mode | `tools/handheld-theme-trial.py` has no `--workload reboot` at all yet — this is host-doable tool-writing work, not a board-only gate, and should be written before it is run. |
| 6.1 (publish evidence / site) | (d) blocked | Correctly open; depends on everything above. |
| 6.2 (validate/archive/push) | (d) blocked | Correctly open; this audit does not close it. `openspec validate --all --strict` passes today (49/49) with both changes and the new successor proposal all open and unarchived. |

### Successor proposal drafted this session

`openspec/changes/the-settings-and-notifications-surfaces-are-themed/` —
proposal.md, design.md, tasks.md and an `ADDED` spec delta for
`runtime/shell-themes`. Validates clean
(`openspec validate the-settings-and-notifications-surfaces-are-themed
--strict`) and as part of `openspec validate --all --strict` (49/49).
**Not archived, not linked as closing the parent's task 3.3** — that
requires your authorization per `AGENTS.md`. It is committed on this
branch so the scope is visible immediately rather than sitting only in a
private worktree.

### Second successor proposal drafted this session

`openspec/changes/the-background-chooser-supports-fill-solid-and-video/` —
proposal.md, design.md, tasks.md and an `ADDED` spec delta for
`runtime/shell-themes`, carrying forward exactly the still-unimplemented
half of task 4.1 (`FitMode::Fill`/`FitMode::Solid`, user background
overlays — per-theme memory and lazy thumbnails are already done and are
NOT reopened here) and task 4.3 in full (muted video backgrounds, format
diagnostics, visibility pause, reduced-motion, the board performance gate).
Validates clean (`openspec validate the-background-chooser-supports-fill-
solid-and-video --strict`) and as part of `openspec validate --all --strict`
(50/50, both successors plus the two parents all open and unarchived).
**Not archived, not linked as closing the parent's tasks 4.1/4.3** — same
authorization requirement as the Settings/notifications successor above.

## Evidence already on `master`: background selection generation and feedback

The other worktree
(`/mnt/MediaVolume/home/jadams/src/gitlab.daringbit.com/josh/k230-picker-board-evidence`,
branch `evidence/picker-working-set`) that this task described as holding
*uncommitted* evidence under `docs/evidence/theme-picker/background-selection/`
was checked and found **clean and fully committed** — its `HEAD`
(`e37dc2243afb38014663fd8c9ed73a03d27f319c`, "docs: close background fix
delivery after verified publication") is already an ancestor of local
`master`, and all 15 files under that evidence directory (including the 5
PNGs) are already present in `master` with matching blob-inventory rows
(`docs/blob-inventory.md` lines 670-674 and 2185-2189). This branch already
has them; **no copy or new inventory rows were needed.**

This evidence is exactly what `eb3905b6` ("plan: correct background
selection generation and feedback") planned, and what it produced:
`the-shell-swaps-themes-without-a-python-stall` task group 16 (16.1-16.3,
"Apply the selected background and show its result") is **already fully
ticked and cited** against this exact evidence — `97785ec7` is the fix,
`a7aa8d49` the QEMU harness update, and the published Pages URL for the
evidence page was checked over HTTP at `d937b8cd`. No gap here; nothing
further to do.

## Plan commits checked for untracked scope

- **`eb3905b6`** ("background selection generation and feedback"): fully
  implemented and tracked — see above. No gap.
- **`af492080`/`b82f0820`** (identical content, "measure remaining picker
  swipe cost and gate speculative work"): both commits only ever touched
  `the-shell-swaps-themes-without-a-python-stall`'s own `design.md`/
  `tasks.md`, adding exactly task group 13 (13.1-13.4) verbatim as it reads
  today. Nothing planned in these commits is missing from `tasks.md`; see
  the 13.1-13.4 rows above for their actual implementation status (three of
  four are real, precisely-scoped gaps, not a tracking gap).

## Commands run to reach these conclusions (host, this session)

```
python3 -m unittest tests.test_omarchy_theme_activation
python3 -m unittest tests.test_omarchy_theme_transaction
python3 -m unittest tests.test_handheld_app_themes
python3 -m unittest tests.test_handheld_theme_rendering
python3 -m unittest tests.test_handheld_theme_trial
nix build --no-link --print-out-paths .#card-shell
nix build --no-link --print-out-paths .#touch-launcher
openspec validate --all --strict
```

All passed as cited above. `tests.test_handheld_theme_backgrounds` and
`tests.test_handheld_theme_chooser` were confirmed **not to exist**
(`ModuleNotFoundError`), which is itself evidence for the 4.1/4.2/4.3
classifications above, not an oversight in this audit.
