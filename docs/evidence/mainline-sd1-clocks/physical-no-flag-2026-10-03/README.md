# Targeted SD1 clock ownership passes automatic restart

Root physically ran the inspected five-clock candidate on 2026-10-03 UTC
(October 2, America/Chicago), using `~/tmp/k230-mainline-probe-integration`,
branch `integrate/mainline-probe-path`, bounded base `65578ff2`. Root owned
the single board/UART reservation; no kernel build slot was used.

The [host build proof](../full-build-success-2026-10-03.json) identifies the
realized `9vdk79…` kernel, `5yqilsfy…` bundle and `9gdms…` console system.
The coordinator independently repeated bundle inspection. A fresh protected
normal identity check preceded the [staging operation](staging.json): eight
new store paths were imported with archive SHA verification, the matching
bundle was GC-rooted, and its four staged artifact hashes passed. The later
trial preflight verified registered validity of the complete 629-path system
closure and exact metadata. Normal profile, boot files and persistent boot
selection were unchanged.

```sh
python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal \
  --runtime-shutdown-trace \
  --bundle /nix/store/5yqilsfyj35jzrcqjjqilkr6sd47qlms-k230-mainline-drm-trial-boot-files \
  --manifest "$HOME/tmp/k230-mainline-sd1-board/candidate-manifest.json" \
  --normal-report "$HOME/tmp/k230-mainline-sd1-board/normal-report.json" \
  --log "$HOME/tmp/k230-mainline-sd1-board/minimal-uart.log" \
  --result "$HOME/tmp/k230-mainline-sd1-board/minimal-result.json"
```

Controller exit **0**: `recovery-verified-diagnostic-passed`.
The exact printed volatile arguments contained **no** `clk_ignore_unused`.
The candidate printed `clk: Disabling unused clocks` at 3.245763 seconds.
Fresh readiness/reception, true/proc/uptime and all six runtime tracing
stages passed, including the independent Y parameter readback.

The real reboot passed the previous MMC shutdown boundary and the remaining
devices. At 5.757050 seconds the candidate printed `reboot: Restarting system`,
then SPL and the normal system booted. Within the 180-second return window,
protected postflight verified a fresh normal boot ID, exact system/profile/
kernel/init, three active shell services and all eight boot hashes unchanged.
No operator reset or global clock bypass was needed.

[Result](minimal-result.json) preserves the controller facts, selected artifact
hashes, source identity and raw-log hash/timestamp; only the private raw-log
pathname was removed. The [curated console excerpt](minimal-console-excerpt.txt)
selects candidate shutdown and following SPL; raw normal-system output remains
private. This is physical serial proof, distinct from host builds or injected
input. No new photograph or real-finger acceptance was obtained for this
restart trial.

The earlier comparison established global cleanup dependence. This result
shows the targeted five-clock correction is sufficient for this candidate's
bounded restart trial with ordinary cleanup; it does not attribute failure
to one particular gate or prove all other hardware resources are complete.
Task 5d.4 now has no-bypass physical proof. Task **5b.5 remains open** for
ordinary NixOS root activation and deliberate touch; the initrd shell used
here is not a usable mainline system.

## Returned SD label check

After the protected minimal return, the operator ran the same explicit
bundle/manifest/normal-report command with `--mode label`, without clock
bypass or runtime tracing, and fresh `label-uart.log` / `label-result.json`
private paths. Controller exit **0**, `recovery-verified-diagnostic-passed`.
Fresh receipt, true/proc/uptime, devtmpfs setup and the expected block node
passed. The bounded read-only partition-label command returned RC0 and
matched `NIXOS_SD`. The single reboot returned through SPL to a fresh
protected normal boot; all identities/services/eight hashes passed.
[Result](label-result.json) and [excerpt](label-console-excerpt.txt) retain
that physical observation. This neither mounts the root nor activates init.

## Read-only mount reply interleaved with kernel logging

The same exact candidate was next run with `--mode root-mount`, fresh
`root-mount-uart.log` / `root-mount-result.json` private paths and the
post-label protected normal report. The controller exited **2**, unknown
at `root-mount mount`, and sent no subsequent probe or reboot input.
[Original failed result](root-mount-parser-stop.json) preserves that limit.

The private capture contains complete mount-reply fragments ending in RC0
and a fresh initrd shell prompt, but an EXT4 informational line splits the
nonce. The kernel reports a read-only mount without journal replay. This is
an interleaved protocol response, not proof of a hung mount. The original
strict parser did not accept it. A narrowly reviewed parser correction and
independent fresh mount-flag/lookups/unmount checks are required before
resuming recovery. Root activation, deliberate touch and recovery from this
specific stopped trial remain UNVERIFIED at this checkpoint.

The [ordinary-init/touch source plan](../../../research/mainline-init-touch-gates-2026-10-02.md)
records the separate full-boot procedure and profile-preserving trial guards.
It does not substitute for those physical gates.
