## 1. Decisions and interaction contract

- [x] 1.1 Land and review the composition-boundary decision from `the-shell-has-a-card-composition-plan`; record the chosen owner, live-surface eligibility, input/focus handoff, privacy behavior, and failure boundary in this change before implementing live capture or composition; verify with `openspec validate the-shell-has-a-card-composition-plan --strict` and review its committed evidence.
- [x] 1.2 Read the landed and archived `the-handheld-has-a-coherent-ux-plan` findings and record the accepted card hierarchy, direct-manipulation behavior, and throw-close feedback in this change; verify the resulting interaction contract with `openspec validate docs/handheld-ux-plan --type spec --strict` and the committed coordinator review in `docs/research/handheld-ux/design-review.md`. This does not wait for all audit successor changes.

## 2. Card state and recovery model

- [ ] 2.1 Implement a host-testable card-deck state model for enter, shrink, horizontal drag, release/expand, unavailable/private state, graceful-close request, refusal, timeout, and restore; verify with the proposed-to-create `python3 tests/test_card_shell_state.py`.
- [ ] 2.2 Implement global edge-gesture entry from an arbitrary eligible running application and a persistent button entry/recovery route, while retaining Apps, Windows/Home, Keyboard, System, Help, terminal, monitor, and Back semantics; verify with the proposed-to-create `python3 tests/test_card_shell_recovery.py` plus existing `python3 tests/test_touch_menu.py`.

## 3. Selected live composition boundary

- [ ] 3.1 Implement the live-content source and card compositor chosen by task 1.1, including explicit eligibility and a non-live private/unavailable card; verify with the proposed-to-create `python3 tests/test_card_shell_composition.py` using eligible and denied fixture surfaces.
- [ ] 3.2 Implement direct finger-following deck movement, tap-to-expand, and upward graceful-close request with bounded refusal/timeout recovery; verify with the proposed-to-create `python3 tests/test_card_shell_gestures.py` and native test surface traces.
- [ ] 3.3 Package only the chosen userspace component and its declared dependencies; verify the proposed-to-create narrow derivation with `nix build .#card-shell` and record its closure difference from the current system.

## 4. Cost decision

- [ ] 4.1 Declare card interaction frame/update, input-to-visible-update, and incremental-memory budgets before acceptance; implement the proposed-to-create `tools/card-shell-benchmark.py` and verify its parser with `python3 tools/card-shell-benchmark.py --self-test`.
- [ ] 4.2 Measure the default Pixman composition path at 568x1232 RGB565 with one and multiple eligible cards; verify on hardware with the proposed-to-create `python3 tools/card-shell-benchmark.py --board --output docs/evidence/card-shell/pixman.json`. Record a reduced-refresh behavior or independently measured optimization only when every required core card interaction remains live and direct; otherwise leave this change open or request explicit authorization for a successor.
- [ ] 4.3 Decide and record whether to pursue the optional VGLite path. If pursued, measure it against the same workload without making it a prerequisite for Pixman acceptance; verify with the proposed-to-create `python3 tools/card-shell-benchmark.py --board --renderer vglite --output docs/evidence/card-shell/vglite.json`. If not pursued, record that decision in the Pixman evidence so this optional path does not remain an archive gate.

## 5. Integration and board acceptance

- [ ] 5.1 Add the `--card-shell-smoke` mode to the existing `tools/qemu-k230.sh`, then build the selected component and integrate it into a system image only after host tests pass; verify the system closure with `nix build .#nixosConfigurations.k230.config.system.build.toplevel` and run `tools/qemu-k230.sh --card-shell-smoke`. QEMU does not prove panel, touch, or live presentation.
- [ ] 5.2 On the physical board, record native captures and injected-touch evidence for two eligible cards, horizontal deck movement, tap-to-expand, unavailable/private state, close refusal, timeout recovery, and every persistent control route; verify with the proposed-to-create `python3 tools/card-shell-acceptance.py --execute --provenance injected-touch --output docs/evidence/card-shell/injected`.
- [ ] 5.3 On the physical board, capture a focused real-finger trial of shrink, horizontal deck drag, expand, upward throw, and recovery; verify with `python3 tools/capture-feature.py card-shell --provenance real-touch --duration 30 --description 'Real-finger card entry, drag, expand, close and recovery' --output-dir docs/evidence/card-shell/real-touch` plus a committed audit that distinguishes camera visibility from native state evidence.

## 6. Proposal validation

- [ ] 6.1 Validate this change and preserve all unresolved hardware requirements as unverified until their named evidence exists; verify with `openspec validate the-shell-manages-apps-as-cards --strict`.
