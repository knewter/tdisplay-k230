{ rustPlatform, pkg-config, wayland, cairo, pango, glib }:

rustPlatform.buildRustPackage {
  pname = "k230-shell-rust";
  version = "0.1.0";
  src = ./.;
  cargoLock.lockFile = ./Cargo.lock;
  nativeBuildInputs = [ pkg-config ];
  buildInputs = [ wayland cairo pango glib ];
  # Cargo unit tests run natively in nix/rust-shell-client host tests. Cross
  # package builds cannot execute a RISC-V test binary on the x86 build host.
  doCheck = false;
}
