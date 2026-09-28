# Stale-change triage — 2026-09-28

Scope: the four OpenSpec changes with 0/N tasks done —
`characterise-bootrom-usb-recovery`, `the-boot-shows-a-computational-game-of-life`,
`the-handheld-evaluates-qtquick-and-quickshell`, and
`the-handheld-gets-a-design-and-ux-review`. This is triage for the user's
decision; nothing was implemented, archived, merged, pushed, or run on the
board to produce it. No task box in any of the four changes was ticked: for
every task, the specific artifact its own verify command names is not yet
committed, so none meets the "tick only with a citation to existing evidence"
bar in `.skills/k230-spec-change/SKILL.md`. Several tasks are, however,
substantially de-risked by evidence that already exists elsewhere, which is
recorded per change below.

## Summary table

| Change | Recommendation | Reason | Effort | Decision needed |
| --- | --- | --- | --- | --- |
| `characterise-bootrom-usb-recovery` | **KEEP** | Genuinely untested: no committed evidence anywhere in the repo shows a BootROM (`29f1:0230` pre-U-Boot) USB device. UMS recovery already covers the common case, so this is a belt-and-suspenders path, not a blocker. Groundwork (J3=data/J2=console, card-reader+UMS recovery steps, known-good-image handling) is already written up in `docs/uboot-ums.md` and can be cited rather than re-derived, so tasks 1.1/1.2 are mostly a citation exercise, not new work. | Small — one board session (~30–60 min): power off/no-card capture, power off/SW3-held capture, `lsusb`/`dmesg`/serial logs. Task group 3 (destructive disposable-card write) only proceeds conditionally and adds more time if BootROM entry is confirmed. | Authorize one board+serial session for the two power-cycle observations (tasks 2.1–2.2), and say whether the conditional destructive-card test (group 3) should be attempted in the same session or deferred. |
| `the-boot-shows-a-computational-game-of-life` | **KEEP, but low priority** | Its stated hard prerequisite — "Require the current static splash geometry/color handoff defect to be fixed before this change is accepted" — was written against `docs/evidence/boot-splash-handoff.md` when the first Sway modeset was still wrapped/color-shifted. Since then, the *in-flight* `the-screen-lights-before-linux` change closed exactly that defect at its own tasks 4.4/5a.1–5a.3 (`docs/evidence/splash-first-modeset-preserve/README.md`: 420 consecutive frames retain the logo with no captured dark frame at the shell transition; `docs/evidence/splash-initial-scene-ready/README.md`). That change is not archived — tasks 3.6, 4.3, 5.2/5.4, 6.1, 6.2 are still open — so this cannot be ticked as "prerequisite satisfied," but the blocking condition is no longer actually true, and this change's task 1.1 should cite that evidence rather than re-observe the defect. No other work has touched the Game of Life engine, RAM ownership, or touch-glider scope — it is still 100% unstarted, and it is a large change: portable C engine, a new reserved-RAM ABI validated against the compiled DTB, two U-Boot/kernel handoff stages, real touch integration, an optional (explicitly non-gating) Goodix-in-U-Boot port, and an optional Wayland continuation, each with its own hardware filming. It is a delight feature on top of a boot splash, not something anything else depends on. | Large overall (kernel + RAM-map tooling + repeated hardware filming across two stages); the *next* step is Small — task 1.2, the portable C engine and its host-only test, needs no board and no dependency on the splash change landing. | Say whether this stays queued behind the in-flight shell/theme/power-key work (per AGENTS.md, do not touch those worktrees) or should be actively picked up now that its blocking defect is functionally resolved elsewhere. |
| `the-handheld-evaluates-qtquick-and-quickshell` | **KEEP, deprioritized** | Not abandoned by other work — no alternative decision record chooses or rejects Qt Quick as an *app* toolkit; `docs/research/quickshell-qtquick-feasibility.md` is a "conditional go" that this change exists to test, not a substitute for testing it. A real start exists: `nix/qtquick-software-probe/` (packaged probe source, `default.nix`, `Probe.qml`) and `docs/evidence/qtquick/minimal-probe-prebuild.md` record a real riscv64 cross-build reaching 28/40 required derivations before the coordinator explicitly deprioritized it ("prioritized goal-critical card and Rust builds") and it was cleanly interrupted rather than left dirty — none of that is a failure, but none of it meets task 1.1's own verify command (`nix build .#qtquick-software-probe ... --print-out-paths` has not completed) so it cannot be ticked. The rest of the change (baseline SHM client, `tools/qtquick-trial.py` manifest/analyzer/recovery tooling, board trial stage, Quickshell stage) has no code at all yet. This is a bounded, opt-in evaluation with explicit non-goals against replacing Sway/the card shell, so it does not conflict with the separate Rust shell-client/probe track (`nix/rust-shell-client/`, `nix/rust-shell-probe/`), which is about the compositor chrome, not guest apps. | Large — Qt Base/Declarative/ShaderTools/Wayland have no binary cache for riscv64; the interrupted build alone ran 18+ minutes past 28 already-cached derivations before being cut off, and the remaining tooling (baseline client, trial harness, two board reservations for Qt then Quickshell) is substantial. | Confirm this still matters enough to hold a dedicated build slot until the interrupted `nix build .#qtquick-software-probe` completes, or say it should wait indefinitely behind card-shell/Rust-shell work — in which case it should stay open but explicitly parked, not closed, since no decision has actually been reached. |
| `the-handheld-gets-a-design-and-ux-review` | **KEEP, but rescope as consolidation** | This proposal (2026-09-23) predates a run of *informal* reviews explicitly written to feed it rather than replace it: `docs/design/webos-polish-review.md` (24 Sep — "not the formal `the-handheld-gets-a-design-and-ux-review` change... raw input for `references-and-gap.md` and `findings.md`"), `docs/design/shell-polish-review-2026-09.md` (25 Sep, re-reviews `shell-ux-critique.md` and `visual-gap-audit.md` against a newer tree), and `docs/design/handheld-shell/visual-gap-audit.md`. None of `review-round-2/`'s named deliverables (`baseline.md`, `rubric.md`, `references-and-gap.md`, `visual-review.md`, `journey-review.md`, `findings.md`, `candidate-recheck.md`, `recommendations.md`) exist yet — the directory itself is not created — so no task ticks, but a large fraction of the *analysis* those tasks call for (visual hierarchy, typography, spacing, icon/corner-radius/elevation critique, webOS comparison with citations) has already been done at least once, sometimes twice, informally. This is consolidation-plus-verification work, not a blank-page review. The archived first UX plan (`2026-09-23-the-handheld-has-a-coherent-ux-plan`, `docs/research/handheld-ux/`) is also directly reusable source material per this proposal's own text ("Existing accepted keyboard/Home observations are reusable"). Group 3 (serialized board recheck of P0/P1 findings on the integrated candidate) is real, un-started hardware work distinct from any of the informal reviews. | Medium for groups 1–2 and 4 (mostly citing/reconciling three existing documents plus the archived plan into the named deliverables, not fresh critique) — Small-to-Medium hardware session for group 3 (console identity capture + recheck against existing findings; new optical/finger evidence only where a changed behavior demands it). | Confirm the coordinator wants the three informal reviews formally folded into `review-round-2/` now (fast, mostly writing) versus waiting for more shell changes (theme-picker, power-key, second-core, heartbeat — all explicitly out of scope for me here) to land first, since the group-3 board recheck is more useful once those settle. |

