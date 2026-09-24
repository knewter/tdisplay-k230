{ stdenv }:
stdenv.mkDerivation {
  pname = "k230-c908-bitmanip-probe";
  version = "0.1";
  dontUnpack = true;
  buildPhase = ''
    runHook preBuild
    $CC -std=c11 -O2 -Wall -Wextra -Werror -fno-lto \
      -march=rv64gc -mabi=lp64d \
      ${./c908-bitmanip-probe.c} -o c908-bitmanip-probe
    runHook postBuild
  '';
  installPhase = ''
    runHook preInstall
    install -Dm755 c908-bitmanip-probe $out/bin/c908-bitmanip-probe
    runHook postInstall
  '';
  meta.description = "Diagnostic C908 Zba/Zbb/Zbc/Zbs userspace execution probe";
}
