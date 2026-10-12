# Install key-only SSH and prove it after an ordinary boot, 2026-10-11

Task 3.1 of OpenSpec change `the-board-accepts-key-only-ssh` (source
`d156ca32`). Worktree `/home/jadams/tmp/k230-ssh-deploy-2026-10-11`, branch
`deploy/board-ssh-2026-10-11`. The board/serial lock covered each serial step,
and the build ran under the build lock. Times are UTC. No finger observation
is claimed.

| Identity | Value |
| --- | --- |
| Bundle | `/nix/store/66ij9hh2gczfh7qcnk40lrw8x16x8irv-k230-coherent-shell-boot-files` |
| System | `/nix/store/c6qjs04ysgdm2v39hxkz6ciac94djknm-nixos-system-nixos-26.11.20260919.20b1ddd` |
| Rust shell ELF | unchanged: `si9vd9hh…` |
| Kernel, `Image`, `initrd.uimg` | unchanged from the baseline |
| Baseline | touch app-menu install `7s8pl7pv…`, see [../../recovery-routes/touch-menu-installed-2026-10-11/](../../recovery-routes/touch-menu-installed-2026-10-11/README.md) |

## Sequence

1. **Preflight (read-only).** PASS on boot `928b8c33-…`
   ([preflight.json](preflight.json), [recipe](preflight-used.py)).
2. **Stage.** First attempt passed ([stage.log](stage.log),
   [transfer.json](transfer.json), [staged-state.json](staged-state.json),
   [host-inspection.json](host-inspection.json)).
3. **Temporary boot.** The controller returned **FAIL**
   ([candidate-boot-controller-fail.json](candidate-boot-controller-fail.json),
   [log](candidate-boot.log)). It checks `shell`, `shell-ui` and
   `theme-helper` once, immediately after login, and all three were still
   `inactive`. On this first boot of an SSH-enabled system, `sshd-keygen` took
   **40.5 s** (`systemd-analyze blame`) to generate host keys. `shell` reached
   active at about 75.7 s monotonic, against serial login at about 53.5 s. A
   serial check at 86 s found all four shell services active. The separate
   runtime check then returned PASS on the same boot `b7fbb19b-…`
   ([candidate-runtime.json](candidate-runtime.json),
   [recipe](runtime-check-used.py), [probe](inspect-runtime.py),
   [expected](expected-runtime.json)). The FAIL is kept as observed.
4. **SSH on the candidate.** The host key's fingerprint over SSH matched
   `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` read over serial. Root
   logged in with the dedicated key. A client offering only password or
   keyboard-interactive authentication got
   `Permission denied (publickey).`
5. **Qualification.** [deployment-authorization.json](deployment-authorization.json)
   ([recipe](qualification-used.py)), class
   `operator-authorized-userspace-update`.
6. **Install and ordinary autoboot.** PASS
   ([ordinary-boot.json](ordinary-boot.json), [log](ordinary-boot.log)).
   [ordinary-runtime.json](ordinary-runtime.json) is PASS on a new boot
   `8050d551-…`: the current system and profile are both `c6qjs04y…`, four
   shell services are active, and the rollback roots are valid.
7. **SSH after the ordinary boot** (task 3.1 proof), boot `8050d551`:
   - `ssh -i ~/.ssh/k230_board_ed25519 root@<board>` printed the system
     `c6qjs04y`, with `sshd` active and no `sshd-keygen` entry in this boot's
     blame, because the host keys persisted in `/etc/ssh`;
   - `ssh -o PubkeyAuthentication=no -o PreferredAuthentications=password,keyboard-interactive -o BatchMode=yes root@<board> true`
     returned `Permission denied (publickey).`

The board's address and network name stay private on the host
(`~/tmp/k230-coordination/`).

## Follow-up

A first boot from a fresh card, or the first boot after enabling SSH, pays
about 40 s of host-key generation, and that delays the shell. Restricting
`services.openssh.hostKeys` to ed25519 would remove most of it. The
controller's one-shot service check could also wait for the services. Neither
is done here.
