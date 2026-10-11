# Deploy the recovery-states shell build, 2026-10-11

This is the deployment for OpenSpec change
`the-rust-shell-explains-stale-denied-and-ended-states`. It precedes task 3.1's
real-finger capture.

- Worktree: `/home/jadams/tmp/k230-recovery-deploy-2026-10-11`
- Branch: `deploy/recovery-states-2026-10-11`
- Source revision: `30b3834b45e888ae27a55f4401d8f883f81e890c` (master)
- Owned paths: this directory

The board/serial lock (`/tmp/k230-board.lock`) protected each board action. The
build ran under `/tmp/k230-nix-build.lock`. Times are UTC.

The operator was present at the board and said: "run the new build or whatever
it's fine yeah go i'm here". This record claims **no** finger observation.

| Identity | Value |
| --- | --- |
| Bundle | `/nix/store/1agv6di19d0dllj1dw9ghvr34f7zzjfr-k230-coherent-shell-boot-files` |
| System | `/nix/store/hamn9j9y78xhy8r6j833kxg5gg9msm82-nixos-system-nixos-26.11.20260919.20b1ddd` |
| Rust shell ELF | `/nix/store/2wcmrw22y9rsfv79z64h1l62xwwd7nwv-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust` |
| Kernel | unchanged: `/nix/store/f3rnipvbc5vqam8kwdmn3wgcl5rbz9yx-linux-riscv64-unknown-linux-gnu-7.3.0-rc5` |
| Baseline | theme install system `925i44g1…`, see [../../omarchy-themes/installed-consumers-2026-10-10/](../../omarchy-themes/installed-consumers-2026-10-10/README.md) |

## Build (host)

`flock -n /tmp/k230-nix-build.lock nix build .#kernelMainlineDrmShellBootFiles --out-link ~/.local/state/tdisplay-k230/retained-builds/recovery-states-2026-10-11/candidate --print-out-paths --max-jobs 1 --cores 4`
passed. See [build-tail.log](build-tail.log).

- `Image` and `initrd.uimg` are byte-identical to the baseline.
- The out-link is the GC root for the bundle.
- No input-retention farm was built this time. Unchanged inputs remain covered
  by the theme deployment's retained farm. New inputs are not retained beyond
  the bundle's own closure.

## Board sequence

1. **Preflight (read-only).** [preflight-used.py](preflight-used.py) matched
   the baseline system, profile, kernel, Rust/Sway executables and all eight
   normal boot hashes, with four services active. The first attempt got no
   console bytes. A direct serial probe then showed the root prompt and the
   retry passed on boot `6371650b-…`
   ([preflight-before-power-cycle.json](preflight-before-power-cycle.json)).
2. **Stage.** [stage-used.py](stage-used.py) delivered the 33-path closure
   delta over the board's Wi-Fi. Attempts 1–3 changed nothing persistent:
   - Attempt 1: curl exit 7, because the private transfer address was stale
     after a host DHCP change. The private file was updated.
   - Attempt 2: curl exit 28, because the 188 MB uncompressed NAR exceeded the
     300 s limit at about 90 KB/s. The delta is now xz-compressed and the
     limit raised to 3600 s.
   - Attempt 3: interrupted at 19:45:47Z when the board's console USB was
     unplugged. The board lost power, and the host kernel log shows a
     different USB device briefly on that port. The board autobooted the
     unchanged baseline. [preflight.json](preflight.json) re-verified it on
     boot `ee934583-…`.
   - Attempt 4 passed: [stage.log](stage.log), [transfer.json](transfer.json),
     [staged-state.json](staged-state.json),
     [host-inspection.json](host-inspection.json).
3. **Temporary boot.** `tools/coherent-shell-board-boot.py --candidate … --state … --output …`
   passed; see [candidate-boot.json](candidate-boot.json) and its
   [log](candidate-boot.log). [runtime-check-used.py](runtime-check-used.py)
   with [inspect-runtime.py](inspect-runtime.py) produced
   [candidate-runtime.json](candidate-runtime.json): PASS on boot
   `e3cf0c3c-…`, exact new system and Rust ELF, four active services, and
   unchanged normal boot files.
4. **Qualification.** [qualification-used.py](qualification-used.py) wrote
   and board-validated
   [deployment-authorization.json](deployment-authorization.json). Its class
   is `operator-authorized-userspace-update`: same kernel and initrd, and no
   finger checks claimed.
5. **Install and ordinary autoboot.** `… --qualification deployment-authorization.json --install`
   passed; see [ordinary-boot.json](ordinary-boot.json) and its
   [log](ordinary-boot.log). [ordinary-runtime.json](ordinary-runtime.json)
   is PASS on a new boot `44fb9940-…`:
   - current system and normal profile are both `hamn9j9y…`;
   - the new Rust ELF is running and four services are active;
   - rollback roots are valid.

## Limits

This record proves that the build was installed and boots normally. It does not
prove that any recovery state renders correctly on glass. That is task 3.1's
real-finger capture, recorded separately under `docs/evidence/recovery-routes/`.
Raw UART logs stay private on the host.
