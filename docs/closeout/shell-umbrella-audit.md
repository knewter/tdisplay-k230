# Shell umbrella closeout audit

Branch `close/shell-umbrella`, audited from `38c264e4db67` and rebased onto
`master` `a1daf003`.
Audited 2026-09-28 against `nix/rust-shell-client`, `nix/card-shell`,
`nix/card-shell-policy`, `nix/touch-launcher`, `nix/shell.nix`, committed
`docs/evidence/**`, `openspec/changes/archive/`, and `git log`.

Classification key: **(a)** done, evidence of the correct class cited and
tasks.md updated to point at it; **(b)** superseded/obsolete, cited; **(c)**
host-doable, not yet done; **(d)** needs the board or a real finger, left
open; **(e)** genuinely unimplemented, non-hardware scope (successor or
future work).

None of the five changes below is archived. Every one still has at least one
open board task, and three (`the-handheld-presents-a-coherent-shell`,
`the-shell-behaves-as-one-coherent-system`, `the-shell-manages-apps-as-cards`)
also have non-hardware scope staged into scope-split successors, per
`AGENTS.md`'s "close deliberately" rule:

- `the-shell-gets-side-edge-back-and-motion-trace` (from `the-handheld-presents-a-coherent-shell` tasks 2.2/4.4/4.5) -- **authorized by the user 2026-09-28 ("yes a-d and f")**
- `the-shell-offers-quick-toggles-and-vision-options` (from `the-shell-behaves-as-one-coherent-system` slices B/C) -- **authorized by the user 2026-09-28 ("yes a-d and f")**
- `the-card-deck-still-misses-its-frame-budget` (from `the-shell-manages-apps-as-cards` task 4.2, plus its dependent task 5.1) -- **not authorized; the user chose to investigate panel refresh timing first.** This one stays staged exactly as it was; its parent keeps ownership of task 4.2/5.1 until a future authorization.

Each successor is fully staged (proposal, design, tasks, spec deltas, all
validating). For the two authorized splits, the corresponding parent tasks
are now ticked `[x] ... MOVED, NOT PERFORMED HERE` and the parent's spec
delta narrowed to drop the requirement text the successor now owns, in the
same commit that activates each successor. Authorization moves task
ownership, not completion: none of the moved work is done, only relocated.

## the-handheld-presents-a-coherent-shell (30 open / 5 done -> 17 open / 18 done)

