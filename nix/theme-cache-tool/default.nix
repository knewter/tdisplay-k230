{ lib, rustPlatform, pkg-config, cairo }:

let
  shared = ../rust-shell-client/src;
in
rustPlatform.buildRustPackage {
  pname = "k230-theme-cache";
  version = "0.1.0";
  # Only this crate and the three shell modules it compiles by path, so an
  # edit elsewhere in the shell does not rebuild this tool or the theme
  # package that runs it.
  src = lib.fileset.toSource {
    root = ../.;
    fileset = lib.fileset.unions [
      ./Cargo.toml
      ./Cargo.lock
      ./src
      (shared + "/background_decode.rs")
      (shared + "/runtime_trace.rs")
      (shared + "/theme_thumbnails.rs")
    ];
  };
  sourceRoot = "source/theme-cache-tool";
  cargoLock.lockFile = ./Cargo.lock;
  nativeBuildInputs = [ pkg-config ];
  buildInputs = [ cairo ];
  # The decode modules' unit tests run with the shell's own host tests.
  doCheck = false;
}
