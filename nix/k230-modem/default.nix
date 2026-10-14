{ rustPlatform }:

# The nRF9151 modem service and its control client
# (openspec/changes/the-nrf9151-gives-the-handheld-cellular-sms-and-location).
# Only libc, serde and serde_json, all already vendored for
# nix/rust-shell-client. Unit tests run natively with `cargo test` in this
# directory; a cross build cannot execute a RISC-V test binary on the host.
rustPlatform.buildRustPackage {
  pname = "k230-modem";
  version = "0.1.0";
  src = ./.;
  cargoLock.lockFile = ./Cargo.lock;
  doCheck = false;
}
