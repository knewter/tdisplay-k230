#!/usr/bin/env sh
# Read-only K230 CPU/firmware handoff snapshot.  It never writes sysfs/MMIO,
# invokes SBI, or changes CPU state.  SECOND_CORE_ROOT and SECOND_CORE_DMESG_FILE
# exist solely to run the host fixture test.
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

printf 'second-core-readiness v1\n'
printf 'captured-utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'source-root=%s\n' "$root"
read_text cpu_possible "$(path /sys/devices/system/cpu/possible)"
read_text cpu_present "$(path /sys/devices/system/cpu/present)"
read_text cpu_online "$(path /sys/devices/system/cpu/online)"
read_text cpu_offline "$(path /sys/devices/system/cpu/offline)"

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
