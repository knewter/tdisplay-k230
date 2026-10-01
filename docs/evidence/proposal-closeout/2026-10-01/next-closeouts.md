# Next closeouts, 2026-10-01

Inspected committed source `568c400bf36791ff1f9d5524a6c23350a7b96f7e`, active task lists and earlier operator acceptance. This is a closeout audit, not a new implementation or physical test. There are **31 active and 46 archived changes**. Sixteen archives are dated 2026-10-01. No active task list is entirely complete. The public work snapshot at this revision has passed CI/deployment and all 77 rendered card IDs match the committed generator order.

## Shortest path to another archive

### Live application card UI — 11/14

`the-shell-manages-apps-as-cards` has three open tasks:

| Task | Actual remaining scope | Proposed disposition |
| --- | --- | --- |
| 4.2 | Measured frame/CPU budgets still fail; acceptance decision remains open | Keep the original requirement and all failed measurements in `the-card-deck-still-misses-its-frame-budget` |
| 5.1 | Full integrated configuration and non-fixture QEMU smoke | Keep this unperformed proof in that same successor's existing task 5.1 |
| 5.3 | Functional real-glass card acceptance/capture | Reconcile the operator's prior ordinary-card/composition acceptance; honor their explicit waiver of difficult extra captures, without inventing a new recording or per-case result |

The successor already exists and already records both unfinished tasks. However, its current proposal explicitly retains parent ownership until its budget decision resolves. Archiving the functional parent earlier changes that closure boundary and needs the operator's explicit scope decision under AGENTS.md. If approved, revise both artifacts coherently, commit the acceptance/ownership record, retain the known failed-budget status, validate and archive/sync the functional parent. Do not mark budget or QEMU tests passed. No image flash is needed to make this ownership decision.

### Pinned Home — 19/25

`the-shell-presents-a-pinned-home-screen` combines delivered page/grid/dock work with a later GNOME-style app-window action request. Its six remaining tasks are physical Home acceptance (8.1) and all five group-11 implementation/integration tasks. Primary tap/focus plus secondary-click or long-press New Window is **not fully implemented** merely because best-effort focus matching exists.

For a separate baseline Home archive, first get an explicit split decision, preserve every group-11 requirement/task in a committed successor and reconcile the original Home placement gate. Prior operator feedback specifically reported drawer-to-Home auto-positioning instead of the intended drop cell; later widget/page proof is relevant, but do not silently equate that with a complete per-case Home acceptance. The useful short check is: page swipe, drop an app into a deliberately chosen cell, move/remove it, then tap the dock. Existing folder/widget archives are already closed and need no repeat.

Alternatively implement group 11 and close the complete parent afterward. That is bounded new source work, not just paperwork.

## Next implementation candidates that can produce real closes

| Change | Why it is a useful target | Work needed before archive |
| --- | --- | --- |
| `the-launcher-explains-app-actions` (2/4) | Only two original tasks remain | Its completed curation code is in the C rollback launcher, while the current Rust catalog independently scans desktop entries. Reconcile/port the intended names, endpoint suppression and safe failed-launch recovery to the actual session; build the affected target and obtain the short discovery/failure interaction proof. Building the old C launcher alone does not establish the Rust feature. |
| `the-settings-and-notifications-surfaces-are-themed` (0/8) | The real Rust Settings/shade paint and authored theme brush work already exist | Reconcile helper-vs-renderer ownership, formally cover every claimed role and compatibility status in host tests, then capture dark/light Settings and notifications plus rollback on the same installed candidate. It is a smaller complete theme scope than the 81-task picker parent. |
| `the-shell-presents-a-pinned-home-screen` | Functional Home is delivered, app-window menu policy is clearly bounded | Finish or explicitly separate group 11, then use the short Home acceptance sequence above. |

The next shared device step is a build/install of the combined picker and visual-polish source, followed by one short dark/light Home, drawer, Settings and shade pass. It can supply relevant evidence to several scopes, but each task must still name what that pass actually proves. Current combined source passed 420 library tests, nine trace tests and blob inventory checks; independent component cross-builds and the injected picker comparison are committed. **Combined device installation is still open.**

## Counts that must not be read as easy archives

- Mainline is 29/30, but the remaining physical usable-root/display-power-domain boot gate failed. Host provider builds and restoring the normal vendor boot do not pass it.
- HDMI gestures/trackpad are accepted and their own proposals are archived. The remaining HDMI proposals still include rotated performance budgets, live output switching or unfinished density/subpage reflow; those are different scopes.
- The picker is 64/81: source and measured improvement landed, but release-curve correction, combined installation, additional attribution coverage and finger feel remain. It is not a one-check archive.
- Normal coherent boot selection is 1/7. Matching bundle/inspector/controller and ordinary persistent boot proof are an important unblocker, not completed work.
- SMP, heartbeat, Bluetooth hardware and speaker/add-on work are not quick user-feedback closes. Audio's headphone listening check stays in the audio proposal; no add-on is assumed.

## Already closed today

App launch splash; app drawer redesign; ordinary cards including video; reboot clock; render-ahead/bottom flicker; Wi-Fi Settings; volume; Home widgets/folders; fluid Home pages/widgets; repeatable GitHub release; keyboard gestures; coherent behavior; card composition plan; mouse navigation; HDMI trackpad; spec-site closeout grounding.

Sources: the named `openspec/changes/*/tasks.md`, existing `docs/evidence/proposal-closeout/2026-09-30/operator-feedback.md`, `2026-10-01/ordinary-cards.md`, card frame-budget artifacts and current Rust `catalog.rs`. No board action, camera capture or new performance measurement occurred for this audit.
