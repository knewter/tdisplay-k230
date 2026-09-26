# App drawer drag-to-close (board check)

Evidence class: **operator report from real-finger use on the board**. No
camera recording or injected-touch run was made for this change.

- System: `kl2y2jmm…-nixos-system-nixos-26.11.20260919.20b1ddd`
  (`fix/drawer-drag-to-close` at `bd718893`), test-activated over
  `yb815pr0` on 2026-09-25.
- Operator, after using the drawer on the glass: "i tested it it worked
  fine".
- Host checks: `cargo test` in `nix/rust-shell-client` passed 240 of 240,
  including the drawer zone gating, the downward-direction mirror, and a
  `RendererCache` partial-offset test.

Not established: a frame-by-frame record of the drag and settle, and
behaviour when the grid has been scrolled before the drag.
