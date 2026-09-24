# Installed keyboard gesture candidate

Observed 2026-09-24 UTC on the physical board. Source `e9d3bd6c` built with
`nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel --max-jobs 1 --cores 4 --no-link --print-out-paths`.
The exact system and running Sway/Rust binaries are in [installed.json](installed.json).
The named narrow hint package command also passed from this same production
source: `nix build .#handheld-shell-rust --max-jobs 1 --cores 4 --no-link --print-out-paths`,
output `/nix/store/a4gdwfmr79pf6yfvq24wmqi495mdm4mg-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0`,
derivation `/nix/store/466mi8pv9nm0m1g1ps0x72l9bhvq9q3j-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0.drv`.
The flake's standalone package and the NixOS module use distinct package
contexts: this narrow output is not claimed to be the installed `b3qdp…`
executable, which was built by the full-system command and read from the
running process. The dark/light hint captures remain separate QEMU evidence.

The matching [coherent image](../../coherent-shell/boot-artifacts/README.md)
is a separate host artifact; it was not flashed or selected for boot here.

Under the exclusive board reservation, 27 additional store paths (10,961,320
NAR bytes) were imported with exit 0. The new system's
`bin/switch-to-configuration test` exited 0. A five-minute transient rollback
timer targeted the previous test system before activation. Console checks
used `readlink -f /run/current-system`, the running process `/proc/PID/exe`
links and `systemctl is-active shell shell-ui shell-session-bus shell-notifications k230-wifi k230-wifi-settings`.
All six services were active. After reviewing the captures below, the timer
was stopped and the candidate identity and shell services were checked again.
Raw transport/service output remains private; the committed record contains
only the allowlisted identities and outcomes.

| State | Native board capture | Method |
| --- | --- | --- |
| Terminal, keyboard hidden | [Terminal](terminal-hidden.png) | Fresh shell session after activation |
| Keyboard and dismissal handle shown | [Keyboard](keyboard-shown.png) | `pkill -USR2 -x wvkbd-mobintl` as the shell user |

Both unedited 568×1232 PNGs were captured with the installed `grim` against
the active Wayland display, transferred over the reserved console, and
visually inspected before publication. They show the actual board compositor,
not the panel through a camera. No gesture was injected or performed by a
person for this record. The shown keyboard was requested by its lifecycle
signal. The handle is present but its dark-theme stroke has weak contrast;
a follow-up source correction is being prepared.

The installed candidate also includes the new Wi-Fi Settings UI, actual
wallpaper preview, quieter card chrome, and the previously installed app grid
and direct carousel. This activation alone does not prove their on-glass
behavior or real Wi-Fi association/persistence. The Settings keyboard hint has
separate dark/light [native QEMU evidence](../../wifi-settings/README.md).
User two-finger show, grip hold/reverse/hide, typing, perceived motion and
workload budgets remain open. No reboot was performed and boot files/profile
were not changed by this test activation. The previous boot selection remains
the reboot fallback. A manual session rollback uses the previous system path
in `installed.json` followed by `/bin/switch-to-configuration test`.
