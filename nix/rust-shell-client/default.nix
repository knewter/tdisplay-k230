{ lib, rustPlatform, pkg-config, wayland, cairo, pango, glib, librsvg, libxkbcommon }:

let
  common = {
    version = "0.1.0";
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
  };

  # Every locked dependency, compiled against stub sources. It depends only on
  # Cargo.toml and Cargo.lock, so an edit to the shell's own code reuses it
  # and the build below compiles one crate instead of about 110. Its inputs
  # and environment must match the build below or cargo recompiles the
  # dependencies there.
  deps = rustPlatform.buildRustPackage (common // {
    pname = "k230-shell-rust-deps";
    src = lib.fileset.toSource {
      root = ./.;
      fileset = lib.fileset.unions [ ./Cargo.toml ./Cargo.lock ];
    };
    postPatch = ''
      mkdir -p src
      echo > src/lib.rs
      echo 'fn main() {}' > src/main.rs
    '';
    installPhase = ''
      runHook preInstall
      mkdir -p $out
      cp -r target $out/target
      runHook postInstall
    '';
    dontFixup = true;
  });
in
rustPlatform.buildRustPackage (common // {
  pname = "k230-shell-rust";
  # Tests and examples run on the host only; leaving them out keeps an edit
  # there from rebuilding the board's binary.
  src = lib.fileset.toSource {
    root = ./.;
    fileset = lib.fileset.unions [ ./Cargo.toml ./Cargo.lock ./src ];
  };
  # Start from the dependency build. cargoSetupHook copies the vendored
  # sources in with fresh mtimes, so give every restored artifact one
  # timestamp just ahead of them; cargo then sees the dependencies as fresh
  # and none newer than another. Drop the stub crate's own artifacts so the
  # real sources compile.
  preBuild = ''
    cp -r ${deps}/target target
    chmod -R u+w target
    find target -exec touch -h -d "@$(( $(date +%s) + 60 ))" {} +
    find target -name 'k230-shell-rust-*' -path '*/.fingerprint/*' -prune -exec rm -rf {} +
    find target \( -name 'k230_shell_rust-*' -o -name 'libk230_shell_rust*' -o -name 'k230-shell-rust' -o -name 'k230-shell-rust.d' \) -exec rm -rf {} +
  '';
  passthru = { inherit deps; };
})
