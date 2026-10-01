# Home app actions: host checkpoint

2026-10-01, x86_64 host. Source adds mouse secondary-click menus to Home,
dock and All apps. Touch hold remains grab-and-move; no touch menu gesture
is added. Primary activation uses Sway focus history and shared desktop-ID,
StartupWMClass and executable fallback matching. Explicit New Window uses
the declared desktop action when present, otherwise a fresh GIO launch where
single-window/DBus metadata permits it. Named actions come from the desktop
entry, not shell-invented flags. Stale entries/windows are revalidated.

Menu metadata/window queries run off the Wayland dispatch thread with bounded
IPC reads. Outside/secondary clicks dismiss; canceled and dragged contacts
cannot activate rows. Trackpad pan release cannot become a menu click.
Private-marked windows conceal their titles. Menus use the active shell theme.

Command in the native Nix environment (Cairo, Pango, librsvg, GLib,
libxkbcommon, Cargo/Rust from the pinned flake at eb38af2a):

```sh
cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml
```

PASS: 426 library checks, 22 binary checks and 43 integration checks; one
pre-existing timing benchmark ignored. New policy tests cover MRU/mismatched
identity, private labels, cancellation/drag and real GIO desktop-action and
single-window metadata. Existing Home grab and primary-pointer ownership
regressions pass. This is host proof, not compositor menu delivery, a native
board capture or finger acceptance. The paired actions scenario, exact cross
build and recoverable installation remain separate tasks.
