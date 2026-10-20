## 1. Source and cross-build

- [x] 1.1 Implement the narrow polling/cached-EDID guard and Nix wiring; verify the actual patched C72-case behavior and unchanged HPD/force/mode functions. Host proof: `python3 tools/test-hdmi-stable-poll.py --source /nix/store/7vzlvixrdhv5a1iw75p18yzwkaqrlxjd-linux-mainline-k230-drm-src`.
- [x] 1.2 Cross-build the actual configured candidate kernel and commit derivation/source/patch/output identities plus build result. Host proof under the heavy-build lock: `nix build .#nixosConfigurations.k230-mainline-drm-shell-landscape-hdmi.config.boot.kernelPackages.kernel`.
- [ ] 1.3 Cross-build the matching full candidate closure without changing landscape/default application settings; record installed artifacts separately from build success. Host proof: `nix build .#nixosConfigurations.k230-mainline-drm-shell-landscape-hdmi.config.system.build.toplevel`.

## 2. Board qualification and promotion

- [ ] 2.1 Reserve board, capture protected current boot/recovery state, preserve known-good bundle, stage candidate and obtain a fresh serial-observed boot with matching artifact/system/kernel identity and unchanged landscape/idle controls. Hardware proof: committed exact staging/boot invocation and transcript plus `python3 tools/console.py /dev/ttyACM0 --wait=3 "uname -r; readlink -f /run/current-system"`; source/build checks alone do not pass this gate.
- [ ] 2.2 Implement/test the fix-specific bounded recorder/report, then collect one untraced and one function-traced24-drag candidate workload with864 joins each and >=3 complete short polling cycles without EDID rereads. Proof: `python3 tools/hdmi-stable-poll-proof.py --self-test`, protected-SSH `--board-run` with explicit system/executable/source identities, and host `--report`; commit exact invocations, all tails, losses/clock/cleanup and old/candidate comparison limits.
- [ ] 2.3 Obtain fresh physical HDMI unplug/replug and real Overview-gesture observations on this candidate, recording cable-selected output, touch/trackpad behavior and retained landscape profile. Hardware-only proof: bounded protected runtime watcher plus timestamped operator/camera evidence; publish exact operator instructions before the action. Injected/sysfs events do not pass this gate.
- [ ] 2.4 After physical acceptance, promote the tested candidate persistently and verify its ordinary autoboot, installed hashes/system identity and restored normal controls. Hardware proof: committed exact promotion/serial boot command and runtime state; no promotion inferred from cross-build.
- [ ] 2.5 Remove owned diagnostics/temporary overrides, verify normal services/idle/image/output and release reservations. Hardware proof: timestamped final protected board query, owned trace/timer absence, preserved root tracing hashes and recorded build/board lease release.

## 3. Evidence and publication

- [ ] 3.1 Commit all named source/build/runtime/physical/persistent proof, remove only resolved UNVERIFIED markers, validate, land/push, verify successful CI and exact published revision. Proof: `openspec validate the-landscape-hdmi-shell-avoids-periodic-edid-stalls --strict`, `python3 tools/blob-scan.py --no-vendor`, and committed CI/HTTP evidence. Archive/sync the ADDED display/hdmi requirement only after all9tasks pass; retain every incomplete hardware gate otherwise.
