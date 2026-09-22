# KFENCE observation during USB and UMS records

The Linux boots recorded during the USB sessions emit KFENCE memory-corruption
warnings while the USB host enumerates the attached Realtek LAN adapter. This
is an observation of the logs, not a diagnosed cause.

## What is observed

The primary KFENCE report sites and their allocation/free stacks are:

- `hub_port_init+0x4ac/0xcc8`; the allocation stack names
  `usb_get_device_descriptor+0x64/0xb4`, while the free is in
  `hub_port_init`;
- in two records, a second report at
  `usb_get_bos_descriptor+0xbc/0x308`; its allocation is also in
  `usb_get_bos_descriptor`;
- the workqueue is `usb_hub_wq hub_event`.

The descriptor functions above are stack evidence for the allocations and
are not, by themselves, proof of the original corrupting write.

The device then identified by Linux is USB `2-1`, vendor/product `0bda:8152`,
`USB 10/100 LAN`. The `r8152` driver resets it, assigns a random address after
reporting an all-zero address, creates `eth0`, and later renames it `enu1`.
These messages establish the concrete USB path involved; they do not establish
which write corrupted which allocation.

## This predates the current flash record

The warning is repeated in the earlier read-only UMS preflight record
(`docs/evidence/uboot-ums-preflight-codex.txt`, KFENCE at approximately 5.065
seconds), in the media-pull record (`docs/evidence/shell-media-usb-pull.txt`,
approximately 5.089 seconds), and in the corrected flash record
(`docs/evidence/shell-usb-flash-corrected.txt`, approximately 4.770 seconds).
The host-coexistence record repeats it too, with both the device-descriptor and
BOS-descriptor warnings (`docs/evidence/uboot-usb-host-coexist.txt`, approximately
5.083 and 5.301 seconds). Therefore the current host-side flash or media-pull
operation must not be named as the cause based on these records alone.

The logs also show `irq 85: nobody cared` in the DWC2 interrupt handler before
the KFENCE warning. That is a separate correlated observation and should not be
treated as proof that either DWC2 or the descriptor parser caused the overwrite.

## What continued successfully

Despite the warnings, each cited Linux boot continues through USB enumeration:
`r8152 ... eth0` and the later `enu1` rename appear in the logs. The corrected
flash record reaches the login prompt after writing and directly verifying all
2,308,689,920 image bytes; the UMS session ends with status 0. The media-pull
and preflight records also reach the Linux login prompt and end their UMS
records with status 0. The coexistence record reaches `Started sway on the
panel` and the Linux login prompt.

This does not prove that the USB warning is harmless, that the LAN traffic is
reliable, or that unrelated memory has not been corrupted. It only records
that these boots reached the shell/login path after the warning.

## Next investigation

The `0bda:8152` device is the board's onboard RTL8152B behind `usbotg1`
(`usb-otg@91540000`), not a conveniently removable external LAN dongle; see
`docs/uboot-ums.md:72-78`. Reproduce with a serial console and KFENCE enabled
while varying conditions that are actually controllable: boot with and without
the UMS transition, and compare diagnostic kernel/image variants with the
DWC2 host path or the `r8152` driver disabled. Preserve the complete kernel
log and compare the IRQ 85/DWC2 sequence with the USB descriptor sequence.
Disabling only `r8152` would test the later network binding, while disabling the
USB host path would test whether enumeration itself is required. Do not disable
KFENCE or infer a code fix from this observation alone.
