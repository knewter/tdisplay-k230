**Sequenced by user decision (2026-09-28):** start groups 1-2 after the
current shell work lands, and fold `docs/design/webos-polish-review.md`,
`docs/design/shell-polish-review-2026-09.md`, and
`docs/design/handheld-shell/visual-gap-audit.md` into `references-and-gap.md`
and `findings.md` as raw input rather than repeating that critique — see
`Status (2026-09-28)` in `proposal.md`.

## 1. Baseline and reusable rubric (host analysis)

- [x] 1.1 Create `docs/research/handheld-ux/review-round-2/baseline.md` and `rubric.md`, pinning source/image/experimental packages and linking the existing evidence for each surface and journey in design.md. Verify by reviewing the inventory against the flow matrix; explicitly retain unavailable states and evidence gaps. Coordinator-reviewed 2026-10-01; current-source/store identity, journey matrix cross-check, and unavailable states are explicit.
- [x] 1.2 Inspect the existing referenced webOS material and record source URLs, access dates, relevant timestamps, observed principles, and a current-shell comparison in `references-and-gap.md`. Verify every comparison has an inspected source and a current artifact or UNVERIFIED marker; do not infer device performance from a reference video. Coordinator-reviewed 2026-10-01; book PDF/printed page numbers, Palm Pre guide pages and webOS OSE guide sections are recorded with 2026-10-01 access date; no video timestamp is used.

Proof: `openspec validate the-handheld-gets-a-design-and-ux-review --strict` plus coordinator review of the three documents and cited artifacts. This is host documentation proof, not QEMU or hardware acceptance.

## 2. Visual and journey critique (parallel host analysis)

- [x] 2.1 Produce a visual consistency critique and at least three annotated current/target sheets covering Apps, cards, and keyboard/recovery, plus one transition storyboard under `review-round-2/`. Render and inspect all sheets; record the exact render invocation and review corrections in `visual-review.md`. Verify proposal labels, portrait geometry, readable annotations, and links to current evidence. Coordinator reviewed the rendered sheets and required revisions, then agreed on closure 2026-10-01; older card/keyboard sources and the missing latest deck image remain clearly labeled.
- [ ] 2.2 Independently walk the baseline journeys and review discovery, focus, feedback, motion, keyboard occlusion, recovery, accessibility, and consistency in `journey-review.md`. Verify each issue names a reproducible action/state and evidence confidence, and each relevant keyboard-visible state is covered or explicitly unknown.
- [x] 2.3 Reconcile both critiques in `findings.md`, with stable issue IDs, severity, confidence, proposed correction, existing owner or successor, dependency, rough effort, and observable acceptance. Verify shared type/spacing/color/touch/motion recommendations are coherent and the independent reviewer has recorded agreement or remaining disagreements. Coordinator review and corrections are recorded in `findings.md` and `visual-review.md`; no disagreement remains on the four scoped findings, and physical impact stays unverified where applicable.

Proof: `openspec validate the-handheld-gets-a-design-and-ux-review --strict` and `python3 scripts/build_site.py`, plus recorded visual inspection and independent critique. Site generation proves publication integrity, not usability; do not mark these tasks complete from validation alone.

## 3. Integrated candidate recheck (serialized board observation)

**Sequenced by user decision (2026-09-28):** best timed after the
theme-picker, power-key, and other current shell work lands, so the recheck
runs against a more final integrated candidate — see `Status (2026-09-28)`
in `proposal.md`.

- [ ] 3.1 Reserve the board and record the integrated candidate identity with `flock /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=3 'readlink -f /run/current-system; systemctl is-active shell.service; systemctl show shell.service -p MainPID -p ExecStart; readlink -f /proc/$(systemctl show shell.service -p MainPID --value)/exe'`. Record any separately launched experimental compositor's unit/PID, resolved executable, and package explicitly; the default system closure alone does not identify it. Commit a sanitized transcript and native screenshots with their exact capture commands. Verify the candidate is identified separately from baseline and opt-in packages; no reflash is required merely to conduct this review.
- [ ] 3.2 Recheck each P0/P1 finding against that candidate and commit `candidate-recheck.md` with before/after evidence and remaining owners. Reuse unchanged accepted physical observations. If a changed behavior requires new optical/finger evidence, use `python3 tools/capture-feature.py ux-review-round-2 --provenance real-touch --duration 30 --description 'Focused design review of changed handheld flows' --output-dir docs/evidence/ux-review-round-2` during a coordinated operator session, inspect the footage, and record its actual limits. If unavailable, mark those claims UNVERIFIED and preserve the acceptance work with its runtime owner; do not silently waive it.

Proof: the recorded console command, committed native captures and reviewed recheck table; use the named camera command only for actual physical interaction. This is hardware observation with separately labelled injected/native/optical/finger evidence, not QEMU proof. Missing physical footage cannot establish readability or finger tracking.

## 4. Next work and publication (host planning)

- [x] 4.1 Publish `recommendations.md` answering what works, what feels unfinished, the webOS-inspired gap, candidate improvements, and the next three priorities. Map every priority to an existing proposal or create full bounded successor artifacts; verify no duplicate card/GPU/launcher/recovery scope and list parallel paths and board dependencies. The three priorities route to existing picker-motion/theme, integrated card/keyboard recheck, and theme-consumer/Settings owners; no duplicate successor proposal was needed.
- [ ] 4.2 Validate, review, merge, and push the report and all new priority proposals to master; update the site's status/evidence links without claiming unimplemented designs as shipped. Verify the exact commit in CI and Pages, then archive this analysis only when all its tasks and committed evidence are complete. Implementation successors may remain open.

Proof: `openspec validate --all --strict`, `python3 scripts/build_site.py`, and `python3 tools/work-status.py`; inspect the exact-revision CI/Pages run with `gh run list --branch master --limit 5` and `gh run view <run-id>`. Record the deployed URL and revision in the handoff. This proves planning/publication, not completion of successor runtime features.

**Host closeout note (2026-10-01):** Tasks 1.1, 1.2, 2.1, 2.3 and 4.1
are complete in `docs/research/handheld-ux/review-round-2/`; named strict
validation and the site build pass. Task 2.2 remains open because this review
did not walk every current-source journey, even though the exact candidate has
three unchanged operator-accepted real-finger checks. Tasks 3.1–3.2 remain
open for the focused integrated candidate/physical recheck. Task 4.2 remains
open for reviewed publication, merge/push, exact-revision CI/Pages and the
published URL. This change is not ready to archive.
