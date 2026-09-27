#!/usr/bin/env sh
# Read-only K230 CPU/firmware handoff snapshot. It never writes sysfs/MMIO,
# invokes SBI, or changes CPU state. MMIO is opt-in and opens only the exact
# documented registers with O_RDONLY and PROT_READ. SECOND_CORE_ROOT,
# SECOND_CORE_DMESG_FILE and SECOND_CORE_MMIO_FILE support the host fixture.
set -eu

root=${SECOND_CORE_ROOT:-/}
dmesg_file=${SECOND_CORE_DMESG_FILE:-}
path() { printf '%s%s' "$root" "$1"; }
read_text() {
  label=$1 file=$2
  printf '%s=' "$label"
  if [ -r "$file" ]; then tr '\000' '\n' < "$file"; else printf '<unreadable>\n'; fi
}
read_hex() {
  label=$1 file=$2
  printf '%s=' "$label"
  if [ -r "$file" ]; then od -An -v -tx1 "$file" | tr -s ' ' | sed 's/^ //; s/ /:/g'; else printf '<unreadable>'; fi
  printf '\n'
}
read_mmio() {
  label=$1 address=$2
  if [ "${SECOND_CORE_READ_MMIO:-0}" != 1 ]; then
    printf '%s=<not-requested>\n' "$label"
    return
  fi
  python3 - "${SECOND_CORE_MMIO_FILE:-/dev/mem}" "$address" "$label" <<'PY'
import mmap
import errno
import os
import struct
import sys

path, address_text, label = sys.argv[1:]
address = int(address_text, 16)
page_size = mmap.PAGESIZE
try:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_SYNC", 0))
    try:
        with mmap.mmap(fd, page_size, flags=mmap.MAP_SHARED,
                       prot=mmap.PROT_READ, offset=address & -page_size) as area:
            value, = struct.unpack_from("<I", area, address % page_size)
    finally:
        os.close(fd)
except OSError as error:
    print(f"{label}=<unavailable:{errno.errorcode.get(error.errno, 'UNKNOWN')}>")
else:
    print(f"{label}=0x{value:08x}")
PY
}

printf 'second-core-readiness v2\n'
printf 'captured-utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'source-root=%s\n' "$root"
read_text cpu_possible "$(path /sys/devices/system/cpu/possible)"
read_text cpu_present "$(path /sys/devices/system/cpu/present)"
read_text cpu_online "$(path /sys/devices/system/cpu/online)"
read_text cpu_offline "$(path /sys/devices/system/cpu/offline)"
read_mmio cpu1_rst_ctl 0x9110100c
read_mmio cpu1_pwr_ctl 0x91103018
read_mmio cpu1_pwr_status 0x9110301c

cpus="$(path /proc/device-tree/cpus)"
if [ -d "$cpus" ]; then
  for node in "$cpus"/cpu@*; do
    [ -d "$node" ] || continue
    printf 'cpu-node=%s\n' "${node##*/}"
    read_hex "${node##*/}.reg" "$node/reg"
    read_text "${node##*/}.status" "$node/status"
    read_text "${node##*/}.isa" "$node/riscv,isa"
  done
else
  printf 'cpu-node=<unreadable>\n'
fi

read_hex plic_interrupts_extended "$(path /proc/device-tree/soc/interrupt-controller@f00000000/interrupts-extended)"
read_hex timer_interrupts_extended "$(path /proc/device-tree/soc/timer@f04000000/interrupts-extended)"

cpuinfo="$(path /proc/cpuinfo)"
printf '%s\n' 'cpuinfo:'
if [ -r "$cpuinfo" ]; then
  grep -E '^(processor|hart|isa|mmu|uarch|mvendorid|marchid|mimpid)[[:space:]]*:' "$cpuinfo" || true
else
  printf '<unreadable>\n'
fi

for cache in "$(path /sys/devices/system/cpu/cpu0/cache)"/index*; do
  [ -d "$cache" ] || continue
  printf 'cache-node=%s\n' "${cache##*/}"
  read_text "${cache##*/}.level" "$cache/level"
  read_text "${cache##*/}.type" "$cache/type"
  read_text "${cache##*/}.size" "$cache/size"
done

printf '%s\n' 'sbi-and-smp-log:'
if [ -n "$dmesg_file" ]; then
  log_source=$dmesg_file
  if [ -r "$log_source" ]; then
    grep -E 'Platform (HART Count|IPI Device|Timer Device|HSM Device)|Domain0 HARTs|SBI HSM extension|smp:|SMP:' "$log_source" || true
  else
    printf '<unreadable>\n'
  fi
elif command -v dmesg >/dev/null 2>&1; then
  dmesg 2>/dev/null | grep -E 'Platform (HART Count|IPI Device|Timer Device|HSM Device)|Domain0 HARTs|SBI HSM extension|smp:|SMP:' || true
else
  printf '<dmesg-unavailable>\n'
fi
