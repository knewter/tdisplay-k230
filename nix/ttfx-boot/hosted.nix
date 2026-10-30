# libk230_ttfx_boot.a for a hosted target (riscv64-linux, glibc): the same no_std
# engine as the stage 1 build, linked into the Linux player (nix/textfx) with std's
# allocator and panic handler, so both stages run one engine (design D4).
# Call with pkgsCross.riscv64.callPackage.
{ lib, stdenv, rustPlatform, callPackage }:

let
  ttfxSrc = callPackage ../ttfx-nostd { };
in
rustPlatform.buildRustPackage {
  pname = "k230-ttfx-boot-hosted";
  version = "0.1.0";
  src = lib.cleanSourceWith {
    src = ./.;
    filter = path: type: !(lib.hasSuffix ".nix" path) && !(lib.hasSuffix "bench" path);
  };
  cargoLock.lockFile = ./Cargo.lock;
  postUnpack = ''
    ln -s ${ttfxSrc} $sourceRoot/ttfx
  '';
  doCheck = false;
  buildPhase = ''
    runHook preBuild
    cargo rustc --release --offline --lib --crate-type staticlib \
      --target ${stdenv.hostPlatform.rust.rustcTarget} \
      --no-default-features --features hosted,all-effects
    runHook postBuild
  '';
  installPhase = ''
    runHook preInstall
    install -Dm644 target/${stdenv.hostPlatform.rust.rustcTarget}/release/libk230_ttfx_boot.a $out/lib/libk230_ttfx_boot.a
    install -Dm644 ${./ttfx_boot.h} $out/include/ttfx_boot.h
    runHook postInstall
  '';
  meta.description = "ttfx no_std engine as a hosted staticlib for the Linux player";
}
