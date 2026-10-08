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
