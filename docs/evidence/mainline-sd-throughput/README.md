# SD throughput: vendor 6.6 vs mainline 7.3 (same board, same card)

2026-10-08, America/Chicago. Physical board; root coordinator held the serial lock.
Evidence class: reserved physical-board serial commands. Card: `mmc1:59b4 EC1S5`
59.7 GiB SDXC. Vendor was a volatile boot of the protected vendor backup
(`coherent-shell-board-boot.py --recover-baseline`); mainline is the installed
normal. Commands, run as root on each kernel:

```
cat /sys/kernel/debug/mmc1/ios
dd if=/dev/mmcblk1 of=/dev/null bs=4M count=32 skip=200 iflag=direct
dd if=/dev/mmcblk1 of=/dev/null bs=128k count=512 skip=9000 iflag=direct
head -c 67108864 /dev/zero | sha256sum   # timed, CPU reference
grep mmc /proc/interrupts
```

| | vendor 6.6.36 | mainline 7.3.0-rc5 |
|---|---|---|
| ios clock / actual clock | 50000000 / 50000000 Hz | 50000000 / 41625000 Hz |
| timing, width, voltage | SD high-speed, 4-bit, 3.30 V | SD high-speed, 4-bit, 3.30 V |
| dd 4 MiB direct read | 23.3 MB/s | 6.1 MB/s |
| dd 128 KiB direct read | 22.2 MB/s | 5.9 MB/s |
| sha256 of 64 MiB | 1512 ms | 1473 ms |
| mmc1 IRQs per 64 MiB read | — | 256 |

Vendor `clk_summary` shows sdhci1's consumer clock is the fixed 100 MHz
`dummy_sd`; SD AXI/bus gates run at 333 MHz, card-clock source gates at 200 MHz.
Mainline's reported actual clock is exactly 333 MHz / 8. CPU speed and
interrupt counts are normal, so transfers are healthy but the card clock is slow.

## After the fix: trial boot (task 2.1)

The fix gives `core` a fixed 100 MHz reference (`sd_ref`) on both controllers
and keeps `HS_SD*_BASE_GATE` claimed as `base` (commit `b20be921`). Bundle
`/nix/store/p3hh3j326i6vh12q9mgx1r9qnfwi4zrv-k230-coherent-shell-boot-files`, system
`kp6ldmdx…`, kernel `zv590h93…-7.3.0-rc5`. Host inspection: PASS. It was staged with
the coherent stage tool at
`/var/lib/k230/coherent-boot/kp6ldmdx33lgjl55hzv3xba5a55ils48-20261008`
([staged-state.json](staged-state.json)) and volatile-booted with
`tools/coherent-shell-board-boot.py`
([trial-serial-result.json](trial-serial-result.json): PASS, three services active).

| | mainline before | mainline after fix | vendor 6.6.36 |
|---|---|---|---|
| mmc1 actual clock | 41625000 Hz | 50000000 Hz | 50000000 Hz |
| mmc0 (SDIO) actual clock | 41625000 Hz | 50000000 Hz | 50000000 Hz |
| dd 4 MiB direct read | 6.1 MB/s | 23.8 MB/s | 23.3 MB/s |
| dd 128 KiB direct read | 5.9 MB/s | 22.0 MB/s | 22.2 MB/s |

`clk_summary`: `sd_ref` is 100 MHz with 2 consumers. All ten
`hs_sd{0,1}_{base,ahb,axi,card,timer}_gate` remain enabled (count 1). That
means no gate was released to unused-clock cleanup.

Integrity: the same 256 MiB region read twice (4 MiB and 1 MiB direct
blocks) gave an identical SHA-256. Wi-Fi: `wlan0` associated over SDIO and
held an IPv4 address (SSID and address withheld). PDMA: `aplay -D hw:0,0` of 3 s
of silence exited 0, with no DMA/oops messages and services still active. `Got
command interrupt` count on this boot: 0.
