# Prepared-header/API proof only: three objects, no kernel or module link.
{ runCommand, gnumake, python3, binutils, crossCc, kernel, baseKernel }:
runCommand "k230-mainline-uart-progress-objects" {
  nativeBuildInputs = [ gnumake python3 binutils crossCc ];
} ''
  mkdir -p build module $out
  cp -r ${baseKernel.dev}/lib/modules/7.3.0-rc5/build/. build/
  chmod -R u+w build
  cp ${kernel.src}/drivers/tty/serial/8250/8250_core.c module/
  cp ${kernel.src}/drivers/tty/serial/8250/8250.h module/
  cp ${kernel.src}/drivers/clocksource/timer-riscv.c module/
  cp ${kernel.src}/drivers/soc/canaan/k230-uart-progress.c module/
  cat > module/Makefile <<EOF
  obj-y += 8250_core.o timer-riscv.o k230-uart-progress.o
  ccflags-y += -DCONFIG_K230_UART_PROGRESS=1 -I${kernel.src}/include -I${kernel.src}/drivers/tty/serial/8250
  EOF
  if ! make -C ${baseKernel.dev}/lib/modules/7.3.0-rc5/source \
    O=$PWD/build M=$PWD/module ARCH=riscv \
    CROSS_COMPILE=${crossCc}/bin/riscv64-unknown-linux-gnu- W=1 \
    8250_core.o timer-riscv.o k230-uart-progress.o > $out/compile.log 2>&1; then
    cat $out/compile.log >&2
    exit 1
  fi
  cp module/*.o $out/
  cp build/.config $out/installed-base.config
  printf '%s\n' '-DCONFIG_K230_UART_PROGRESS=1' > $out/diagnostic-config-overlay.txt
  for object in $out/*.o; do
    readelf -hSWs "$object" >> $out/readelf.txt
  done
  sha256sum $out/*.o $out/installed-base.config > $out/SHA256SUMS
  printf '%s\n' ${kernel.src} > $out/source-path.txt
''
