## 1. Guarded system growth

- [ ] 1.1 Implement a narrowly packaged root-layout guard and two-phase growth helper using pinned partition/ext4 tools; verify supported layout, wrong device/label/filesystem, later partition, full card and failed-tool decisions with the proposed `python3 tests/test_root_growth.py` and `nix build .#root-growth --no-link --print-out-paths`. Host policy/build proof only.
- [ ] 1.2 Integrate a finitely bounded, repeatable NixOS boot service that gates both mutation phases and leaves the existing root/shell usable on growth failure; verify selected tools, target derivation, ordering and default-image inclusion with the proposed `python3 tools/check-root-growth-config.py`. Keep QEMU's unrelated netboot root outside board growth selection.

Narrow host proof: `python3 tests/test_root_growth.py`, `nix build .#root-growth --no-link --print-out-paths`, and `python3 tools/check-root-growth-config.py`. These do not prove real filesystem mutation.

## 2. Disposable-media preservation

- [ ] 2.1 Add and run an isolated system-QEMU fixture against actual sparse disk images; verify first expansion, repeat no-op, an already-full disk, unsupported root identity/filesystem, a later partition, injected tool failure and retry after partition-only growth with the proposed `python3 tools/test-root-growth.py --qemu --output docs/evidence/storage-capacity/qemu`. Assert protected firmware/boot hashes, root start/identity, root-file sentinels, increased capacity and no writes on refusal. Record exact guest/tool artifacts and keep failed runs.
- [ ] 2.2 Build the integrated board system and compact image after those checks pass; verify with `nix build .#nixosConfigurations.k230.config.system.build.toplevel --no-link --print-out-paths` followed by `nix build .#sdImage --no-link --print-out-paths`, recording image/system identities and unchanged initial boot/root offsets. This proves build/layout, not physical expansion.

Proof: `python3 tools/test-root-growth.py --qemu --output docs/evidence/storage-capacity/qemu`, then the two narrow system/image builds above. QEMU is not K230 boot proof.

## 3. Board boot and repeatability

- [ ] 3.1 Preserve a known recovery artifact and record the actual compact starting layout, mounted root identity, available bytes and selected firmware/boot/root-sentinel hashes before the board trial; verify with the proposed `python3 tools/check-root-growth.py --board --phase before --output docs/evidence/storage-capacity/board-before.json`. Reserve board/serial and retain the existing protected credential procedure. No routine whole-image flash readback is required.
- [ ] 3.2 Boot the integrated image on the physical larger card and verify increased usable capacity, unchanged protected boot data/root identity, existing sentinel contents, normal shell and Wi-Fi recovery; use the proposed `python3 tools/check-root-growth.py --board --phase after --before docs/evidence/storage-capacity/board-before.json --output docs/evidence/storage-capacity/board-after.json` and commit the actual serial growth/boot observations. A manual resize alone does not satisfy this task.
- [ ] 3.3 Reboot again and prove idempotence, stable partition boundaries and normal shell return using the same board checker with `--phase repeat --before docs/evidence/storage-capacity/board-after.json --output docs/evidence/storage-capacity/board-repeat.json`. Keep this open until the physical second boot exists.

Physical proof: the named `tools/check-root-growth.py --board` captures plus serial boot logs; host/QEMU output cannot close group 3.

## 4. Review and publication

- [ ] 4.1 Document compact image versus expanded runtime layout, refusal/recovery behavior, artifacts and every evidence limit; verify `openspec validate the-system-uses-the-card-space --strict`, `python3 scripts/build_site.py`, and `python3 tools/blob-scan.py --no-vendor`, then merge/push and inspect the deployed spec URL. Archive only after every preceding task and physical proof is complete.

Proof: the three commands above and the published URL for the landed revision. Proposal publication alone is not a shipped expansion capability.
