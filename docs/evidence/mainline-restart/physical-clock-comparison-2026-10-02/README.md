# Automatic mainline restart passes with unused-clock cleanup skipped

On 2026-10-02 the operator pressed the reset button after the preceding
traced shutdown timeout. Protected [manual recovery](../physical-runtime-ready-2026-10-02/postflight.json)
passed before this trial. Root ran the reviewed `9cd4a3f8` controller in
`~/tmp/k230-mainline-probe-integration`, branch `integrate/mainline-probe-path`,
bounded base `9cd4a3f8`, holding the single board/UART reservation.
No build slot, flash, protected boot-file/profile change or persistent
boot-selection write was used.

```sh
python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal \
  --runtime-shutdown-trace --ignore-unused-clocks \
  --bundle /nix/store/asj7l4zj5jrjkgng4nrcx3y72p7jf7aa-k230-mainline-drm-trial-boot-files \
  --manifest "$HOME/tmp/k230-mainline-restart-board/candidate-manifest.json" \
  --normal-report "$HOME/tmp/k230-mainline-restart-board/normal-report.json" \
  --log "$HOME/tmp/k230-mainline-restart-board/runtime-clock-20261002T195123Z-uart.log" \
  --result "$HOME/tmp/k230-mainline-restart-board/runtime-clock-20261002T195123Z-result.json"
```

The controller exited **0**, `recovery-verified-diagnostic-passed`.
Matching artifact count/CRC and exact volatile bootargs checks passed.
The candidate printed `clk: Not disabling unused clocks`, independently
confirming the argument affected kernel cleanup. Candidate readiness,
fresh receipt, true/proc/uptime and all six runtime tracing stages passed;
the parameter's independent Y readback passed before the one reboot request.

The shutdown log passed the preceding MMC block-device boundary and all
remaining devices. At 5.756131 seconds the candidate printed
`reboot: Restarting system`, followed by **U-Boot SPL** and the normal boot.
Within the bounded 180-second return window, protected postflight verified
a fresh normal boot ID, exact system/profile/kernel/init, all three shell
services active and all eight protected hashes unchanged. No operator reset
or further trial was needed for this automatic return.

[Result](result.json) is the controller-generated record with only its private
raw-log pathname removed, plus explicit source/hash/timestamp/observation
fields. [Console excerpt](console-excerpt.txt) selects candidate shutdown
and subsequent SPL lines; raw normal output stays private. The selected
bundle and system are the same `asj…` / `v9qc…` artifacts as the
[failed baseline](../physical-runtime-ready-2026-10-02/README.md).
Its matching artifact hashes remain recorded there and in the parent
[restart evidence](../README.md).

After serial postflight, the normal shell's Home IPC completed with exit 0.
The [reviewed camera still](recovered-home-panel.jpg) shows normal Home;
[provenance](camera.json) records crop, source time/hash and glare/angle/blur
limits. It is not a mainline shell or a new real-finger acceptance claim.

This completes task **5d.4's automatic restart proof for this explicitly
qualified diagnostic boot**. The baseline without `clk_ignore_unused` still
failed its return deadline. The comparison demonstrates dependence on
global unused-clock cleanup; it does not identify one clock or prove the
MMC callback caused the stall. Permanent global clock bypass is not enabled.
The next source fix must claim the K230 SD1 clocks required by its binding,
then independently repeat restart and usable-root probes without the flag.
Task **5b.5**, usable mainline root and deliberate touch, remains
**UNVERIFIED** and open. The change cannot be archived yet.
