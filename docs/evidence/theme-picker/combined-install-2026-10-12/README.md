# Install the combined picker motion and profiling build, 2026-10-12

This install supports change `the-shell-swaps-themes-without-a-python-stall`.
It puts task 18.2's release motion and the task 13.1/13.2 cost-attribution
build on the board for one later board session. The source is master
`faae7298`, from a detached worktree at
`/home/jadams/tmp/k230-theme-board-2026-10-12`. Every serial step held the
board/serial lock, and the build held the build lock. Times are UTC.

The install claims no finger observation, timing, or performance result.

| Identity | Value |
| --- | --- |
| Bundle | `/nix/store/rmm45d7wpic7npaslga3di4bmv9j5381-k230-coherent-shell-boot-files` |
| System | `/nix/store/zvxmd93gnn6n3vpk1mdxgajqnb8h1gkm-nixos-system-nixos-26.11.20260919.20b1ddd` |
| Rust shell ELF | `/nix/store/ybpnyqmcn672n7x45nx9ybzprljgdhfg-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust` |
| Theme helper | `/nix/store/nlwjrn9c77qrjdrnaakafkhd4carp3by-handheld-theme-command-0.1` |
| Sway | unchanged: `q96sk40q…-sway-unwrapped-…-1.12` |
| Kernel, `Image`, `initrd.uimg` | unchanged from the baseline (asserted by [stage-used.py](stage-used.py)) |
| Baseline | key-only SSH install `c6qjs04y…`, see [../../console/ssh-installed-2026-10-11/](../../console/ssh-installed-2026-10-11/README.md) |

Build command:
`flock /tmp/k230-nix-build.lock nix build .#kernelMainlineDrmShellBootFiles --out-link ~/.local/state/tdisplay-k230/retained-builds/theme-board-2026-10-12/candidate --print-out-paths --max-jobs 1 --cores 4`
(exit 0).

## Sequence

1. **Preflight (read-only, serial).** PASS at 05:25:37 on boot `8050d551-…`
   ([preflight.json](preflight.json), [recipe](preflight-used.py)).
2. **Stage.** The closure delta (30 paths, xz NAR) went over the private
   transfer endpoint, followed by `stage.py prepare`, with no reboot
   ([stage.log](stage.log), [transfer.json](transfer.json),
   [staged-state.json](staged-state.json), [host-inspection.json](host-inspection.json)).
3. **Temporary candidate boot.** Controller result PASS
   ([candidate-boot.json](candidate-boot.json), [log](candidate-boot.log)).
   The runtime check passed at 05:30:51 on boot `8b66fed0-…`
   ([candidate-runtime.json](candidate-runtime.json), [recipe](runtime-check-used.py),
   [probe](inspect-runtime.py), [expected](expected-runtime.json)).
4. **Qualification.** [deployment-authorization.json](deployment-authorization.json)
   ([recipe](qualification-used.py)), class `operator-authorized-userspace-update`.
5. **Install and ordinary autoboot.** PASS ([ordinary-boot.json](ordinary-boot.json),
   [log](ordinary-boot.log)). The ordinary runtime check passed at 05:34:12
   on a new boot `9de0e538-…`
   ([ordinary-runtime.json](ordinary-runtime.json)):
   - the current system and profile are both `zvxmd93g…`;
   - `shell`, `shell-ui`, `theme-helper` and `k230-touch-trackpad` are active.
6. **Native capture over SSH.** `grim -s 0.5` ran as `shell`
   ([home-after-install-native.png](home-after-install-native.png)). It shows
   a foot terminal card in the foreground, not Home. The capture records the
   shell output only. No view of the glass was taken.

The board's address and network name stay private on the host. Raw UART logs
are kept privately in the host run directory.

## Remaining

Tasks 17.3, 13.4/11.3, 10.7, 6.6 and 18.3 are board measurements, and none
of them was performed by this install. Task 14.4 and task 18.4 require
real-finger acceptance from the operator.
