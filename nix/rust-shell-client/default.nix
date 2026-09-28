{ rustPlatform, pkg-config, wayland, cairo, pango, glib, librsvg, libxkbcommon }:

rustPlatform.buildRustPackage {
  pname = "k230-shell-rust";
  version = "0.1.0";
  src = ./.;
  cargoLock.lockFile = ./Cargo.lock;
  nativeBuildInputs = [ pkg-config ];
  # libxkbcommon: smithay-client-toolkit's "xkbcommon" feature (Cargo.toml)
  # turns wl_keyboard keycodes into text for the Wi-Fi password field --
  # already a runtime dependency of Sway/wlroots itself in this same
  # closure, so cross-compiling it for riscv64 is already proven.
  buildInputs = [ wayland cairo pango glib librsvg libxkbcommon ];
  # Cargo unit tests run natively in nix/rust-shell-client host tests. Cross
  # package builds cannot execute a RISC-V test binary on the x86 build host.
  doCheck = false;
}