**Correction (2026-09-28, coordinator review):** tasks 4.1, 4.2, 4.3 and 4.8
were briefly ticked citing evidence other than each task's own named test,
and 4.8's citation was a stale evidence file from an earlier source revision.
Rerunning each task's actual command found: `tests/test_shell_motion.py`
genuinely does not exist (4.1-4.3 reopened, no way to run their command as
written), and `tests/test_card_shell_two_axis_runtime.py` fails against a
fresh `.#card-shell` build (4.8 reopened -- the cited two-axis-qemu evidence
is from source `532115c2`, not this branch's current state). Task 1.6 also
cited another change's stale test run rather than a fresh one; rerunning it
here found a real (harness-only) compile bug in `nix/rust-shell-client`'s
test crate, since fixed on master by `close/themes` (`d622576a`), with 299/299 tests passing after rebase -- kept ticked with the
corrected citation. Net count corrected from the previously reported 22 done
to 18 done.

Most of this change's host-scope tasks turned out to already be implemented,
just via a different path than the tasks' own cited commands assumed: the
final UI was built directly as `nix/rust-shell-client` (`Route::Drawer/Shade/
Settings/Hide`) plus `nix/card-shell-policy/card-shell-policy.c`'s `CS_DECK`,
not by growing `nix/touch-launcher --serve`. `tests/test_shell_routes.py`,
`test_shell_gestures.py`, and `test_shell_motion.py` (the last of which does
not exist) are stale for this reason; the real evidence trail is the ~35
checkpoint files under `docs/evidence/coherent-shell/`.

| Task | Classification | Citation / next step |
|---|---|---|
| 0.1, 0.2 | done (pre-existing) | Rust probe pinned/cross-built. |
| 0.3 | (d) | `docs/evidence/coherent-shell/rust-probe-board/README.md` exists (board process + native capture) but its own text says it "does not close coherent-shell task 0.3" -- no touch or camera evidence. Needs a board session running `tests/test_rust_shell_probe.py`'s cases plus camera evidence. |
| 1.1 | (a) | `docs/evidence/coherent-shell/{drawer-route-host.md,rust-drawer-interaction-host.md,reveal-integrated-qemu,reveal-stream-host.md}` + `Route` enum in `nix/rust-shell-client/src/lib.rs` + `card-shell-policy.c` `CS_DECK`. |
| 1.2 | (a) | `docs/evidence/coherent-shell/rust-drawer-interaction-host.md` (bounded flick/tap-stop, cancels on second contact/Back). |
| 1.3 | (a) | Same file: "a long press opens a cancellable context sheet." |
| 1.4 | (a) | `nix/rust-shell-client/src/icon.rs` + `nix/card-shell/icon.c` (added by `the-shell-behaves-as-one-coherent-system` A.3); `tests/test_shell_icons.py` 8/8 passing; `docs/evidence/coherent-shell/icons/`. |
| 1.5 | (e), partial | Gesture cues (`render.rs:1704`), Help (`render.rs:3751`), and the rollback bar (`coherentShell` defaults `false`) all confirmed present. The opt-in large-labeled-button accessibility aid does not exist anywhere in `nix/rust-shell-client` or `nix/card-shell` (grepped for "accessib", zero hits). Left open for that one remaining piece; distinct from the text-scale/contrast option in `the-shell-offers-quick-toggles-and-vision-options`. |
| 1.6 | (a) | `flake.nix:191` (`handheld-shell-rust` package); `cargo test --manifest-path nix/rust-shell-client/Cargo.toml --locked` rerun 2026-09-28 after rebasing onto `a1daf003`: 299/299 passing. The earlier test-crate compile bug (`tests/theme_catalog_module.rs`, unresolved `crate::runtime_trace`) is fixed on master by `close/themes` (`d622576a`); `docs/evidence/coherent-shell/{prototype-launcher-build.md,image-wiring-host.md}`. |
| 2.1 | (a) | `docs/evidence/coherent-shell/{settings-backend.md,notification-backend.md}`; `Route::Shade`/`Route::Settings`. |
| 2.2 | (e) -> successor, authorized | `openspec/changes/the-shell-behaves-as-one-coherent-system/proposal.md` names this task explicitly as still open; only the narrower, different bottom-edge overlay-escape fix landed. Moved to `the-shell-gets-side-edge-back-and-motion-trace` task 1.1; parent task now `[x] MOVED, NOT PERFORMED HERE`. |
| 2.3 | (a) | `tools/device_settings.py` implements the exact capability-state contract (network/brightness/keyboard/motion, no battery key); `tests/test_device_settings.py` 9/9 passing. |
| 2.4 | (a) | Same test file (`test_restart_cancel`, `test_denial_consumes_confirmation`, `test_expired_and_replaced_confirmation`); `docs/evidence/coherent-shell/settings-backend.md`. |
| 2.5 | (a) | Ran `nix build .#handheld-settings --no-link --print-out-paths` 2026-09-28: succeeded, `/nix/store/46sw7cwipb8g0pfjqa7vry4x1x65345g-k230-settings`. |
| 3.1 | (a) | `tools/notification_center.py` + `tests/test_notification_center.py` 9/9 passing. |
| 3.2 | (a) | Same test file; `notification_center.py`'s preview is non-focus-taking by construction (`"focus": False` on every emitted event), so the typing-focus case holds by design. |
| 3.3 | done (pre-existing) | Unchanged. |
| 3.4 | (a) | Ran `nix build .#handheld-notifications --no-link --print-out-paths` 2026-09-28: succeeded, `/nix/store/n9p1qlrflc463v3siyrhj49n5hdbh1fd-k230-notifications`. |
| 4.1 | (e), reopened | `tests/test_shell_motion.py` (this task's own named fixture) does not exist. `nix/card-shell/adapter.c` privacy/eligibility handling and `docs/evidence/card-shell/injected/README.md` are real but do not substitute for the named test. |
| 4.2 | (e), reopened | Same reason as 4.1. QEMU evidence exists (`docs/evidence/coherent-shell/{reveal-integrated-qemu,direct-reveal-drag-qemu,rust-shade-dismiss-qemu,two-axis-qemu}/README.md`) but is not this task's named fixture. |
| 4.3 | (e), reopened | Same reason as 4.1. `card-shell-policy.c`'s reverse/retarget state (`entry_reverse_from`, `expand_reversing`) is real and exercised in `two-axis-qemu/README.md`'s reverse case, but again not the named fixture. |
| 4.4 | (e) -> successor, authorized | Same citation as 2.2; moved to the same successor's task 1.2; parent task now `[x] MOVED, NOT PERFORMED HERE`. |
| 4.5 | (e) -> successor, authorized | `tools/shell-motion-trace.py` and `tests/test_shell_motion.py` confirmed absent from disk. Moved to the same successor's tasks 2.1/2.2; parent task now `[x] MOVED, NOT PERFORMED HERE`. |
| 4.6 | (a) | Task names the wrong attr (`k230` instead of `k230-coherent-shell`); task 4.9 (done) already built `sdImage-coherent`, which builds the `k230-coherent-shell` toplevel as a dependency. `docs/evidence/coherent-shell/boot-artifacts/README.md`. |
| 4.7, 4.9 | done (pre-existing) | Unchanged. |
| 4.8 | (e), reopened | `tests/test_card_shell_two_axis_runtime.py` exists (task text's "to be implemented" is stale) but **fails** when rerun against a fresh `nix build .#card-shell`: `AssertionError: ((0, 0, 566, 1230), (16, 0, 552, 1128))` at `tests/card_shell_runtime.py:252`. The cited `docs/evidence/coherent-shell/two-axis-qemu/README.md` is from source `532115c2`, an earlier revision, not this branch's current build. |
| 5.1-5.8 | (d) | All eight require a reserved board and/or real finger; none has committed evidence (`docs/evidence/coherent-{shell,cards,gestures,notifications,two-axis}/` do not exist yet). See `docs/closeout/board-checklist-umbrella.md`. |

**Scope split authorized 2026-09-28** ("yes a-d and f"): `the-shell-gets-side-edge-back-and-motion-trace`
carries tasks 2.2, 4.4, and 4.5 (side-edge contextual Back, general touch
ownership arbitration, and motion-trace tooling) with matching
`runtime/handheld-shell-design` requirement text. The parent's own
`runtime/handheld-shell-design` spec delta has been narrowed to drop that
text. The parent is **not** archived -- it keeps its own board tasks (0.3,
5.1-5.8) and reopened tasks (4.1-4.3, 4.8) regardless of this split.

## the-shell-behaves-as-one-coherent-system (4 open / 16 done, after the B/C scope split)

Slices A (webOS-fan overview) and E (bottom-edge overlay escape) are
implemented with host/QEMU evidence; only their board tasks (A.4, E.4) are
open. Slices B (shade quick toggles) and C (vision accessibility) have no
code yet -- their 8 tasks are ticked `[x] MOVED, NOT PERFORMED HERE` per the
2026-09-28 authorized split, not because the work is done; only D.1 (moved
already ticked before this audit), D.2, and D.3 remain from group D.

| Task | Classification | Citation / next step |
|---|---|---|
| A.4 | (d) | `docs/evidence/card-shell/webos-fan-switcher/README.md` is headless-QEMU only and says so explicitly ("not a substitute"). Operator command in tasks.md. |
| B.1-B.3 | (b)/(c) mixed, moved -> successor, authorized | Brightness half of B.1 is superseded by `the-brightness-control-is-a-slider` (`render.rs:1717` `Route::Shade` slider). Keyboard-toggle half is small/mechanical (same pattern as the existing `shade_and_settings_hits_are_bounded_and_cancel_scroll_taps` test) but not implemented. Parent tasks now `[x] MOVED, NOT PERFORMED HERE`; moved to `the-shell-offers-quick-toggles-and-vision-options` tasks B.1-B.3. |
| B.4 | (d) -> successor, authorized | Operator command in successor's tasks.md. Parent task now `[x] MOVED, NOT PERFORMED HERE`. |
| B.5 (untracked shade tap-target requirement) | (e) -> successor, authorized | Added as a new task in the successor (parent had the requirement with no task). |
| C.1 | (c) -> successor, authorized | Small: a Rust-side enum/field + persistence, same pattern as existing theme-choice persistence. Parent task now `[x] MOVED, NOT PERFORMED HERE`. |
| C.2 | (e) -> successor, authorized | Not small: requires extending `struct card_appearance` (`nix/card-shell/appearance.h`), the `report.json` schema, and both C and Rust renderers -- a real cross-process protocol change, not a Rust-only edit. `webos-polish-review.md` P1-1 independently confirms this channel does not exist yet. Parent task now `[x] MOVED, NOT PERFORMED HERE`. |
| C.3 | (c)/(e), blocked on C.2, moved | Not implemented; depends on C.2 landing first, now in the successor. Parent task now `[x] MOVED, NOT PERFORMED HERE`. |
| C.4 | (d) -> successor, authorized | Operator command in successor. Parent task now `[x] MOVED, NOT PERFORMED HERE`. |
| D.2 | (c), blocked | A/E's own toplevel evaluation is done/cited; B/C's own toplevel evaluation moved to the successor's own D.2. |
| D.3 | gate | Blocked on A.4/E.4 only now that B.4/C.4 moved with the rest of slices B/C. |
| E.4 | (d) | Host/QEMU evidence exists (`overlay-bottom-escape-qemu/README.md`); needs real board proof. |

**Scope split authorized 2026-09-28** ("yes a-d and f"): `the-shell-offers-quick-toggles-and-vision-options`
carries slices B and C (plus new task B.5 for the untracked shade tap-target
requirement) unchanged. **Not implemented yet** -- this is bookkeeping only;
the actual keyboard-toggle/accessibility-scale code remains to be written,
in the successor. The parent's own `runtime/device-settings` and
`runtime/notification-center` spec deltas, which existed solely for slices
B/C, have been removed (they now live only in the successor). The parent
keeps A.4 and E.4 as its own remaining board gates regardless of this
split.

## the-shell-manages-apps-as-cards (4 open / 10 done -> 3 open / 11 done)

| Task | Classification | Citation / next step |
|---|---|---|
| 4.2 | (e), longstanding perf gate -> successor | Ten-plus board rounds (`docs/evidence/card-shell/{board-cost/long-trace,touch-timestamps/board,throw-sampling,repaint-stages,throw-fixture-sync,scaled-cache-board}/README.md`, `kernel-rvv/card-cost/README.md`) have never passed the declared CPU/tracking budgets. Tracking-presentation p95 is ~57.47-57.49ms against a 33.334ms budget in every single run, invariant across cache/RVV/fixture-timing changes -- looks structural (output cadence), not a code-fixable CPU cost. `renderer-decision.md` already declines the GPU/VGLite path. Staged in `the-card-deck-still-misses-its-frame-budget`, **awaiting authorization**, per this task's own text ("leave this change open or request explicit authorization for a successor"). The successor's design.md suggests measuring actual panel vblank cadence directly before another CPU-side board round. The right next step (further investigation vs. explicitly accepting the miss) is left as a coordinator decision, not predetermined. |
| 5.1 | (c), blocked on 4.2 -> successor | `tools/qemu-k230.sh --card-shell-smoke` and its fixture already pass (`docs/evidence/card-shell/qemu-fixture/passing/result.json`). `docs/research/card-shell-qemu-smoke.md`'s own "Remaining integration gate" section says this task stays unchecked until 4.2's board budgets pass -- it is not independently host-doable, so it is carried into the same successor as 4.2. |
| 5.3 | (d) | `docs/evidence/card-shell/real-touch/` does not exist; `injected/README.md` (task 5.2, done) is explicit its provenance is injected, not a finger. Operator command in tasks.md. |
| 6.1 | done 2026-09-28 | `openspec validate the-shell-manages-apps-as-cards --strict` passes; `specs/runtime/card-shell/spec.md`'s `UNVERIFIED` markers were rewritten to cite the real injected-touch/failing-board-cost evidence instead of stale "not observed" text. Does not close the change: 4.2, 5.1, 5.3 remain open. |

## the-launcher-explains-app-actions (4 open / 0 done -> 2 open / 2 done)

Targets `nix/touch-launcher/`, the default bar session (`coherentShell`
defaults `false`), so this scope is real and current, not superseded by the
still-unmerged coherent-shell work.

| Task | Classification | Citation / next step |
|---|---|---|
| 1.1 | done 2026-09-28 | `nix/touch-launcher/catalog.c`/`.h`: a curated policy table suppresses `footclient.desktop`/`foot-server.desktop`, demotes `foot.desktop`/`htop.desktop` as duplicates of the built-in Terminal/Monitor rows, and describes unknown entries from `Comment=`/`GenericName=`. `tests/test_desktop_catalog.py` 6/6. `docs/evidence/launcher-curation/host.md`. |
| 1.2 | done 2026-09-28 | Same commit: failed-launch copy (`k230_app_failure_copy`) names the app and "Back returns to Apps"; raw GLib text goes to stderr only. `tests/test_launcher_navigation.py` 4/4. Back's rendered visibility (not just the page model) is deferred to task 2.2. |
| 2.1 | (c), blocked on build slot | `nix build .#touch-launcher` not run: a dry run lists 12 uncached riscv64 derivations (cairo, pango, librsvg, json-glib, ...), needing the shared build slot per `AGENTS.md`. |
| 2.2 | (d) | Operator command already in tasks.md (`launcher-curation`, `--provenance real-touch`). |

## the-shell-makes-recovery-routes-legible (4 open / 0 done, unchanged)

Targets the same default bar session (`nix/touch-launcher.c`, plus
`nix/touch-menu.sh` for the bar itself -- the persistent Apps/Windows/
Keyboard/System bar this change's `Why` describes lives in `touch-menu.sh`,
not `touch-launcher.c`).

| Task | Classification | Citation / next step |
|---|---|---|
| 1.1 | (c), not done | `nix/touch-menu.sh`'s `home` page array (line 49) has no `home` segment even though its click handler (line 129, `terminal\|home) ... present_or_start k230-terminal ...`) already recognizes `home` unchanged -- a small, mechanical addition. The broader ask (shared state-ID/copy-key table spanning `touch-launcher.c`, `touch-menu.sh`, and `nix/video-session.py`) is real design work, not left undone by oversight. Not implemented in this session: no dedicated test harness exists for `touch-menu.sh` to verify a change against, and rewriting three subsystems' error/state copy under time pressure without board or automated proof was judged too risky to do blind. |
| 1.2 | (c), not done | Depends on 1.1's shared contract. Raw-leak points already identified: `touch-launcher.c:314,339,354` still assign `error->message` directly in call sites task 1.1/1.2 of the launcher change did not touch (only `launch_selected`'s copy, at line 626-area, was fixed by that commit). |
| 2.1 | (c), blocked on build slot | Same as the launcher change's 2.1. |
| 2.2 | (d) | Operator command already in tasks.md (`recovery-routes`, `--provenance real-touch`). |

This change is left entirely open. It is small, host-doable, and well-scoped
by its own design.md, but implementing it correctly means designing one
shared state-ID/copy-key contract across three files with no existing
regression test -- worth a dedicated, unhurried pass rather than a rushed
edit in this closeout session.
