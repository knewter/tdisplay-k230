{ rustPlatform, pkg-config, wayland }:

rustPlatform.buildRustPackage {
  pname = "k230-shell-rust-probe";
  version = "0.1.0";
  src = ./.;
  cargoLock.lockFile = ./Cargo.lock;
  nativeBuildInputs = [ pkg-config ];
  buildInputs = [ wayland ];
  # Cargo unit tests run natively in tests/test_rust_shell_probe.py. Cross
  # package builds cannot execute a RISC-V test binary on the x86 build host.
  doCheck = false;
}
