# RTC day-of-month mask fix: board verification

Board operator session, `fix/backlight-rtc-board-findings`, base `master`
@ `3d65166c`. Verified against the toplevel built from this branch,
deployed to `/boot` via export/import + bootfetch/bootswap, confirmed by a
real cold reboot (`init=` in `/proc/cmdline` matches the new toplevel).

## Bug and fix

`drivers/rtc/rtc-k230.c:136` (pinned kernel tree) read:

```c
tm->tm_mday = (date_value >> DATE_DAY_OFFSET) & 0xf;
```

Four bits (max 15) for a field that needs five (1..31). The write side
(`k230_rtc_set_time()`) shifts the full `tm_mday` into the register with no
mask, so the hardware register itself holds the correct value; only the
*read-back* path truncated it. Board evidence for the bug, from the
coordinator's report: `hwclock --set` to day 15 read back 15 (`15 & 0xf ==
15`, no visible effect below 16), but day 26 read back 10
(`0b11010 & 0b01111 == 0b01010 == 10`).

Fix, `nix/patches/k230-rtc-mday-mask.patch`, one line:

```diff
-	tm->tm_mday = (date_value >> DATE_DAY_OFFSET) & 0xf;
+	tm->tm_mday = (date_value >> DATE_DAY_OFFSET) & 0x1f;
```

## Verification

Set and read back four days, including the bit-4 boundary case (16) and
the two days the original bug report named (15, 26):

```
$ hwclock --set --date '2026-09-15 12:00:00' && hwclock -r
2026-09-15 12:00:00.009037+00:00        # OK (matches; also matched under the old buggy mask, not a discriminating case)

$ hwclock --set --date '2026-09-16 12:00:00' && hwclock -r
2026-09-16 12:00:00.004597+00:00        # OK -- this is the discriminating case: 16 = 0b10000,
                                         # the old `& 0xf` mask would have read back day 0

$ hwclock --set --date '2026-09-26 12:00:00' && hwclock -r
2026-09-26 12:00:00.006224+00:00        # OK -- exactly the day named in the original bug report
                                         # (old mask: 26 & 0xf == 10)

$ hwclock --set --date '2026-10-31 12:00:00' && hwclock -r
2026-10-31 12:00:00.006449+00:00        # OK -- top of the valid range
```

All four read back exactly as set.

## Reboot persistence (hctosys)

The RTC was set to the real current time (`2026-09-26 17:33:24`) and the
board was rebooted normally (not the one-shot boot-new path — this is a
real cold boot from the `/boot` this branch's `bootswap.sh` installed).
Kernel log from that boot:

```
[    4.547130] k230-rtc 91000c00.rtc: registered as rtc0
[    4.555695] k230-rtc 91000c00.rtc: setting system clock to 2026-09-26T17:34:36 UTC (1790444076)
```

`hctosys` set the system clock to `17:34:36`, ~72 seconds after the RTC was
last set to `17:33:24` — consistent with the real elapsed reboot time, not
a reset to the kernel's compiled-in epoch. Post-boot:

```
$ hwclock -r; date
2026-09-26 17:36:56.844333+00:00
Sat Sep 26 05:36:57 PM UTC 2026
```

Today's actual date is day 26 of the month — every one of these
post-fix reads is itself a live instance of the exact case that was
broken before this patch.

## Left as `UNVERIFIED`

Survival across a full power-off (main power removed, not a warm reboot)
was not tested this session and remains `UNVERIFIED` per
`openspec/changes/the-clock-survives-a-reboot/tasks.md` task 4.2 — no
backing supply for this RTC domain is documented anywhere in this
repository or LILYGO's published material.
