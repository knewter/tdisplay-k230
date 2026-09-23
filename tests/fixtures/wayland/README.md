# Launcher host-test protocol fixture

`wlr-layer-shell-unstable-v1.xml` is copied verbatim from the flake-pinned
wlroots 0.20.2 source (`protocol/wlr-layer-shell-unstable-v1.xml`). Its copyright
and permissive license are retained in the file. This fixture lets CI compile
the production launcher without a Nix store; the production Nix derivation
continues to obtain the protocol from its pinned wlroots source.

Source archive: https://gitlab.freedesktop.org/api/v4/projects/wlroots%2Fwlroots/repository/archive.tar.gz?sha=0.20.2

SHA-256: `87e0b9c837aecd6977f76f3c47d73088b7159871f5d979dc1840f6cadb5e2ed8`

Host dependencies: a C compiler, pkg-config, GLib/GIO, Wayland client and scanner,
Pango/Cairo development files, and wayland-protocols (stable xdg-shell). The
launcher navigation test fails explicitly if these dependencies are missing.
