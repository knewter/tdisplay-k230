# Direct-SBI boundary diagnosis — matching full build

2026-10-03 UTC. Coordinator branch `integrate/mainline-probe-path`, worktree
`/home/jadams/tmp/k230-mainline-probe-integration`; bounded build source
`007410ee7daa55cecd4f59708e4941679a701f9d`. Root held
`/tmp/k230-nix-build.lock` during the full build and released it on completion.
This increment owns this evidence directory and the mainline task progress note.
No UART or board was used for these host checks.

```sh
flock -n /tmp/k230-nix-build.lock nix build \
  .#kernelMainlineBootTraceSbiTrialBootFiles --no-link --print-out-paths \
  --max-jobs 1 --cores 16
python3 tools/mainline-drm-trial-inspect.py \
  /nix/store/j0ad6h3s23s5zlwizn3mbiw6cs98s4qn-k230-mainline-drm-trial-boot-files
```

Both **passed**. Private log:
`~/tmp/k230-mainline-boot-trace-sbi-full-build.log`. Exact selected bundle,
system/kernel identities, file hashes and actual built configuration are in
[result.json](result.json). Image equality, initrd payload/header/data CRC,
DT-to-environment arguments, inventory presence and SHA256SUMS passed.
The hardware DT is identical to the previous trace trial after removing only
`/chosen/bootargs`. The inventory has 629 paths; recursive closure 630 includes
the bundle. The protected host GC root is
`~/tmp/k230-mainline-boot-trace-sbi-bundle-root`.

The realized source's `init/main.c` hash matches the
[source/native/RISC-V-object proof](../boot-boundary-sbi-host-2026-10-03.md).
All four public direct-SBI record strings are in the linked Image. The actual
built dev configuration enables RISCV_SBI, 64BIT, VMAP_STACK and 4KiB pages;
KUnit is disabled. Full link/build does not show firmware output or progress.

Both `rd.prepare_trial(...)` and the actual ordinary controller's `prepare(...)`
passed against the exact file manifest and most recent verified protected
normal report. Preparation checks required executable tools, immutable init,
serial-only console, both exact runtime flags and the original three qualified
controls. Commands use the private `prepare-transfer.py` and
`host-prepare-ordinary.py` under `~/tmp/k230-mainline-boot-trace-sbi-board`.
No console registration, earlycon/keep_bootcon, global clock bypass or observer
service is introduced. The command remains below the 512-byte U-Boot input bound.

The private delta NAR export is 103,873,318 bytes with eight new paths relative
to the already staged original trace bundle. Its own prospective board archive
and GC root are distinct; transfer preparation is not board staging proof.

## Remaining physical gate

Direct-SBI output, ordinary root/login, panel/touch and automatic return are
**UNVERIFIED**. Task 5b.5 stays unchecked. The source proof's outcome map and
firmware-call deadline caveat remain controlling. After a fresh protected normal
preflight and staging, the reserved operator runs:

```sh
python3 tools/mainline-drm-system-trial.py begin \
  --bundle /nix/store/j0ad6h3s23s5zlwizn3mbiw6cs98s4qn-k230-mainline-drm-trial-boot-files \
  --manifest <private-exact-manifest> --normal-report <private-normal-report> \
  --state <private-state> --log <private-uart-log> --result <private-result>
```

Keep the existing 180-second readiness deadline and exact banner/login/root
qualification. Unknown readiness stops all input; operator reset may be needed.
Real glass `touch --real-touch` and protected `finish` postflight remain required
if a candidate becomes ready. No archive or production acceptance is implied.
