#!/usr/bin/env bash
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
fixture=$(mktemp -d)
trap 'rm -rf "$fixture"' EXIT
mkdir -p "$fixture"/{sys/devices/system/cpu,proc/device-tree/cpus/cpu@0,proc/device-tree/soc/interrupt-controller@f00000000,proc/device-tree/soc/timer@f04000000,proc}
printf '0\n' > "$fixture/sys/devices/system/cpu/possible"
printf '0\n' > "$fixture/sys/devices/system/cpu/present"
printf '0\n' > "$fixture/sys/devices/system/cpu/online"
printf '\0\0\0\0' > "$fixture/proc/device-tree/cpus/cpu@0/reg"
printf 'okay\0' > "$fixture/proc/device-tree/cpus/cpu@0/status"
printf 'rv64imafdcv\0' > "$fixture/proc/device-tree/cpus/cpu@0/riscv,isa"
printf '\0\0\0\1\0\0\0\013' > "$fixture/proc/device-tree/soc/interrupt-controller@f00000000/interrupts-extended"
printf '\0\0\0\1\0\0\0\003' > "$fixture/proc/device-tree/soc/timer@f04000000/interrupts-extended"
printf 'processor\t: 0\nhart\t\t: 0\nuarch\t\t: thead,c908\n' > "$fixture/proc/cpuinfo"
printf 'Platform HART Count       : 1\nPlatform HSM Device       : ---\nDomain0 HARTs             : 0*\n[ 0.1] smp: Brought up 1 node, 1 CPU\n' > "$fixture/dmesg"
out=$(SECOND_CORE_ROOT="$fixture" SECOND_CORE_DMESG_FILE="$fixture/dmesg" "$repo/tools/second-core-readiness.sh")
grep -Fqx 'cpu_possible=0' <<<"$out"
grep -Fqx 'cpu@0.reg=00:00:00:00' <<<"$out"
grep -Fqx 'plic_interrupts_extended=00:00:00:01:00:00:00:0b' <<<"$out"
grep -Fqx 'Platform HART Count       : 1' <<<"$out"
grep -Fqx '[ 0.1] smp: Brought up 1 node, 1 CPU' <<<"$out"
printf '%s\n' 'second-core-readiness fixture: PASS'
