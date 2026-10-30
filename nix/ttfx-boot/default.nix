# libk230_ttfx_boot.a: the no_std ttfx engine as a freestanding riscv64imac
# (soft-float, lp64) staticlib for linking into U-Boot, which is itself built
# `-march=rv64imac -mabi=lp64` with the FPU never enabled (docs/evidence/boot-text-effects/
# nostd-feasibility.md).  Not built by default; nothing consumes it until the
# stage 1 task is reviewed.
#
# nixpkgs' rustc ships no std for riscv64imac-unknown-none-elf (its
# riscv64-embedded target is riscv64gc, hard-float, which would trap in U-Boot),
# so the official rust-std tarball for the same rustc version is added to a
# sysroot.  Hash is the one static.rust-lang.org publishes beside the tarball.
{ lib, stdenv, rustc, cargo, rustPlatform, fetchurl, symlinkJoin, runCommand, xz
, callPackage
, features ? [ "fw" "subset" ]
}:

let
  target = "riscv64imac-unknown-none-elf";
  ttfxSrc = callPackage ../ttfx-nostd { };
  rustStd = fetchurl {
    url = "https://static.rust-lang.org/dist/rust-std-${rustc.version}-${target}.tar.xz";
    hash = "sha256-8d2lMs7DI2BeoBMOIu60fTMpLooPRCmJ6I0NFW04I4E="; # rustc 1.98.1
  };
  stdTree = runCommand "rust-std-${target}-${rustc.version}" { nativeBuildInputs = [ xz ]; } ''
    mkdir -p $TMPDIR/x $out/lib/rustlib
    tar -xJf ${rustStd} -C $TMPDIR/x
    cp -r $TMPDIR/x/*/rust-std-${target}/lib/rustlib/${target} $out/lib/rustlib/
  '';
  sysroot = symlinkJoin {
    name = "rust-sysroot-${target}";
    paths = [ rustc.unwrapped stdTree ];
  };
in
stdenv.mkDerivation {
  pname = "k230-ttfx-boot";
  version = "0.1.0";
  src = lib.cleanSourceWith {
    src = ./.;
    filter = path: type: !(lib.hasSuffix "default.nix" path);
  };

  cargoDeps = rustPlatform.importCargoLock { lockFile = ./Cargo.lock; };
  nativeBuildInputs = [ cargo rustc rustPlatform.cargoSetupHook ];

  postUnpack = ''
    ln -s ${ttfxSrc} $sourceRoot/ttfx
  '';

  buildPhase = ''
    runHook preBuild
    export RUSTFLAGS="--sysroot ${sysroot} -C relocation-model=pic"
    cargo rustc --release --offline --lib --crate-type staticlib --target ${target} \
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
