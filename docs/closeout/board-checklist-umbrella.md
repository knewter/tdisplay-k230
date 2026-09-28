# Board checklist: shell umbrella closeout

Every item below needs a reserved board and `/dev/ttyACM0` (per `AGENTS.md`:
"A single board and its serial port belong to one operator at a time" --
announce the reservation before starting and release it when done). None of
these can be satisfied by a QEMU run, a host render, or an injected-touch
replay; each command below is copied verbatim from the owning change's
`tasks.md`. Sanitize console output and camera evidence before committing
(no SSIDs, tokens, or private addresses).

## the-handheld-presents-a-coherent-shell

| Task | Pass criteria | Operator command | Evidence path |
|---|---|---|---|
| 0.3 | Real 568x1232 map/unmap, distinguishable software frame, real touch/move/cancel, bounded IPC ack, cold start/RSS/CPU/cadence measured against the C reference and Qt probe | Opt in to the Rust probe on the board; run `tests/test_rust_shell_probe.py`'s physical cases plus a camera trace | `docs/evidence/coherent-shell/rust-probe-board/` (extend; current contents explicitly do not close this task) |
| 5.1 | Bottom Home->live deck, empty deck->drawer, drawer->app, top shade->Settings, contextual Back, keyboard escape, no permanent bar, all observed on glass | `python3 tools/capture-feature.py coherent-shell --provenance real-touch --duration 60 --description 'Gesture Home drawer shade and recovery on glass' --output-dir docs/evidence/coherent-shell`, plus `flock /tmp/k230-board.lock ./tools/console.py /dev/ttyACM0 --wait=3 'systemctl is-active shell'` | `docs/evidence/coherent-shell/` |
| 5.2 | Card shrink/adjacent-swipe/snap/expand, reverse mid-transition, upward throw, refusal/timeout, all on glass | `python3 tools/capture-feature.py coherent-cards --provenance real-touch --duration 60 --description 'Card motion and close recovery on glass' --output-dir docs/evidence/coherent-cards` | `docs/evidence/coherent-cards/` |
| 5.3 | Real-finger drawer/Settings scrolling, icon/text/fallback readability, long-press cancellation, app/keyboard conflict, accessibility-aid discovery, outcome table, no accidental activations | `python3 tools/capture-feature.py coherent-gestures --provenance real-touch --duration 60 --description 'Gesture ownership and drawer discovery on glass' --output-dir docs/evidence/coherent-gestures` | `docs/evidence/coherent-gestures/` |
| 5.4 | Preview while typing, shade scroll/side-swipe cancel and committed dismiss, critical recovery, failed settings action, sanitized timestamps, outcome table | `python3 tools/capture-feature.py coherent-notifications --provenance real-touch --duration 60 --description 'Shade notification and settings motion on glass' --output-dir docs/evidence/coherent-notifications` | `docs/evidence/coherent-notifications/` |
| 5.5 | Two-app live drag, app/deck reversal, drawer rise, shade arrival; p50/p95/p99, blank/missed frames, CPU/RSS, renderer, cadence -- **report failed budgets honestly, do not round up** | `python3 tools/shell-motion-trace.py --board --output docs/evidence/coherent-shell/motion.json` | `docs/evidence/coherent-shell/motion.json` (tool does not exist yet -- see `the-shell-gets-side-edge-back-and-motion-trace` task 2.1, host-first) |
| 5.6 | `openspec validate` clean and `work-status.py` clean, **after** 5.1-5.5/5.7/5.8 land -- this is the archive gate itself, not a task to do early | `openspec validate the-handheld-presents-a-coherent-shell --strict && python3 tools/work-status.py` | n/a (process gate) |
| 5.7 | Up-then-left/right in one contact, both quick-switch directions, stationary hold, diagonal reversal, one-app/end-of-deck, target exit, app/keyboard conflicts, outcome table | `python3 tools/capture-feature.py coherent-two-axis --provenance real-touch --duration 60 --description 'Two-axis app entry and bottom quick switch on glass' --output-dir docs/evidence/coherent-two-axis` | `docs/evidence/coherent-two-axis/` |
| 5.8 | Persistent boot-file selection after 5.1-5.7 pass; exact `readlink -f /run/current-system`, shell service health, theme restoration after an ordinary reboot | `python3 tools/console.py /dev/ttyACM0 --wait=5 'readlink -f /run/current-system; systemctl is-active shell shell-ui'` plus a sanitized boot-file hash report | append to `docs/evidence/coherent-shell/boot-artifacts/` |

## the-shell-behaves-as-one-coherent-system

