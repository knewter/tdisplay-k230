# Daily shell image build — 3f397a6

This is the original build-host record. The image was subsequently deployed;
[launcher evidence](shell-features/desktop-launcher/README.md) records its fresh
boot and application checks.

## Source and command

- Source: `3f397a66f6e5cfeedbc13d49b289e574157ce962` (`3f397a6`, detached
  clean worktree).
- Command: `nix build .#sdImage --out-link resultdaily --option substituters
  https://cache.nixos.org/ --option max-jobs 1 --option cores 8
  --print-build-logs`.
- Result: exit status 0. Nix reported 22 derivations built. The foreground
  build session took about 82 seconds.

## Output

- Image: `/nix/store/x0qz7ibmyb1bbmx1cpwgryxapkzisb0m-k230-sd-image.img`
- Image size: `2308689920` bytes.
- Full SHA-256:
  `797d3fdf1e9901c6cf5d219a75c902e0cae12b951c9582514042535837d4b0a6`.
- Toplevel:
  `/nix/store/mp5llx58dcpnikfdwn455pyrygdvggbg-nixos-system-nixos-26.11.20260919.20b1ddd`.
- Closure of the **image output**, including the image file: `3590915736` bytes.
- System toplevel closure: `1280743192` bytes (`nix path-info -S`), separate
  from the image-output closure above.

The generated MBR has a 112 MiB boot partition at sectors `8192..237567` and
the root partition at sectors `262144..4507111`. Extracting the boot partition
and listing it with read-only `debugfs` found `Image`, `initrd.uimg`, the DTB,
and OpenSBI, and found no `logo.xrgb`. This matches the daily
`panelConsole = true` no-logo workaround; it is not a display claim.

## Stage 1 and handoff ABI

- Stage 1: `/nix/store/r7lvl2ddpm86p8cly5gcrnil58biyzsa-k230-stage1`.
- `fn_u-boot-spl.bin`:
  `fe3d537f62c34a3d01127c58fef4caec50f0e65b0192670712ecb1599584a954`.
- `fn_ug_u-boot.bin`:
  `e0b5787f3e68267f997ca61d45afaf8945e6fe9be775cc6165f981978cf3f1bb`.
- `env.env`:
  `cf108755a3cf3a8070a2f0ded84af672108e2301dfd58e5c2aa6a7555dbbd352`.
- `fw_jump.bin`:
  `74d08f8701dc72ea166d74be62fc3e5bff437d7c73ab68ad2f113cab289c38f9`.
- `fw_jump_add_uboot_head.bin`:
  `9627edbeea9b115d7040beea27cc61b23b6aca61cd502fd7760d7ee179f42c99`.

The source-built U-Boot output is
`/nix/store/zzz867rp8drrwkhibj0rlqc04sk9g7f8-uboot-k230_canmv_v3_defconfig-riscv64-unknown-linux-gnu-2022.10`.
`strings u-boot` finds `canaan,stage1-splash`, confirming that the 0005
runtime-handoff property is present in this build. The property can only be
validated on a board when a successful stage-1 splash path reaches Linux.

## Routine flashing policy

On 2026-09-22 the user requested that routine flashes stop repeating full
image readback now that the path has repeatedly passed it. `tools/ums-session.py`
therefore defaults to checking write completion and normal Linux return;
`--full-readback` explicitly enables the full device comparison for diagnosis.
Target identification and card-size checks still run before a write.
For this deployment, the write succeeded and the already-running comparison
was intentionally interrupted at the user's request. The subsequent boot
is recorded separately; this attempt is not labeled a readback pass.
