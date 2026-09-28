#!/usr/bin/env bash
# Host-only ELF and image proof. This script never touches the board.
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if [ -n "${SMALL_CORE_OUTPUT_DIR:-}" ]; then
  out=$SMALL_CORE_OUTPUT_DIR
  mkdir -p "$out"
else
  out=$(mktemp -d)
  trap 'rm -rf "$out"' EXIT
fi

clang --target=riscv64-unknown-elf -march=rv64imac_zicsr -mabi=lp64 -fuse-ld=lld \
  -nostdlib -fno-pic -Wl,--no-relax -Wl,-T,"$repo/tools/small-core-heartbeat.ld" \
  -o "$out/heartbeat.elf" "$repo/tools/small-core-heartbeat.S"
llvm-objcopy -O binary "$out/heartbeat.elf" "$out/heartbeat.bin"
llvm-objdump -d "$out/heartbeat.elf" > "$out/disassembly.txt"
readelf -A "$out/heartbeat.elf" > "$out/attributes.txt"
readelf -h "$out/heartbeat.elf" | grep -Eq 'Entry point address:[[:space:]]+0x7000000$'
readelf -s "$out/heartbeat.elf" | grep -Eq '0+7002000[[:space:]].*heartbeat_output'
[ "$(stat -c %s "$out/heartbeat.bin")" -le 4096 ]
grep -Fq 'csrr' "$out/disassembly.txt"
grep -Fq 'fence' "$out/disassembly.txt"
grep -Fq 'Tag_RISCV_arch: "rv64i' "$out/attributes.txt"
if grep -Eq 'Tag_RISCV_arch:.*_v[0-9]' "$out/attributes.txt"; then
  echo 'unexpected V extension in CPU0 payload ELF attributes' >&2
  exit 1
fi
if grep -Eiq '[[:space:]](vsetvli|vsetivli|vle[0-9]|vse[0-9]|vadd|vsub|vmul)' "$out/disassembly.txt"; then
  echo 'unexpected vector instruction in CPU0 payload' >&2
  exit 1
fi
grep -Fq 'lui' "$out/disassembly.txt"
grep -Fq '0x7003' "$out/disassembly.txt"
grep -Fq '0x7004' "$out/disassembly.txt"
printf '%s\n' 'small-core heartbeat host image: PASS (entry 0x07000000, output 0x07002000/0x07003000/0x07004000, scalar RV64)'
if [ -n "${SMALL_CORE_OUTPUT_DIR:-}" ]; then
  sha256sum "$out/heartbeat.bin"
fi
