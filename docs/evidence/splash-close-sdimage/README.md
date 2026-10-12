# Task 6.1 host proof: `.#sdImage` with `panelConsole = true`

Host evidence only (laptop claim). No board was touched, nothing was flashed,
and no physical or QEMU result is claimed. Base revision `4f1558ed`, worktree
`k230-splash-close`, 2026-10-12.

`.#sdImage` today builds `k230-mainline-drm-shell` (`flake.nix:844-848`),
which extends the coherent shell and inherits `k230.panelConsole = true`
(`flake.nix:130-134`), so no configuration was flipped to produce it.

Commands:

```sh
flock /tmp/k230-nix-build.lock nix build .#sdImage \
  --out-link /home/jadams/tmp/k230-splash-close-sdimage --max-jobs 1 --cores 4
# exit 0 -> /nix/store/y35kzw56nrdzdliz1i8234kmjqim66xd-k230-sd-image.img
python3 docs/evidence/splash-close-sdimage/inspect-image.py \
  /home/jadams/tmp/k230-splash-close-sdimage > inspect.json
docs/evidence/splash-close-sdimage/evaluate.sh > both-states.json
```

- [inspect.json](inspect.json): the boot partition (sfdisk partition 1, offset
  4194304, 112 MiB), read without root through `debugfs`, lists `Image`,
  `bootargs.txt`, `force_dtb`, `fw_jump_add_uboot_head.bin`, `hdmi_dtb`,
  `initrd.uimg`, `k230-tdisplay.dtb`, `lcd_dtb`. `stat /logo.xrgb` reports
  `File not found`. `bootargs.txt` begins `console=tty0`.
- [both-states.json](both-states.json): `drvPath` of the toplevel evaluates
  with the option true (`console=tty0` in `kernelParams`) and with it forced
  false (`console=tty0` absent).

Limits: the false-state `sdImage` was not built here, so "false puts
`logo.xrgb` on the partition" is source-read (`nix/sd-image.nix:86-88`) and
was previously inspected for the vendor splash image in
`../splash-preserve-trial/image-contents.txt`. This is a host inspection of an
image artifact, not a flashed-card readback and not a physical boot.
