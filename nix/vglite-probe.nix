{ lib
, stdenv
, fetchFromGitHub
}:

stdenv.mkDerivation (finalAttrs: {
  pname = "k230-vglite-probe";
  version = "0-1104236db4d1e47873bd68924f912747b820228c";

  # The normal SDK pin intentionally fetches only the stage-1 overlays.  This
  # narrow fetch is the pinned VG-Lite source required to build this optional
  # probe; it does not introduce an opaque vendor library into the image.
  src = fetchFromGitHub {
    owner = "kendryte";
    repo = "k230_linux_sdk";
    rev = "1104236db4d1e47873bd68924f912747b820228c";
    sparseCheckout = [ "buildroot-overlay/package/vg_lite" ];
    hash = "sha256-s64roxkoGxj9vpcWQW/XVbt42Z1hSeeNwVR0Qfmh3lA=";
  };

  sourceRoot = "source/buildroot-overlay/package/vg_lite";
  patches = [ ./patches/vglite-broker-device.patch ];

  # The pinned SDK Makefile hard-codes a vendor GCC spelling unsupported by
  # this pinned cross compiler. Retain the compiler's normal riscv64 target
  # ABI; the separately documented cache helper retains its C908 operation.
  postPatch = ''
    cp ${./vglite-access/k230_vg_lite.h} inc/k230_vg_lite.h
    substituteInPlace VGLite/Makefile --replace-fail "-mcpu=c908v " ""
    cat > inc/thead.h <<'EOF'
    #ifndef _THEAD_H_
    #define _THEAD_H_
    #include <stdint.h>

    /*
     * The SDK's `dcache.civa` mnemonic is not accepted by the pinned GNU
     * assembler.  The pinned 6.6.36 kernel documents this exact C908
     * virtual-address clean-and-invalidate encoding as 0x0275000b and its
     * completion barrier as 0x0190000b in errata_list.h.
     */
    static inline void thead_csi_dcache_clean_invalid_range(void *addr, uint64_t size) {
      register uint64_t a0 asm("a0") = (uint64_t)addr;
      int64_t remaining = size + a0 % 64;
      __asm volatile("fence iorw, iorw" ::: "memory");
      while (remaining > 0) {
        __asm volatile(".word 0x0275000b" : "+r"(a0) :: "memory");
        a0 += 64;
        remaining -= 64;
      }
      __asm volatile(".word 0x0190000b" ::: "memory");
      __asm volatile("fence iorw, iorw" ::: "memory");
      __asm volatile("fence.i" ::: "memory");
    }
    #endif
    EOF
  '';

  buildPhase = ''
    runHook preBuild

    make -C VGLite CC="$CC" CFLAGS="-fPIC"
    "$CC" -O2 -Wall -Wextra -Werror \
      -Iinc -I VGLiteKernel \
      ${./vglite-probe.c} \
      -Ldrivers -lvg_lite -Wl,-rpath,"$out/lib" \
      -o k230-vglite-probe

    runHook postBuild
  '';

  installPhase = ''
    runHook preInstall
    install -Dm755 drivers/libvg_lite.so "$out/lib/libvg_lite.so"
    install -Dm755 k230-vglite-probe "$out/bin/k230-vglite-probe"
    install -Dm644 inc/vg_lite.h "$out/include/vg_lite.h"
    install -Dm644 inc/k230_vg_lite.h "$out/include/k230_vg_lite.h"
    install -Dm644 test/LICENSE.txt "$out/share/licenses/k230-vglite-probe/LICENSE.txt"
    runHook postInstall
  '';

  meta = {
    description = "Source-built, offscreen-only VG-Lite blit/scale diagnostic for K230";
    license = lib.licenses.mit;
    platforms = [ "riscv64-linux" ];
  };
})
