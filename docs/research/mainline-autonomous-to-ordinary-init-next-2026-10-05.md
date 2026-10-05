# Next comparison: ordinary init on the current image

The [autonomous physical run](../evidence/mainline-autonomous-bash-pid1/physical-2026-10-05/README.md)
completed B/E and the interactive handoff with all optional reporter gates absent.
The next bounded step uses the existing ordinary controller and the same p2
bundle, selecting its archived systemd `/init` instead of Bash. This is within
the existing mainline task 5b.5; no new proposal, controller or kernel build is
needed. **This ordinary comparison has not been run.**

The earlier [ordinary attempt](../evidence/mainline-system-trial/physical-2026-10-03/README.md)
used the 5y bundle and reached systemd/udev without usable root. The
[marker-free attempt](../evidence/mainline-system-trial/marker-free-physical-2026-10-03/README.md)
used brmp and did not show systemd/login. Neither is an ordinary-init result for
the current p2 artifacts. Successful Bash execution does not overturn those
observations or prove a hardware cause.

Host source analysis of the selected 0l4 tree finds that
`drivers/soc/canaan/k230-uart-progress.c:224–243` returns before either
`kthread_run` when its enable gate is absent, and `init/main.c:1508–1511` returns
before optional trace output when its gate is absent. No runtime thread listing
or IRQ trace was collected. The selected system `/init` SHA256 is
`d3e109a270c0b4463ac5b7b0655ce7667d7c55f6f93341bb461300a5dd5c8c63`,
matching the archived systemd ELF in the existing host proof.

Pure policy generation was independently checked through
`ordinary_bootargs(..., wait_initramfs_in_initcall=True, without_boot_markers=True)`
and `volatile_bootargs_command`: 299 raw argument bytes and a 317-byte literal
U-Boot command, below the existing 512-byte bound. It retains the sole ttyS0
console, exact init/root, fsck skip, two service masks and `initramfs_async=0`.
It contains no `rdinit`, post-`--` script, reporter/trace, nohz or nohlt selection.
This is pure host policy evidence; fresh actual preparation remains required.

After a NEW reset and exact protected normal recovery, reserve board/UART and
run actual `system.prepare` with both selectors. Retain the same p2/24h/0l4
config/Image/source/archive/native artifact identities, five manifest/load/CRC
guards, systemd identity, diagnostic tools and registration-absence helper.
Historical normal reports do not replace that fresh recovery/preflight.

```sh
python3 tools/mainline-drm-system-trial.py begin \
  --wait-initramfs-in-initcall --without-boot-markers \
  --bundle /nix/store/p2kdar89q7dhwdajjy0mrhmxxzcgsalw-k230-mainline-drm-trial-boot-files \
  --manifest PRIVATE_MANIFEST --normal-report NEW_PRIVATE_NORMAL \
  --state NEW_PRIVATE_STATE --log NEW_PRIVATE_LOG --result NEW_PRIVATE_RESULT
```

The existing controller waits passively up to 180 seconds for fresh Linux,
autologin and a root prompt. A qualified prompt then allows its exact candidate
kernel/system/init/root/profile/boot/cmdline checks. No systemd output,
systemd/udev without login, and qualified stage-2 identity distinguish observed
boundaries; silence does not identify the stalled instruction or hardware cause.
Unknown readiness or boot/write/read completion preserves facts without further
input or recovery guesses. A successful begin retains the candidate for separate
panel/glass verification and guarded finish. A failed begin requires another
NEW operator reset. Task 5b.5 remains open until its named physical proof exists.