| Task | Pass criteria | Operator command | Evidence path |
|---|---|---|---|
| A.4 | webOS-fan overview (2-3 cards, real icons/names, scroll momentum, close, open) legible and usable at arm's length with a real theme and real apps; direct switch-gesture feel unchanged | `python3 tools/capture-feature.py webos-fan-switcher --provenance real-touch --duration 30 --description 'webOS-fan card overview: icons, names, scroll, close, open' --output-dir docs/evidence/card-shell/webos-fan-switcher` | `docs/evidence/card-shell/webos-fan-switcher/` (existing dir is host/QEMU only -- add to it) |
| E.4 | Bottom-edge overlay escape and unified dismiss direction feel right from a real finger across Settings sub-pages, no stall/glitch, correct destination every time | `python3 tools/capture-feature.py overlay-bottom-escape --provenance real-touch --duration 30 --description 'Bottom-edge overlay escape and dismiss-direction consistency on glass' --output-dir docs/evidence/coherent-shell/overlay-bottom-escape` | `docs/evidence/coherent-shell/overlay-bottom-escape/` |
| B.4 (successor, once B implemented) | Shade quick toggles reachable, correctly reflect live capability state incl. unavailable | `python3 tools/capture-feature.py shade-quick-toggles --provenance real-touch --duration 30 --description 'Shade quick-toggle reachability and live state' --output-dir docs/evidence/coherent-shell/shade-quick-toggles` | `docs/evidence/coherent-shell/shade-quick-toggles/` |
| C.4 (successor, once C implemented) | Text-scale/high-contrast choice persists across reboot, legibly larger/higher-contrast on real panel | `python3 tools/capture-feature.py accessibility-scale --provenance real-touch --duration 30 --description 'Text-scale and high-contrast option on glass' --output-dir docs/evidence/coherent-shell/accessibility-scale` | `docs/evidence/coherent-shell/accessibility-scale/` |

## the-shell-manages-apps-as-cards

| Task | Pass criteria | Operator command | Evidence path |
|---|---|---|---|
| 5.3 | Real-finger shrink, horizontal deck drag, expand, upward throw, recovery, with a committed audit distinguishing camera visibility from native state evidence | `python3 tools/capture-feature.py card-shell --provenance real-touch --duration 30 --description 'Real-finger card entry, drag, expand, close and recovery' --output-dir docs/evidence/card-shell/real-touch` | `docs/evidence/card-shell/real-touch/` (does not exist yet) |
| 4.2 (coordinator decision, not purely a capture) | An accepted budget decision, or explicit authorization for a successor -- **this is not a capture-feature task**; ten-plus board rounds have already failed the same CPU/tracking budget. Before spending another board round, consider whether the ~57.48ms tracking-interval invariant is even CPU-addressable (e.g. check actual panel/output vblank cadence) rather than re-running the same benchmark | `python3 tools/card-shell-benchmark.py --board --output docs/evidence/card-shell/pixman.json` (only if a genuinely new variable is being tested) | `docs/evidence/card-shell/` (many existing rounds; see audit doc) |

## the-launcher-explains-app-actions

| Task | Pass criteria | Operator command | Evidence path |
|---|---|---|---|
| 2.2 | Real-finger Apps discovery and a failed launch, with no raw filesystem path visible on screen; inspect target geometry/readability | `python3 tools/capture-feature.py launcher-curation --provenance real-touch --duration 30 --description 'Curated Apps catalog and recovery' --output-dir docs/evidence/launcher-curation` | `docs/evidence/launcher-curation/` |

(Task 2.1, `nix build .#touch-launcher`, is a host build blocked on the
shared build slot, not a board task -- see the audit doc.)

## the-shell-makes-recovery-routes-legible

| Task | Pass criteria | Operator command | Evidence path |
|---|---|---|---|
| 2.2 | Real-finger Home/recovery readability after the image is deployed | `python3 tools/capture-feature.py recovery-routes --provenance real-touch --duration 30 --description 'Visible Home and recovery routes' --output-dir docs/evidence/recovery-routes` | `docs/evidence/recovery-routes/` |

This change's host tasks (1.1, 1.2) are not implemented yet, so its board
task cannot usefully run until they land -- see the audit doc.

## Scheduling note

Several of the above (5.1-5.5, 5.7, A.4, E.4, B.4, C.4, `card-shell` 5.3) are
all real-touch captures on the **same** coherent-shell opt-in image
(`k230-coherent-shell` / `.#sdImage-coherent`). A single board session that
boots that image once and runs `tools/capture-feature.py` for each in
sequence, in the order above, would avoid repeated flashing/booting. Task 5.8
(persistent boot-file selection) must run last, only after every other
coherent-shell capture in this list has passed, since it is the step that
makes that image the normal boot rather than a `switch-to-configuration test`
preview.
