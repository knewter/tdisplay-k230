## 1. Pinned compositor capability audit

- [ ] 1.1 Resolve the exact pinned Sway and wlroots source paths used by `nix/shell.nix`, audit scene-surface creation/movement/clipping, seat touch dispatch, focus, xdg close, frame-done, and presentation hooks, and record source paths/line ranges in `docs/research/`; verify with `nix eval --raw .#nixosConfigurations.nixos.config.k230.shell.package` plus a source-path report.
- [ ] 1.2 Write the route decision and public interface contract (eligible surface, card ID, lifecycle, focus/touch ownership, close/refusal, format, completion, fallback) for the sibling `the-shell-manages-apps-as-cards` change; verify the contract names no dependency on `the-handheld-has-a-coherent-ux-plan` and no reverse dependency.
- [ ] 1.3 If the audit finds no safe compositor hook, record a source-cited negative result and leave the product card change blocked; verify `openspec validate the-shell-has-a-card-composition-plan --strict` still distinguishes a negative capability finding from feature delivery.

## 2. Opt-in compositor capability probe

- [ ] 2.1 Add an opt-in, source-built Sway patch/package and a two-test-app fixture that retains Sway as the only DRM/KMS owner and Pixman as renderer; verify a narrow `nix build .#<card-composition-probe> --max-jobs 1 --cores 8` succeeds without adding it to the default image.
- [ ] 2.2 Implement a compositor-owned scene probe that attaches two eligible live app surfaces, logs per-surface map/unmap/destroy and format/stride, and moves the selected card continuously from touch motion; verify host fixture tests cover stale surface destruction, disabled probe, and no second DRM open.
- [ ] 2.3 Implement selection/expand and dismissal request/refusal states, with explicit focus and keyboard restoration; verify a scripted Sway fixture tests selected, closed, refusal, and app-exit paths without orphaned card nodes.

## 3. Board capability evidence

- [ ] 3.1 With the coordinator as sole board operator, run the opt-in probe while the normal shell remains active and record app shrink, continuous drag, adjacent expand, dismissal request, and refusal/exit separately; verify `systemctl is-active shell seatd` and invocation IDs remain unchanged before/after.
- [ ] 3.2 Measure two-app scene CPU and memory deltas plus scene frame/presentation signals at 568x1232 RGB565/Pixman; verify a board transcript names renderer, format, buffer lifetime, damage/commit completion, sample count, and limits without calling it GPU or zero-copy proof.
- [ ] 3.3 Exercise fallback by disabling or aborting the probe and confirm Apps, keyboard, terminal, and existing Pixman session remain usable; verify a concise board capture and sanitized logs identify the fallback result.

## 4. Handoff and review

- [ ] 4.1 Publish the source audit, interface contract, probe evidence, and explicit result (feasible or blocked) for `the-shell-manages-apps-as-cards`; verify its implementation scope consumes only the recorded contract and does not infer unsupported live-card behavior.
- [ ] 4.2 Run `openspec validate the-shell-has-a-card-composition-plan --strict`, relevant host tests, `./tools/blob-scan.py --no-vendor`, and `python3 tools/work-status.py`; verify evidence media and source-built artifacts have named provenance before any default-shell proposal.
