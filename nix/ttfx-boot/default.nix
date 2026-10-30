# libk230_ttfx_boot.a: the no_std ttfx engine as a freestanding riscv64imac
# (soft-float, lp64) staticlib for linking into U-Boot, which is itself built
# `-march=rv64imac -mabi=lp64` with the FPU never enabled
# (docs/evidence/boot-text-effects/nostd-feasibility.md).  Not built by default;
# nothing consumes it until the stage 1 task is reviewed.
#
# nixpkgs' rustc ships no std for riscv64imac-unknown-none-elf (its riscv64-embedded
# target is riscv64gc, hard-float, which would trap in U-Boot), and the official
# rust-std tarball is refused by a nixpkgs rustc ("compiled by an incompatible version of
# rustc": the nixpkgs compiler reports `built from a source tarball`).  So core, alloc and
# compiler_builtins are built from the matching rust-src with `-Zbuild-std` (the stable
# compiler under RUSTC_BOOTSTRAP=1), offline: cargo resolves the whole std workspace, so
# the vendor directory is the crate's own lock plus the std lock, both through importCargoLock.
{ lib, stdenv, rustc, cargo, rustPlatform, runCommand, writeShellScript, callPackage
, features ? [ "fw" "boot-set" ]
}:

let
  target = "riscv64imac-unknown-none-elf";
  ttfxSrc = callPackage ../ttfx-nostd { };
  libSrc = rustPlatform.rustLibSrc;
  vendor = runCommand "k230-ttfx-boot-vendor" { } ''
    mkdir $out
    for d in ${rustPlatform.importCargoLock { lockFile = ./Cargo.lock; }}/* \
             ${rustPlatform.importCargoLock { lockFile = "${libSrc}/Cargo.lock"; }}/*; do
      [ -d "$d" ] && cp -rn "$d" $out/ || true
    done
  '';
  sysroot = runCommand "rust-sysroot-with-src-${rustc.version}" { } ''
    mkdir -p $out
    cp -rs ${rustc.unwrapped}/. $out/
    chmod -R u+w $out
    mkdir -p $out/lib/rustlib/src/rust
    ln -s ${libSrc} $out/lib/rustlib/src/rust/library
  '';
  rustcWithSrc = writeShellScript "rustc-with-src" ''
    exec ${sysroot}/bin/rustc --sysroot ${sysroot} "$@"
  '';
in
stdenv.mkDerivation {
  pname = "k230-ttfx-boot";
  version = "0.1.0";
  src = lib.cleanSourceWith {
    src = ./.;
    filter = path: type: !(lib.hasSuffix ".nix" path) && !(lib.hasSuffix "bench" path);
  };
  nativeBuildInputs = [ cargo ];

  postUnpack = ''
    ln -s ${ttfxSrc} $sourceRoot/ttfx
  '';

  buildPhase = ''
    runHook preBuild
    export CARGO_HOME=$TMPDIR/cargo-home
    mkdir -p $CARGO_HOME
    cat > $CARGO_HOME/config.toml <<CFG
    [source.crates-io]
    replace-with = "vendored-sources"
    [source.vendored-sources]
    directory = "${vendor}"
    CFG
    export RUSTC=${rustcWithSrc}
    export RUSTC_BOOTSTRAP=1
    export RUSTFLAGS="-C relocation-model=pic"
    cargo rustc --release --offline --lib --crate-type staticlib --target ${target} \
      -Zbuild-std=core,alloc,compiler_builtins -Zbuild-std-features=compiler-builtins-mem \
      --no-default-features --features ${lib.concatStringsSep "," features}
    runHook postBuild
  '';

  installPhase = ''
    runHook preInstall
    install -Dm644 target/${target}/release/libk230_ttfx_boot.a $out/lib/libk230_ttfx_boot.a
    install -Dm644 ${./ttfx_boot.h} $out/include/ttfx_boot.h
    runHook postInstall
  '';

  dontFixup = true;
  meta = {
    description = "ttfx boot animation engine (no_std, riscv64imac soft-float) for U-Boot";
    license = lib.licenses.mit;
  };
}
