# Exact selected-kernel prepared headers: three objects, no kernel/module link.
# Realizing this output requires the matching kernel.dev; root owns that build.
{ runCommand, gnumake, python3, binutils, crossCc, kernel }:
runCommand "k230-mainline-uart-progress-exact-objects" {
  nativeBuildInputs = [ gnumake python3 binutils crossCc ];
} ''
  mkdir -p build module $out
  cp -r ${kernel.dev}/lib/modules/7.3.0-rc5/build/. build/
  chmod -R u+w build
  python3 - <<'PYCONFIG'
  from pathlib import Path
  config = Path('build/.config').read_text().splitlines()
  assert [line for line in config if line.startswith('CONFIG_K230_UART_PROGRESS=')] == ['CONFIG_K230_UART_PROGRESS=y']
  autoconf = Path('build/include/generated/autoconf.h').read_text().splitlines()
  assert [line for line in autoconf if line.startswith('#define CONFIG_K230_UART_PROGRESS ')] == ['#define CONFIG_K230_UART_PROGRESS 1']
  PYCONFIG
  cp build/.config $out/installed-kernel.config
  cp build/include/generated/autoconf.h $out/installed-autoconf.h
  cp ${kernel.src}/drivers/tty/serial/8250/8250_core.c module/
  cp ${kernel.src}/drivers/tty/serial/8250/8250.h module/
  cp ${kernel.src}/drivers/clocksource/timer-riscv.c module/
  cp ${kernel.src}/drivers/soc/canaan/k230-uart-progress.c module/
  cat > module/Makefile <<EOF
  obj-y += 8250_core.o timer-riscv.o k230-uart-progress.o
  ccflags-y += -I${kernel.src}/include -I${kernel.src}/drivers/tty/serial/8250
  EOF
  if ! make -C ${kernel.dev}/lib/modules/7.3.0-rc5/source \
    O=$PWD/build M=$PWD/module ARCH=riscv \
    CROSS_COMPILE=${crossCc}/bin/riscv64-unknown-linux-gnu- W=1 \
    8250_core.o timer-riscv.o k230-uart-progress.o > $out/compile.log 2>&1; then
    cat $out/compile.log >&2
    exit 1
  fi
  cp module/*.o $out/
  cmp build/.config $out/installed-kernel.config
  cmp build/include/generated/autoconf.h $out/installed-autoconf.h
  for object in $out/*.o; do
    readelf -hSWs "$object" >> $out/readelf.txt
  done
  sha256sum $out/*.o $out/installed-kernel.config $out/installed-autoconf.h > $out/SHA256SUMS
  printf '%s\n' ${kernel.src} > $out/source-path.txt
  printf '%s\n' ${kernel.dev} > $out/dev-path.txt
''
