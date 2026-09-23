{ lib, stdenv, fetchFromGitHub, libdrm, pixman }:

stdenv.mkDerivation (finalAttrs: {
  pname = "k230-vglite-validation";
  version = "0-1104236db4d1e47873bd68924f912747b820228c";
  src = fetchFromGitHub {
    owner = "kendryte"; repo = "k230_linux_sdk";
    rev = "1104236db4d1e47873bd68924f912747b820228c";
    sparseCheckout = [ "buildroot-overlay/package/vg_lite" ];
    hash = "sha256-s64roxkoGxj9vpcWQW/XVbt42Z1hSeeNwVR0Qfmh3lA=";
  };
  sourceRoot = "source/buildroot-overlay/package/vg_lite";
  postPatch = ''
    substituteInPlace VGLite/Makefile --replace-fail "-mcpu=c908v " ""
    cat > inc/thead.h <<'EOF'
    #ifndef _THEAD_H_
    #define _THEAD_H_
    #include <stdint.h>
    static inline void thead_csi_dcache_clean_invalid_range(void *addr, uint64_t size) {
      register uint64_t a0 asm("a0") = (uint64_t)addr; int64_t remaining = size + a0 % 64;
      __asm volatile("fence iorw, iorw" ::: "memory");
      while (remaining > 0) { __asm volatile(".word 0x0275000b" : "+r"(a0) :: "memory"); a0 += 64; remaining -= 64; }
      __asm volatile(".word 0x0190000b" ::: "memory"); __asm volatile("fence iorw, iorw" ::: "memory"); __asm volatile("fence.i" ::: "memory");
    }
    #endif
    EOF
  '';
  buildPhase = ''
    make -C VGLite CC="$CC" CFLAGS="-fPIC"
    "$CC" -O2 -Wall -Wextra -Werror -Iinc -IVGLiteKernel -I${lib.getDev libdrm}/include -I${lib.getDev libdrm}/include/libdrm -I${lib.getDev pixman}/include/pixman-1 ${./vglite-validation-probe.c} -Ldrivers -lvg_lite -L${lib.getLib libdrm}/lib -ldrm -L${lib.getLib pixman}/lib -lpixman-1 -Wl,-rpath,"$out/lib" -o k230-vglite-validation
  '';
  installPhase = ''
    install -Dm755 drivers/libvg_lite.so "$out/lib/libvg_lite.so"
    install -Dm755 k230-vglite-validation "$out/bin/k230-vglite-validation"
    install -Dm644 inc/vg_lite.h "$out/include/vg_lite.h"
    install -Dm644 test/LICENSE.txt "$out/share/licenses/k230-vglite-validation/LICENSE.txt"
  '';
  meta = { description = "Bounded source-built K230 VG-Lite validation"; license = lib.licenses.mit; platforms = [ "riscv64-linux" ]; };
})
