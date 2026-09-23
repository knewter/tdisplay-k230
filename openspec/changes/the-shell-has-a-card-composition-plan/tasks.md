## 1. Pinned architecture decision

- [x] 1.1 Create `tools/audit-card-composition-sources.py` to resolve and report derivation/source inputs for `.#shell-compositor` and `.#touch-launcher`, then audit client protocol, Sway seat/container, and wlroots scene/frame/presentation hooks; verify `nix path-info --derivation .#shell-compositor .#touch-launcher`, `python3 tools/audit-card-composition-sources.py --flake . --output docs/research/card-composition-source-audit.md`, and `python3 tests/test_card_composition_source_audit.py`.
- [x] 1.2 Compare whether an existing protocol-client route can provide live surfaces plus global touch/focus with whether a narrow Sway patch can, and publish the selected route or source-cited negative finding and interface contract; verify `python3 tests/test_card_composition_contract.py docs/research/card-composition-architecture.md` checks lifecycle/fallback fields and no dependency on `the-handheld-has-a-coherent-ux-plan`.
- [ ] 1.3 On a negative finding, record product delivery as blocked and mark tasks 2–3 not pursued rather than successful; verify `openspec validate the-shell-has-a-card-composition-plan --strict` and handoff distinguish investigation completion from card-feature delivery.

## 2. Conditional selected-route probe

- [ ] 2.1 If task 1 selects a client route, add the proposed `.#card-composition-probe` package exposing `bin/card-composition-probe`; if it selects Sway, expose the same executable and attribute using a source-built opt-in Sway package; verify `nix build .#card-composition-probe --max-jobs 1 --cores 8` and `python3 tests/test_card_composition_probe.py --mode selected` without adding either route to the default image.
- [ ] 2.2 Implement the selected route's two-app live-surface scene and continuous touch motion with map/unmap/destroy, format/stride, and buffer-release logs; verify `python3 tests/test_card_composition_probe.py --case two-app-drag --case stale-destroy --case disabled` and source checks show no DRM node open.
- [ ] 2.3 Implement selected/expand and dismissal request/refusal/exit behavior with focus and keyboard restoration; verify `python3 tests/test_card_composition_probe.py --case select --case close-refused --case app-exit --case keyboard-return` leaves no scene node or focus orphan.

## 3. Coordinator-reserved board evidence

- [ ] 3.1 If and only if task 1 selected a viable route, create `tools/card-composition-board-session.sh` with `--probe`, `--restore-shell`, `--collect`, and `--verify-restored` modes. For a client route it keeps normal Sway as sole DRM owner; for a Sway route it stops normal `shell`, runs the opt-in session as sole DRM owner, and restores the known normal shell in cleanup. Verify with `probe_path=$(nix build --no-link --print-out-paths .#card-composition-probe)` followed by `tools/card-composition-board-session.sh --probe "$probe_path/bin/card-composition-probe" --restore-shell`, recording session ownership with no concurrent DRM owners.
- [ ] 3.2 In that reserved session, record two app surfaces, shrink, continuous drag, adjacent expand, dismissal request, and refusal or exit; verify `tools/card-composition-board-session.sh --collect` writes sanitized evidence naming renderer, format, buffer lifetime, damage/commit and frame/presentation signals, process CPU, memory, and limits.
- [ ] 3.3 After restoration, verify Apps, keyboard, terminal, and normal Pixman session work; verify `systemctl is-active shell seatd`, a concise board capture, and `tools/card-composition-board-session.sh --verify-restored` pass. Do not require unchanged invocation IDs across planned stop/start.

## 4. Handoff and review

- [ ] 4.1 Publish the source audit, selected-route contract or negative block, and conditional probe evidence for `the-shell-manages-apps-as-cards`; verify its scope consumes only the published contract and makes no unsupported live-card claim.
- [ ] 4.2 Run `openspec validate the-shell-has-a-card-composition-plan --strict`, named host tests, `./tools/blob-scan.py --no-vendor`, and `python3 tools/work-status.py`; verify media and source-built artifacts have named provenance before any default-shell proposal.
