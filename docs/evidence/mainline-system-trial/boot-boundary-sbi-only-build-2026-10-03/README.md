# SBI-only boot markers — matching full build

2026-10-03 UTC. Coordinator worktree
`/home/jadams/tmp/k230-mainline-probe-integration`, branch
`integrate/mainline-probe-path`; source `c6896fbc3b4a3e0fe7b3579f0add791adafbef12`
at master `7a660a6a638617d3ca32325fc1672dbfb6ce713f`. Root held
`/tmp/k230-nix-build.lock` for the full build and released it on completion.
Owned paths are this evidence directory and the mainline task progress note.

```sh
flock -n /tmp/k230-nix-build.lock nix build \
  .#kernelMainlineBootTraceSbiOnlyTrialBootFiles --no-link --print-out-paths \
  --max-jobs 1 --cores 16
python3 tools/mainline-drm-trial-inspect.py \
  /nix/store/brmp1qf9cz65yciazabc8yg5j39nn643-k230-mainline-drm-trial-boot-files
```

Both **passed**. Exact selected system/kernel/config/source and artifact
hashes are in [result.json](result.json). Inspector verified Image equality,
matching initrd payload and U-Boot header/data CRC, DT/environment arguments,
SHA256SUMS and inventory. The 629-path inventory plus bundle gives 630 recursive
closure paths. Hardware DT equals the previous `j0ad6h3s…` candidate after
removing only `/chosen/bootargs`. All twenty fixed public SBI-only records are
in the linked Image; the four outer-record variant is absent. The actual dev
config matches source/object proof, enabling RISCV_SBI/64BIT/VMAP_STACK/4KiB
pages with KUnit disabled. Realized `init/main.c` matches the reviewed
[source/native/object proof](../boot-boundary-sbi-only-host-2026-10-03.md).

Both actual `rd.prepare_trial(...)` and ordinary-controller `prepare(...)`
passed against exact artifacts and the last verified protected normal identity
baseline. Preparation is host-only and validates immutable init, required
executables, sole serial console, exactly both base/new flags and the three
original qualified controls. No earlycon/keep_bootcon, global clock bypass,
observer, new console or controller change is present. The command remains
below the 512-byte U-Boot input bound. Subsequent user reset passed fresh
protected normal postflight, recorded separately in
[reset recovery](../boot-boundary-sbi-physical-2026-10-03/operator-reset-recovery.json);
the new report now carries that verified normal boot ID.

Private full-build log: `~/tmp/k230-mainline-boot-trace-sbi-only-full-build.log`.
Host GC root: `~/tmp/k230-mainline-boot-trace-sbi-only-bundle-root`. Private
helper/manifest/export directory: `~/tmp/k230-mainline-boot-trace-sbi-only-board`.
Delta export contains eight new paths / 103,844,240 bytes relative to the
already staged `j0ad6h3s…` bundle. Separate board archive and GC root names
are prepared. This export is not transfer or board-staging proof.

## Remaining physical gate

SBI-only output, ordinary login/root, deliberate glass and automatic return
remain **UNVERIFIED**. Task 5b.5 stays unchecked. With the board/UART reserved,
first stage and recheck fresh protected normal identities; then run:

```sh
python3 tools/mainline-drm-system-trial.py begin \
  --bundle /nix/store/brmp1qf9cz65yciazabc8yg5j39nn643-k230-mainline-drm-trial-boot-files \
  --manifest <private-exact-manifest> --normal-report <private-normal-report> \
  --state <private-state> --log <private-uart-log> --result <private-result>
```

Keep the 180-second readiness deadline and exact fresh Linux/login/root gates.
Unknown readiness stops all input; operator recovery may still be necessary.
A visible last record does not prove its firmware ECALL returned. If ready,
real glass `touch --real-touch` and protected `finish` postflight remain
required. No production or archive acceptance is implied.
