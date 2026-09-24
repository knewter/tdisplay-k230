## 1. Normal kernel and renderer graph

- [ ] 1.1 Move the tested vector compiler probe and kernel configuration into the normal kernel derivation, retain a diagnostic trial alias, and verify the normal kernel with `nix build .#kernel --max-jobs 1 --cores 4 --no-link --print-out-paths` (host cross-build only).
- [ ] 1.2 Enable the tested runtime-gated Pixman RVV build in the normal package graph, verify one Pixman provider and a scalar disable control, and run `nix build .#shell-compositor --max-jobs 1 --cores 4 --no-link --print-out-paths` (host cross-build only).
- [ ] 1.3 Build and inspect the coherent normal kernel/modules/initrd/system closure with `nix build .#toplevel --max-jobs 1 --cores 4 --no-link --print-out-paths` (host cross-build only).

## 2. Useful extension inventory

- [ ] 2.1 Record a per-extension table from the pinned board DT, relevant stage 1 and kernel source/config, compiler/assembler support and physical runtime reports; explicitly classify privilege, version, selected userspace path and exclusions, then verify the table against the pinned source with `rg -n 'riscv,isa|riscv,isa-extensions' /nix/store/l6jdpbzp53y5n24ky6602f41gzs6f6ik-linux-xuantie-k230-rvv-src/arch/riscv/boot/dts/canaan/k230.dtsi` (source audit, not execution proof).
- [ ] 2.2 For each additional useful extension proposed for ordinary userspace, add a bounded targeted implementation and physical test or leave it explicitly UNVERIFIED; verify its host build with `nix build .#toplevel --max-jobs 1 --cores 4 --no-link --print-out-paths` (host cross-build only).

## 3. Candidate execution and recovery

- [ ] 3.1 Check a matching candidate image boots in emulation with `tools/qemu-k230.sh` and retain the console transcript with machine limits (QEMU proof only).
- [x] 3.2 Replace the fixed old trial identities in the pixel and card drivers with a validated candidate manifest covering system, kernel, probe, Pixman, package, executable and configuration; retain strict running-system and mapped-library guards, and test valid, stale and missing identity cases with `python3 tests/test_pixman_rvv_probe.py && python3 tests/test_card_shell_rvv_benchmark.py` (host guard proof).

  Host proof: `PIXMAN_SOURCE_TAR=/nix/store/s2cifkjf074cwcim1p9lij646fi3p3zy-pixman-0.46.4.tar.gz python3 tests/test_pixman_rvv_probe.py && python3 tests/test_card_shell_rvv_benchmark.py` passed 5 pixel/detector and 8 card tests. Temporary manifests and mocked board transport do not prove a candidate boot, physical vector dispatch, or card acceptance.
- [ ] 3.3 On the reserved physical board, verify candidate identities, stage a one-time candidate selection and run the vector context and 192-case pixel checks; preserve serial reports and exact commands in `docs/evidence/`; verify with `python3 tools/pixman-rvv-compare.py --board --manifest <matching-candidate-manifest> --package <matching-probe-path> --output <new-output>` after the matching candidate boot (physical proof).
- [ ] 3.4 On that candidate boot, record console, shell, Wi-Fi and representative one-/two-card results with unchanged acceptance and budget scripts; verify with `python3 tools/card-shell-rvv-benchmark.py --board --manifest <matching-candidate-manifest> --repeats 3 --revision <candidate-revision> --output <new-output>` (injected-input physical workload, not real-finger or optical proof).
- [ ] 3.5 Return to the preserved known-good persistent image, check protected hashes and root layout, shell and Wi-Fi, and record the actual recovery with `python3 tools/check-root-growth.py --board --phase repeat --helper <existing-helper-store-path> --target-system <known-good-system-store-path> --before <prior-after-evidence.json> --output <new-recovery-evidence.json>` (physical recovery proof).
- [ ] 3.6 After reviewing the recorded candidate and recovery results, select the proved image persistently and verify a fresh ordinary boot and exact `/run/current-system` identity with `python3 tools/console.py --wait=5 'readlink -f /run/current-system'` on the reserved board; leave this task unchecked if any physical gate fails (physical deployment proof).
