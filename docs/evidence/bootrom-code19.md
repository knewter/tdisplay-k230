# K230 BootROM code 19 observation

On 2026-09-29, a UART0 capture from the T-Display K230 recorded:

```
boot failed with exit code 19
```

Canaan's [K230 SDK FAQ, “Bootrom Startup Error Codes”](https://github.com/kendryte/k230_docs/blob/main/en/03_other/K230_SDK_FAQ_C.md#bootrom-startup-error-codes)
defines 19 as “Boot medium initialization failed,” giving no SD card as an
example. This places the observed failure before U-Boot stage 1. The line does
not distinguish a missing/unreadable SD card from other boot-medium
initialization faults, and it does not prove the OS image contents are bad.

The capture did not expose the board's TF card as a host block device. A
separate USB card reader on the host contained a single FAT32 partition named
`System`; the known K230 image has two Linux-type partitions, so that reader
card was not treated as the K230 image and was not modified.
