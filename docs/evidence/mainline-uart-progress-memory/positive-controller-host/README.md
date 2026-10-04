# Actual Memory controller host qualification

Actual matching Memory artifact preparation passed on 2026-10-04 from
`04:48:51.726195Z` to `04:48:52.602799Z`. This satisfies task 5i.4's positive host
preparation gate. New physical summary, receipt, recovery, ordinary root and touch
remain **UNVERIFIED**. No UART access, board command or implicit build was performed
by this qualifier.

Worktree `/home/jadams/tmp/k230-mainline-uart-progress-memory-controller`, branch
`mainline-uart-progress-memory-controller`, base `a4d6958d`, controller
`6fffac506a2d58b1b736b86de06ab8d1a485dbcf`. Owned for this handoff: this evidence
directory and only task 5i.4's completion note/checkbox. Root owns matching
builds, staging, board/UART and independent recovery. Cached start/handoff scans
are read-only host checks; no build-slot or board reservation was taken here.

The actual matching full-build receipt returned zero for frozen root revision
`7af8f7b8b5849c75df61d39ee772c2cc8f38542c`. The qualifier required that exact
revision, compared preparation-function and relevant-constant ASTs with its frozen
controller, then ran actual `prepare_trial` followed by
`prepare_uart_progress(..., uart_progress_memory=True)` using the guarded private
normal report and exact manifest. The source and functions were unchanged; earlier
[controller tests and old-artifact rejection](../controller/README.md) remain the
separate source/fixture evidence. No broad test rerun was needed for this handoff.

| Realized artifact | Store identity |
| --- | --- |
| Bundle | `/nix/store/lznjjfx1kzm8mp2j0r06c87h2vdymkhd-k230-mainline-drm-trial-boot-files` |
| System | `/nix/store/sja2fw7arlkkjws7ax7h1r2b9can7y8j-nixos-system-nixos-26.11.20260919.20b1ddd` |
| Kernel | `/nix/store/zk5rbsrgqgp40bk1314mj0i50qhn260m-linux-riscv64-unknown-linux-gnu-7.3.0-rc5` |
| Matching dev | `/nix/store/1pvqbm4r3gqcvsabgkz5wvrpxfbk5k1v-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-dev` |
| Source | `/nix/store/f7xg031sjb9dy3bswm5s3qjr9xwx1g02-linux-mainline-k230-uart-progress-memory-src` |

Read-only Nix queries tied the actual kernel and realized dev/config to the same
derivation. Each of the six required built-in config options was present exactly
once; full config SHA256 is
`52e7470b108ad094dbdf88b94e3e8838564edbda9e7a015b4279012e6765c9f1`.
Its derivation's immutable source contains the reviewed Memory worker SHA256
`307d7c0588499dd32826c1d05476e0bf6d46ca0c8939d42e0b4f7180545b98dc`.
The selected linked Image SHA256 is
`dd4466aae08927dd3eb7e2bcbc28c81d7279c341c52bd002ae67fcc04dde42af`.
The full NUL-terminated Memory summary format was unique at byte offset 25646120,
as was the exact Memory setup key. [result.json](result.json) records these proofs,
artifact SHA256/CRC values and actual archived executable/shared-loader checks.
Linked-string presence is host source/artifact evidence, not runtime output.

Actual preparation inspected the compressed selected initrd, U-Boot wrapper,
archived RISC-V Bash and original systemd ELF executables with shared interpreter,
manifest hashes and five load ranges. Archive metadata includes the base shell
comparison arguments; the top-level `bootargs` records the final selected Memory
policy. Protected wrapper size/hash comes from the guarded prior normal report
and fixed controller CRC; no new card readback was performed. Registration
absence is an assertion included in the pre/post helper, not a protected board
check performed during this host invocation.

Only `k230.uart_progress_memory=1` is added to the inherited qualified base
progress policy for this selected system. Breadcrumbs/PostSample gates are absent.
The full safe literal U-Boot command is 381 bytes versus 353 bytes without that
one gate. No variable expansion, duplicate init/control, saveenv, persistent
card/profile selection or new hardware DT setting is added by this controller.
It still requires fresh exact received arguments and Bash readiness before one
builtin receipt, followed only by passive capture. It never issues a candidate
reboot. Summary validity, worker completion, wait timeout, receipt and protected
normal return remain independent facts; a summary does not prove its final
firmware call returned or establish ordinary root acceptance.

Executed actual host command:

```sh
TMPDIR=$HOME/tmp python3 "$HOME/tmp/k230-mainline-uart-memory-host-qualification/qualify.py"
```

[qualification-command.py](qualification-command.py) preserves the exact executed
runner, SHA256
`a3c9fc004aef4a642cccc125b40b8e9345180d8c44c40adad10aeebc8e8eb1e9`.
It requires the protected expected-revision file and fresh outputs. Reexecution
belongs in a new protected `~/tmp` directory, never this public evidence directory.
Private baseline/prepared-state/transport files were not copied into the repo.

The matching private manifest is ready for root review/copy from
`~/tmp/k230-mainline-uart-memory-host-qualification/candidate-manifest.json`,
SHA256 `f6107dfefa6808b7f4840fc315466f892386c138f53da2bef985333ed68487ba`.
Root must use fresh private run/log/result paths and repeat protected normal
preflight/load CRC guards. After exact object/full artifact/controller gates and
NEW independently verified protected normal recovery, the sole root operator may
reserve board/UART and use:

```sh
python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal \
  --same-image-shell-pid1 --uart-progress --uart-progress-memory \
  --bundle /nix/store/lznjjfx1kzm8mp2j0r06c87h2vdymkhd-k230-mainline-drm-trial-boot-files \
  --manifest PRIVATE_MANIFEST --normal-report PRIVATE_NORMAL \
  --log PRIVATE_FRESH_LOG --result PRIVATE_FRESH_RESULT
```

Physical tasks 5i.5–6 and task 5b.5 remain open. This host receipt is not staging,
deployment, physical scheduling/RX proof or a normal-return observation.