## Per-change detail

### `characterise-bootrom-usb-recovery` (11 open / 0 done)

**Intent.** Prove, with the TF card removed and with SW3/BOOT0 held, that the
K230 BootROM itself exposes a USB device before any stage-1 software runs —
the recovery path that works even when the card has no bootable U-Boot at
all — and, only if that device appears, verify the vendor `k230_flash` tool's
write-and-reboot path on a disposable card without touching the known-good
one.

**What's happened since.** The sibling change
`2026-09-22-the-card-is-flashed-over-usb-from-u-boot` (archived) completed
U-Boot's `ums` gadget recovery path and explicitly split BootROM
characterization out as this successor rather than let it hide behind UMS
evidence (`openspec/changes/archive/2026-09-22-the-card-is-flashed-over-usb-from-u-boot/tasks.md`
§5: "BootROM recovery was not tested and is not part of this completed UMS
change"). `docs/uboot-ums.md` documents the BootROM's existence, its four
strap combinations, `SW3`→`BOOT0`, and the vendor `k230_flash`/`k230_flash_py`
tooling as read-only research (§5, "Route C") but never actually power-cycled
the board with the card removed or the button held. No file in
`docs/evidence/` contains `29f1:0230`, `lsusb`, or `k230_flash` output from an
actual BootROM enumeration attempt.

**Task audit.** No task's own artifact exists: `docs/evidence/` has no
BootROM-recovery evidence file at all. Tasks 1.1/1.2 (confirm image hash,
serial device, cables, recovery instructions, rollback image) are answerable
almost entirely by citing `docs/uboot-ums.md` (J3=data, J2=console, VID/PID
`29f1:0230` from a *running* U-Boot gadget, and the existing UMS/card-reader
procedure as the rollback), so they are cheap but not yet done as this
change's own committed record. Tasks 2.x–4.x are fully unperformed.

**Recommendation: KEEP.** Reasoning above. Effort: Small — a single board
session covers the two required observations (task group 2); task group 3
only runs if group 2 confirms a device, and only with the safety
prerequisites (disposable card, verified rollback) task 3.2 already
requires before it can proceed.

### `the-boot-shows-a-computational-game-of-life` (10 open / 0 done)

**Intent.** Give the boot splash a small, real workload — a shared C Game of
Life engine rendered by U-Boot and continued by early Linux — with a
versioned reserved-RAM handoff, a deterministic default pattern, and a
touch-dropped glider once Linux owns the panel; explicitly not a promise of
uninterrupted animation during kernel boot.

**What's happened since.** The design's own stated prerequisite — the first
Sway modeset's physical wrap/color defect — is tracked and appears resolved
inside the still-open `the-screen-lights-before-linux` change: task 4.4
("first-modeset acceptance") and the 5a sub-series closed with
`docs/evidence/splash-first-modeset-preserve/README.md` (420 consecutive
frames retain the stage-1 logo through the owner/shell transition with no
captured dark frame) and `docs/evidence/splash-initial-scene-ready/README.md`
(physical warm-boot samples without the earlier dark gap). That change is
**not archived** — `docs/evidence/boot-splash.md` and the tasks file still
show 3.6, 4.3, 5.2/5.4, 6.1, 6.2 open — so this change's prerequisite is not
formally "done," but the specific defect it names as a blocker is no longer
the current observed behavior.

**Task audit.** No engine code, no `tools/check-boot-life-memory.py`, no
`docs/evidence/game-of-life/` directory exists. All ten tasks are fully
unstarted; none can be ticked. Task 1.1 in particular should be rewritten to
cite the evidence above rather than re-run the defect check from scratch once
work resumes.

**Recommendation: KEEP, low priority.** This is additive boot polish with no
downstream dependents; nothing else in the tree needs it. It does not
conflict with in-flight theme-picker/power-key/heartbeat work. Effort: Large
overall (new RAM ABI, two-stage kernel/U-Boot handoff, real touch, repeated
filming); the concrete next step — task 1.2, the portable C engine with its
`cc ... && test-game-of-life` host check — is Small and needs neither the
board nor the splash change to land first.

### `the-handheld-evaluates-qtquick-and-quickshell` (13 open / 0 done)

**Intent.** Determine, with measured evidence rather than a demo, whether a
minimal Qt Quick (software scene graph) Wayland app and, conditionally, a
Quickshell layer-shell panel are usable on this handheld — startup, memory,
CPU, and input latency against an equivalent SHM baseline — without adopting
either as the default shell or app toolkit.

**What's happened since.** `docs/research/quickshell-qtquick-feasibility.md`
(2026-09-23, cited by this proposal) is the source-reading groundwork that
motivated this change; it is a "conditional go for one small Qt Quick app
preflight," not a result. Real implementation work exists and was
deliberately paused, not abandoned: `nix/qtquick-software-probe/` (probe
source, `Probe.qml`, `default.nix`) plus
`docs/evidence/qtquick/minimal-probe-prebuild.md` record a real riscv64
cross-build of `.#qtquick-software-probe` that reached 28 of 40 required
derivations cached before the coordinator "prioritized goal-critical card and
Rust builds" and the task's own Nix client was interrupted cleanly (`error:
interrupted by the user`, not a build failure). Separately, an unrelated
GPUI/Rust-renderer feasibility study
(`docs/research/gpui-handheld-feasibility.md`) reached a "do not replace Sway"
verdict for a *different* toolkit and does not bear on Qt Quick apps. The
`nix/rust-shell-client/` and `nix/rust-shell-probe/` packages are a separate,
also-unfinished track evaluating the compositor's own chrome in Rust, not
guest-app toolkits, so they neither satisfy nor conflict with this change's
scope.

**Task audit.** Only task 1.1 has partial, uncommitted-as-success progress:
the probe package exists and evaluates, and 28/40 target derivations are
already realized in the local Nix store, but the task's own verify command
(`nix build .#qtquick-software-probe ... --print-out-paths`) has not
completed, so it is correctly left unticked per
`docs/evidence/qtquick/minimal-probe-prebuild.md`'s own conclusion ("Task 1.1
remains open"). No other task (1.2 onward) has any code.

**Recommendation: KEEP, deprioritized.** No decision has actually been
reached for or against Qt Quick apps; the work was paused for board-time
triage, not because it failed or became moot. Effort: Large — Qt's cross
build has no binary cache on riscv64 (the interrupted run alone took 18+
minutes past 28 cached dependencies), and the remaining scope (SHM baseline,
trial/analyzer tooling, two separate board reservations for Qt then
Quickshell) is substantial on top of that.

### `the-handheld-gets-a-design-and-ux-review` (9 open / 0 done)

**Intent.** Run a second, more rigorous design/UX critique round across the
whole shell — a reusable rubric, current-vs-target visual sheets, an
independent journey walkthrough, reconciled severity-ranked findings, and a
recheck of the highest-priority findings against the actual integrated build
— producing an ordered backlog rather than another one-off critique.

**What's happened since.** This proposal predates three informal reviews
explicitly written *for* it: `docs/design/webos-polish-review.md` (24 Sep)
states outright that it is "not the formal
`the-handheld-gets-a-design-and-ux-review` change... a coordinator folding
this into the formal review round should treat it as raw input for
`references-and-gap.md` and `findings.md`, not a finished replacement."
`docs/design/shell-polish-review-2026-09.md` (25 Sep) re-reviews the shell
against a newer tree and explicitly checks which findings from
`shell-ux-critique.md` (25 Sep) and `visual-gap-audit.md` (24 Sep) still hold.
The archived first UX plan (`2026-09-23-the-handheld-has-a-coherent-ux-plan`,
material at `docs/research/handheld-ux/`) is also named by this proposal as
reusable ("Existing accepted keyboard/Home observations are reusable; do not
request repetition"). None of this was produced as part of
`the-handheld-gets-a-design-and-ux-review` — `docs/research/handheld-ux/
review-round-2/` does not exist — so nothing here satisfies a task as
written, but the raw critique material the tasks ask for largely already
exists, twice over in places.

**Task audit.** `docs/design/app-drawer-review.md`, named as existing in the
initial framing of this triage, does not exist; the nearest artifact is
`docs/evidence/coherent-shell/first-integrated-preview/app-drawer.png`
(a capture, not a review). No `review-round-2/` deliverable exists, so no
task ticks. Group 3 (serialized board recheck) is genuinely untouched and
independent of the informal reviews, which were all done without board
access.

**Recommendation: KEEP, rescope as consolidation.** The honest framing is
"fold three existing critiques into the formal rubric and reconcile them,"
not "review the shell from scratch." Effort: Medium for groups 1, 2, and 4
(citation and reconciliation work against material that already exists);
Small-to-Medium hardware session for group 3, best timed after the
in-flight theme-picker/power-key/shell work this triage does not touch has
landed, so the recheck is against a more final candidate.

## On recording an abandonment, if the user chooses SUPERSEDE/ABANDON later

None of the four is recommended for SUPERSEDE/ABANDON here, but if the user's
decision goes that way for one of them, the mechanism consistent with
`.skills/k230-spec-change/SKILL.md` and `AGENTS.md`'s close-out rules is:

1. Add a short "Withdrawn" note at the top of the change's `proposal.md`
   stating why (what other work met the goal, or why it no longer matters),
   citing the superseding evidence or change by path.
2. Do **not** tick any task that was not actually performed — an abandoned
   change is archived with its task list exactly as it stands, unperformed
   boxes included, not backfilled to look complete.
3. Move the change directory to `openspec/changes/archive/<date>-<id>/` (the
   same mechanism `openspec archive` uses for completed changes) with that
   withdrawal note as the first thing a reader sees, and run
   `openspec validate --all` to confirm the archive doesn't leave a dangling
   `MODIFIED`/`RENAMED` reference against a capability that was never created.
4. If any capability spec files were already synced from this change's
   deltas, they must be reverted or reconciled in the same commit — an
   abandoned proposal must not leave live spec text implying the capability
   shipped.
5. Record the decision and its date in this triage doc or a follow-up commit
   message, not only in the archived proposal, so `tools/work-status.py` and
   future triage don't need to re-derive it from git history.

This is a proposal for how to record a withdrawal, not an action taken here.
