# Touch-hold opens an app's menu (headless QEMU), 2026-10-11

Task 1.1 of OpenSpec change `the-shell-proves-recovery-states-by-touch`.
Evidence class: **headless QEMU, injected touch**. This is not a board,
camera or real-finger observation; task 3.1 remains open for that.

Gesture (operator choice, 2026-10-11, "Android-style"): hold a drawer tile
still for 500 ms and the app's menu opens. Lifting without moving leaves it
open. Moving the same finger more than 12 px closes the menu and starts the
existing drag to Home.

Command (from worktree `~/tmp/k230-touch-app-menu`, output under a short
host temporary path):

```sh
python3 tests/rust_home_screen_qemu.py --actions-only \
  --sway /nix/store/q96sk40q7j5v9f0ygxf2wx3yk7nzixqs-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --swaymsg /nix/store/q96sk40q7j5v9f0ygxf2wx3yk7nzixqs-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/swaymsg \
  --rust /nix/store/17506zjlnfdmpvr272lrzf5cncif3f7b-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust \
  --theme-bundle /nix/store/jc3fqhg3n3rq52gd0vgfyw2rxphl5hj8-handheld-theme-default-28ceaae7 \
  --icons /nix/store/in3nc21zx02xiz2rdp5bpq36719x3axd-handheld-theme-icons-25.10.3 \
  --client /nix/store/z31hh776z0s4q9pgqn6bsd69al3xkqbn-card-composition-probe-client-riscv64-unknown-linux-gnu-0.1/bin/card-composition-probe-client \
  --output <short temporary path>
```

[result.json](result.json) is PASS with 11 checks. These two cover this change:

- `drawer_touch_hold_opens_menu_without_drag`: the shell logged `app-menu-hold`
  and `app-menu-ready`, with no new `home-drag-begin` and no dismissal on lift.
  A tap outside then dismissed the menu, and the layout and windows were
  unchanged.
- `touch_hold_keeps_drawer_drag_to_home`: holding and then moving still placed
  the app on Home, after exactly one menu open.

[drawer-actions-touch-hold-menu.png](drawer-actions-touch-hold-menu.png) is the
menu that stayed open after the lift. Terminal is already on Home, so the menu
offers "Remove from Home". The scrim over Home is how the drawer always
renders a menu: right-click shows the same.

The Rust ELF above is the host build of `.#handheld-shell-rust` from this
change's source. It is not yet deployed to the board.
