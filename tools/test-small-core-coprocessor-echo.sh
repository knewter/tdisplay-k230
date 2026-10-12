#!/usr/bin/env bash
# Host-only ELF and image proof for the CPU0 echo/ping payload.
# This script never touches the board. Method follows
# tools/test-small-core-heartbeat.sh.
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if [ -n "${SMALL_CORE_OUTPUT_DIR:-}" ]; then
  out=$SMALL_CORE_OUTPUT_DIR
  mkdir -p "$out"
else
  out=$(mktemp -d)
  trap 'rm -rf "$out"' EXIT
fi

build() { # build <dir> [extra lld args]
  local d=$1; shift
  mkdir -p "$d"
  clang --target=riscv64-unknown-elf -march=rv64imac_zicsr -mabi=lp64 -fuse-ld=lld \
    -nostdlib -fno-pic -Wl,--no-relax "$@" -Wl,-T,"$repo/tools/small-core-echo.ld" \
    -o "$d/echo.elf" "$repo/tools/small-core-echo.S"
  llvm-objcopy -O binary "$d/echo.elf" "$d/echo.bin"
  llvm-objdump -d "$d/echo.elf" > "$d/disassembly.txt"
  readelf -A "$d/echo.elf" > "$d/attributes.txt"
}

fail() { echo "$*" >&2; exit 1; }

build "$out"
readelf -h "$out/echo.elf" | grep -Eq 'Entry point address:[[:space:]]+0x7000000$' \
  || fail 'entry is not the default PAYLOAD_BASE 0x07000000'
readelf -s "$out/echo.elf" | grep -Eq '0+7002000[[:space:]].*echo_page' \
  || fail 'echo_page is not PAYLOAD_BASE+0x2000'
size=$(stat -c %s "$out/echo.bin")
[ "$size" -le 4096 ] || fail "image $size bytes exceeds the first 4 KiB page"

# Scalar RV64 only, no V extension.
grep -Fq 'Tag_RISCV_arch: "rv64i' "$out/attributes.txt" || fail 'unexpected arch attribute'
if grep -Eq 'Tag_RISCV_arch:.*_v[0-9]' "$out/attributes.txt"; then
  fail 'unexpected V extension in CPU0 payload ELF attributes'
fi
if grep -Eiq '[[:space:]](vsetvli|vsetivli|vl[a-z0-9]*\.v|vs[a-z0-9]*\.v|vadd|vsub|vmul)' "$out/disassembly.txt"; then
  fail 'unexpected vector instruction in CPU0 payload'
fi

# The poll/echo state machine is present: request load, compare, response
# stores, sequence word last (fence w,w before it), heartbeat doubleword.
for pat in 'csrr[[:space:]]+t1, mhartid' 'csrr[[:space:]]+t1, misa' \
           'lwu[[:space:]]+t1, 0x0\(s0\)' 'bne[[:space:]]+t1, s1' \
           'lw[[:space:]]+t2, 0x4\(s0\)' 'addiw[[:space:]]+t4, t2, 0x1' \
           'not[[:space:]]+t4, t2' 'fence[[:space:]]+w, w' \
           'sw[[:space:]]+t1, 0x0\(t3\)' 'sd[[:space:]]+s3, 0x40\(s0\)'; do
  grep -Eq "$pat" "$out/disassembly.txt" || fail "missing instruction pattern: $pat"
done

# The pinned l2cache.ciall word (0x0170000b) is issued before the request
# read (poll), after the heartbeat publish, after the response publish and
# after the initial zeroing: at least four sites, each preceded by a fence rw,rw.
n=$(grep -c '\.word[[:space:]]*0x0170000b' "$out/disassembly.txt")
[ "$n" -ge 4 ] || fail "expected >=4 l2cache.ciall sites, found $n"
if [ "$(grep -B1 '\.word[[:space:]]*0x0170000b' "$out/disassembly.txt" | grep -c 'fence[[:space:]]*rw, rw')" -ne "$n" ]; then
  fail 'an l2cache.ciall is not preceded by fence rw, rw'
fi

# No access to the reset / vector / boot MMIO block (0x9110_xxxx) and no
# lui/auipc building such an address.
if grep -Eiq '0x9110|0x91101|0x91102|0x91103|0x91104' "$out/disassembly.txt"; then
  fail 'payload references the 0x9110xxxx system-control MMIO block'
fi
if grep -Eq '(lui|auipc)[[:space:]]+[a-z0-9]+, 0x9[0-9a-f]{4}$' "$out/disassembly.txt"; then
  fail 'payload builds an MMIO-range (0x9xxxxxxx) address'
fi
# Only CSRs read: mhartid and misa; no csrw/csrrw/csrs/csrc.
if grep -Eq '[[:space:]](csrw|csrrw|csrs|csrc|csrrwi|csrrsi|csrrci)[[:space:]]' "$out/disassembly.txt"; then
  fail 'payload writes a CSR'
fi

# The load address is a single constant: relinking at another base moves the
# entry and the slot page together and the code is unchanged.
mkdir -p "$out/moved"
echo 'PAYLOAD_BASE = 0x20000000;' > "$out/moved/base.ld"
build "$out/moved" -Wl,-T,"$out/moved/base.ld"
readelf -h "$out/moved/echo.elf" | grep -Eq 'Entry point address:[[:space:]]+0x20000000$' \
  || fail 'PAYLOAD_BASE override did not move the entry'
readelf -s "$out/moved/echo.elf" | grep -Eq '0+20002000[[:space:]].*echo_page' \
  || fail 'PAYLOAD_BASE override did not move echo_page'
cmp -s "$out/echo.bin" "$out/moved/echo.bin" \
  || fail 'image differs after relinking at another base (code holds an absolute address)'

printf '%s\n' "small-core echo host image: PASS (entry 0x07000000, slot page 0x07002000, $size bytes, $n l2cache.ciall sites, scalar RV64, no 0x9110xxxx access, position-independent across PAYLOAD_BASE)"
sha256sum "$out/echo.bin"
python3 -c 'import sys,zlib;print("crc32 %08x" % zlib.crc32(open(sys.argv[1],"rb").read()))' "$out/echo.bin"
