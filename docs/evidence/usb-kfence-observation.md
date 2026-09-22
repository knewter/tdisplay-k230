# KFENCE observation during USB and UMS records

The Linux boots recorded during the USB sessions emit KFENCE memory-corruption
warnings while the USB host enumerates the attached Realtek LAN adapter. This
is an observation of the logs, not a diagnosed cause.

## What is observed

The affected call paths are:

- `hub_port_init+0x4ac/0xcc8`, followed by `usb_get_device_descriptor+0x64/0xb4`;
- in two records, a second warning at `usb_get_bos_descriptor+0xbc/0x308`;
- the workqueue is `usb_hub_wq hub_event`.

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

Reproduce with a serial console and KFENCE enabled while varying one condition
at a time: the attached USB LAN device, the DWC2 host controller, and the UMS
gadget/boot transition. Preserve the complete kernel log and compare the IRQ
85/DWC2 sequence with the USB descriptor sequence. Check whether the warning
still occurs with no UMS session and whether the same image boots with the
external LAN device absent. Do not disable KFENCE or infer a code fix from this
observation alone.
