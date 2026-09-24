# Integrated session configuration: host build checkpoint

Observed 2026-09-24. Exact source
`9e3e16bb4601a753e01e5a162fe93a9a975631b3` introduces the opt-in
`nixosConfigurations.k230-coherent-shell` configuration. The normal `k230`
configuration remains the reproducible bar-session rollback.

The candidate selects the live-card Sway package and supervised Rust frontend,
with a shared private session bus, notification broker and immutable Settings
command. Sway and Rust use the same runtime/reveal socket and reduced-motion
setting. The ordinary-app rule invokes the private per-container
`card_shell ordinary` command and excludes the two video application IDs;
dialogs retain their own geometry. Keyboard usable-area behavior of the
compositor is recorded separately in [usable-area-qemu.md](usable-area-qemu.md).

Managed terminal and monitor launches use the acknowledged generated Foot
palette, a pinned fresh-home fallback and the live palette follower. Their
defaults, including htop configuration, remain image inputs. The separately
supervised Rust service discovers the actual single Wayland display and
shares the application environment with the compositor.

```sh
nix build \
  .#nixosConfigurations.k230-coherent-shell.config.k230.shell.rustFrontend \
  .#nixosConfigurations.k230-coherent-shell.config.k230.shell.themedTerminal \
  --max-jobs 1 --cores 4 --no-link --print-out-paths
```

PASS. Exact output wrappers:

- `/nix/store/z05sm7il7pkpxq8wggqklhy97d3nx3jq-k230-shell-rust`
- `/nix/store/s59ry2bk1q4rgbsyjkf4hb4jjnmy32k9-k230-foot`

The Rust source includes the corrected interaction and named-icon initialization
checkpoint. Host Nix evaluation reports all assertions true for both
configurations, coherent mode enabled only in the candidate, and the UI/bus
services absent from the normal configuration. The UI is ordered after Sway,
the session bus and notification broker, and stops with the Sway service.

This proves evaluation and the two named package builds. It does **not** prove
a complete system closure/image, service startup on the board, real app touch
interaction, theme switching, notification presentation or an installed
revision. The legacy C theme-receiver trial remains separate; Rust/deck theme
consumers are being integrated and this checkpoint does not claim their
system-wide activation works.

The next build gate is
`nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel`.
After the exact candidate and its recovery path are staged by the sole board
operator, the remaining device gate is the integrated drawer/card/keyboard
trial with representative apps, native captures and measured CPU/frame cost.
Real-finger acceptance stays pending until separately observed.

## Integrated theme system closure

Source `cd06bee4` built the complete opt-in NixOS toplevel on 2026-09-24:

```sh
nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel \
  --max-jobs 1 --cores 4 --no-link --print-out-paths
```

PASS: `/nix/store/206lci3a8k86igxi1hmahdwfzd9gd5l0-nixos-system-nixos-26.11.20260919.20b1ddd`.
This includes the paired Rust/deck appearance command wiring and persistent
Rust wallpaper implementation. An initial evaluation rejected a store-context
attribute name in the notification source allowlist; `cd06bee4` uses JSON
string content to preserve its package dependency. Full build passed after
that correction. No board activation or image boot is claimed by this build.
