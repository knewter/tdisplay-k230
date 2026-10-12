# Deploy the touch app-menu shell build, 2026-10-11

This deploys OpenSpec change `the-shell-proves-recovery-states-by-touch`
(task 1.1, master `383d4524`), ahead of task 3.1's real-finger capture.

- Worktree: `/home/jadams/tmp/k230-touch-menu-deploy-2026-10-11`
- Branch: `deploy/touch-app-menu-2026-10-11`
- Source revision: `383d45247e6ac56a11504e4bda7837aee930a9e0`
- Owned paths: this directory

The board/serial lock (`/tmp/k230-board.lock`) protected each board action. The
build ran under `/tmp/k230-nix-build.lock`. Times are UTC (2026-10-12 UTC is
the evening of 2026-10-11 local).

The operator was at the board and said "go" to deploy. This record claims
**no** finger observation.

| Identity | Value |
| --- | --- |
| Bundle | `/nix/store/hns0czzx7j27qy4wpzbpl3104535dx51-k230-coherent-shell-boot-files` |
| System | `/nix/store/7s8pl7pvdc9npqry1c6dzblk8k16x002-nixos-system-nixos-26.11.20260919.20b1ddd` |
| Rust shell ELF | `/nix/store/si9vd9hhdcb8kzppfsfq9id8kaqhnmwk-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust` |
| Kernel | unchanged: `/nix/store/f3rnipvbc5vqam8kwdmn3wgcl5rbz9yx-linux-riscv64-unknown-linux-gnu-7.3.0-rc5` |
| Baseline | recovery-states install `hamn9j9y…`, see [../installed-2026-10-11/](../installed-2026-10-11/README.md) |

## Build (host)

`flock -n /tmp/k230-nix-build.lock nix build .#kernelMainlineDrmShellBootFiles --out-link ~/.local/state/tdisplay-k230/retained-builds/touch-app-menu-2026-10-11/candidate --print-out-paths --max-jobs 1 --cores 4`
passed; see [build-tail.log](build-tail.log). `Image` and `initrd.uimg` are
byte-identical to the baseline. The out-link is the bundle's GC root.

### QEMU check of the exact installed ELF

This ELF differs from the one tested in
[../touch-app-menu-qemu-2026-10-11/](../touch-app-menu-qemu-2026-10-11/README.md):
that ELF was built from a staged, uncommitted tree. The same `--actions-only`
command, run on this ELF with this bundle's theme
(`4zi9dmny…-handheld-theme-default-28ceaae7`), returned PASS with all 11 checks
([qemu-actions/result.json](qemu-actions/result.json)). This is injected touch
under headless QEMU, not board input.

Three earlier attempts timed out at the same pointer step
(`home_app_actions_scenario.py:105`). That step comes before any touch-hold
scenario. Other jobs had the host at a load average of about 45. A control run
of the previously passing ELF timed out at the same line under the same load.
The PASS above came after the load dropped below 16.

## Board sequence

1. **Preflight (read-only).** [preflight-used.py](preflight-used.py) matched
   the recovery-states install's system, profile, kernel, executables and
   eight normal boot hashes, with four services active
   ([preflight.json](preflight.json), boot `44fb9940-…`).
2. **Stage.** [stage-used.py](stage-used.py) delivered a 30-path, xz-compressed
   closure delta over Wi-Fi on the first attempt: [stage.log](stage.log),
   [transfer.json](transfer.json), [staged-state.json](staged-state.json),
   [host-inspection.json](host-inspection.json).
3. **Temporary boot.** `tools/coherent-shell-board-boot.py --candidate … --state … --output …`
   passed ([candidate-boot.json](candidate-boot.json),
   [log](candidate-boot.log)).
   [runtime-check-used.py](runtime-check-used.py) with
   [inspect-runtime.py](inspect-runtime.py) and
   [expected-runtime.json](expected-runtime.json) returned PASS
   ([candidate-runtime.json](candidate-runtime.json)) on boot `561f5e4b-…`.
4. **Qualification.** [qualification-used.py](qualification-used.py) wrote and
   board-validated
   [deployment-authorization.json](deployment-authorization.json), class
   `operator-authorized-userspace-update`, with no finger checks claimed.
5. **Install and ordinary autoboot.** `… --qualification deployment-authorization.json --install`
   passed ([ordinary-boot.json](ordinary-boot.json),
   [log](ordinary-boot.log)). [ordinary-runtime.json](ordinary-runtime.json)
   is PASS on a new boot `8000d79e-…`:
   - current system and normal profile are both `7s8pl7pv…`;
   - the new Rust ELF is running and four services are active;
   - rollback roots are valid.

## Limits

This record proves that the build was installed and boots normally. It does
not prove that the touch hold opens the menu on glass, or that any recovery
state reads correctly there. Both belong to task 3.1's real-finger capture.
Raw UART logs stay private on the host.
