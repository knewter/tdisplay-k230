## 1. Host

- [x] 1.1 Drawer search: `focus_from_keys`, `key_action` (Enter launches,
  Esc clears then closes) and the `drawer-keys` request line. Proof:
  `cargo test --offline` in `nix/rust-shell-client`, with
  `a_key_focused_search_launches_on_enter_and_clears_then_closes_on_esc` and
  the route-socket test.
- [x] 1.2 Overview key mode: `overview_key_mode` in `adapter.c` and the
  `overview` mode in `nix/shell.nix`. Proof: the system build compiles the
  patched Sway.

## 2. Board (hardware-only)

- [x] 2.1 With an app in front, inject LILYGO, `ti` and Enter. Timer
  launches, and the terminal behind received no keys. Proof:
  `docs/evidence/base-keys/` with the injected key log and grim captures.
- [x] 2.2 Inject LILYGO+Tab, Right, Enter, then LILYGO+Tab, Esc, then type in
  a terminal. The chosen app opens, Esc returns, and the terminal receives
  the plain keys afterwards (`swaymsg -t get_binding_state` reads `default`).
- [ ] 2.3 The operator does 2.1 and 2.2 on the real base. Physical proof: a
  timestamped operator report tied to the installed build.
