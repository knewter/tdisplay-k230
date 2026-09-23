## 1. Reconcile opt-in builds and diagnostic proof

Existing successful commands may be reused only after reviewing their committed source/artifact provenance. These tasks claim host or full-system guest proof, never physical vector execution.

- [x] 1.1 Reconcile the optional compiler-probe correction and enabled vector configuration against the recorded kernel build; verify `nix build .#kernel-rvv-trial --no-link --print-out-paths` and cite the inspected configuration in `docs/evidence/card-shell/kernel-rvv/`.
- [x] 1.2 Reconcile scalar runtime gating and the optional Pixman build; verify `PIXMAN_SOURCE_TAR=/nix/store/s2cifkjf074cwcim1p9lij646fi3p3zy-pixman-0.46.4.tar.gz python3 tests/test_pixman_rvv_probe.py` and `nix build .#pixman-rvv --no-link --print-out-paths`, retaining the normal-board no-vector result.
- [x] 1.3 Verify the matching system includes the trial kernel, external Wi-Fi module, initrd, context diagnostic and root-growth service using `nix build .#nixosConfigurations.k230-rvv-trial.config.system.build.toplevel --no-link --print-out-paths`; record the immutable system path.
- [x] 1.4 Verify the matching image and extracted boot artifacts using `nix build .#sdImage-rvv-trial --no-link --print-out-paths`; record actual image/kernel hashes, wrapped-initrd payload/CRCs and matching bootargs selection.
- [x] 1.5 Reconcile the bounded diagnostic's full Linux guest cases: V absent safely skips, VLEN 128 and 256 pass signal/preemption checks, and deliberate corruption fails as expected. Verify the exact `python3 tools/rvv-context-qemu.py --package PROBE --corrupt-package CORRUPT_PROBE --kernel GUEST_KERNEL --output NEW_OUTPUT` invocation and artifacts recorded in `docs/evidence/card-shell/kernel-rvv/context-probe/README.md` and `result.json`.

## 2. Prove recoverable physical vector execution

Reserve the board and keep raw console output private until selecting secret-free evidence. Each capture uses a new output path. `HOST_TRIAL_MANIFEST` binds the inspected trial artifacts to the committed normal-system baseline. A failed gate remains open; do not force vector instructions.

- [x] 2.1 Verify the guarded loader's host rejection cases with `python3 tests/test_rvv_board_boot.py`, then load all five physical artifacts with matching lengths/CRCs and return to normal using `python3 tools/rvv-board-boot.py --manifest HOST_TRIAL_MANIFEST --private-log PRIVATE_LOG --output NEW_LOAD_JSON`. Commit the load observation and separate normal shell/Wi-Fi recovery capture.
- [x] 2.2 Boot the matching trial once with `python3 tools/rvv-board-boot.py --manifest HOST_TRIAL_MANIFEST --private-log PRIVATE_LOG --output NEW_BOOT_JSON --boot`; commit the observed boot and running-system/configuration identity. A login by itself does not complete the identity check.
- [x] 2.3 On that verified trial, capture scalar hwprobe and require both physical diagnostic processes to pass vector arithmetic, asynchronous signals and scheduling. Verify the bounded immutable probe via `flock /tmp/k230-board.lock python3 tools/console.py --wait=20 'timeout --kill-after=3s 15s /nix/store/4gn2z5fi5szrnflhzjsr1kq3f1b39wqx-k230-rvv-context-probe-riscv64-unknown-linux-gnu-0.1/bin/k230-rvv-context-probe'`; commit JSON, exit status and provenance. SKIP, timeout or FAIL does not satisfy this gate.
- [x] 2.4 Return to normal and verify fresh boot identity, protected boot/firmware hashes, root layout, shell/seatd and Wi-Fi HTTPS recovery with `python3 tools/check-root-growth.py --board --phase repeat --helper /nix/store/6sca423wcjlq1v9ynjpbv4ai48jf53l9-k230-root-growth --target-system /nix/store/gnr36q39hmy4pq7ipwac1r1rpfbyqxd4-nixos-system-nixos-26.11.20260919.20b1ddd --before docs/evidence/storage-capacity/board-after.json --output NEW_RECOVERY_JSON`. Record whether recovery needed physical intervention and retain failures.

## 3. Establish physical pixel correctness

Requires 2.3 PASS. Proposed commands in this section must be implemented before invocation; their names are intended interfaces, not claims that tools already exist.

- [ ] 3.1 Add a narrow, capability-gated Pixman comparison covering declared RGB565/ARGB copy, blend and scale cases including stride/edge conditions; verify scalar reference equality and a deliberately corrupted-output rejection on the physical trial using the proposed `python3 tools/pixman-rvv-compare.py --board --output NEW_PIXEL_OUTPUT`. Commit cases, exact library identities, actual dispatch evidence and results.
- [ ] 3.2 Package the opt-in card compositor with the verified vector Pixman, preserving the normal renderer and image. Verify the proposed `nix build .#card-shell-rvv --no-link --print-out-paths` and record its dependency/dispatch identity; this build is host proof only.

## 4. Measure and publish the decision

Requires physical context and pixel correctness. The comparison must use the same trial kernel, scene, panel format, input sequence and measurement producer. Keep native capture, injected input and real-glass observations distinct.

- [ ] 4.1 Add and run a bounded paired workload driver, proposed `python3 tools/card-shell-rvv-benchmark.py --board --repeats 3 --output NEW_BENCHMARK_OUTPUT`, measuring identical live-card interactions with vector dispatch on/off. Commit each run's frame/update timing, input latency, CPU and memory costs, producer/artifact identity and comparison against unchanged card budgets.
- [ ] 4.2 Record the measured decision, including negative results and remaining compatibility limits, in `docs/evidence/card-shell/kernel-rvv/`; restore and reverify the normal system using the recovery command in 2.4 after the final rendering trial. A successful experiment does not promote the default image; any promotion requires a separate reviewed proposal.
- [ ] 4.3 Publish the evidence and proposal status without claiming unperformed proof; validate with `openspec validate the-system-trials-cpu-vector-acceleration --strict` and `python3 scripts/build_site.py`, then verify the pushed revision's CI and published site. Archive only after every task and physical evidence gate is complete.

Physical tasks 2.2–2.4: `docs/evidence/card-shell/kernel-rvv/board-trial/README.md`
links the actual one-time boot, verified running-system/configuration identity,
scalar capability report, two-process context PASS and separate normal-recovery
capture. The committed capture script invokes the bounded command in 2.3; this
is physical-board evidence, not the earlier generic Linux guest result.
