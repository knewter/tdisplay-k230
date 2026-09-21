# GT9895 touch: no port needed, the interrupt trigger was wrong

Investigated 2026-09-21, after `docs/evidence/touch-probe.txt` established
that the backported `goodix_berlin` binds at i2c 1-005d, the controller
answers 32-bit-addressed i2c reads, and IRQ 87 has counted **4** interrupts
since boot where a 40-second drag should give thousands.

**Conclusion: the driver is correct and needs no change. The device tree
declared the touch interrupt as `IRQ_TYPE_EDGE_FALLING`; a Goodix Berlin
part needs `IRQ_TYPE_LEVEL_LOW`.** The fix is device-tree-only, so it costs a
DTB rebuild (seconds) rather than a kernel cross-compile.

The change is in `nix/dts/k230-tdisplay.dts`. Nothing was added to
`nix/kernel.nix` and no patch was added under `nix/patches/`, because
nothing in the kernel is wrong. Section 5 says why the driver-side change
that was on the table is a no-op.

---

## 1. The IC-info blob parses correctly. READ, then ARITHMETIC.

This was the leading hypothesis — that `goodix_berlin_get_ic_info()`
silently mis-parses the GT9895's blob and derives a wrong `touch_data_addr`,
so the driver waits forever on data written somewhere else. **It is wrong.**
The parse is self-consistent to the byte.

### What was read off the part (from `touch-probe.txt`, captured on hardware)

```
$ i2ctransfer -f -y 1 w4@0x5d 0x00 0x01 0x00 0x70 r16     # IC info, 0x10070
0xad 0x00 0x01 0x00 0x00 0x00 0x22 0xfc 0x0b 0x65 0x02 0x01 0x00 0x01 0x00 0x00
```

### Decoded by hand against the driver's own structs

`goodix_berlin_get_ic_info()`
(`nix/patches/goodix-berlin/goodix_berlin_core.c:359`) reads a `__le16`
length first, then re-reads that many bytes.

| blob offset | bytes | field | value |
|---|---|---|---|
| 0–1 | `ad 00` | `length` | **173** |
| 2 | `01` | `info_customer_id` | 1 |
| 3 | `00` | `info_version_id` | 0 |
| 4 | `00` | `ic_die_id` | 0 |
| 5 | `00` | `ic_version_id` | 0 |
| 6–9 | `22 fc 0b 65` | `config_id` | 0x650BFC22 |
| 10 | `02` | `config_version` | 2 |
| 11 | `01` | `frame_data_customer_id` | 1 |
| 12 | `00` | `frame_data_version_id` | 0 |
| 13 | `01` | `touch_data_customer_id` | 1 |
| 14 | `00` | `touch_data_version_id` | 0 |
| 15–17 | `00` … | `reserved[3]` | — |

Field names and order are `struct goodix_berlin_ic_info_version`,
`goodix_berlin_core.c:75-87`. Every value is in range; none is 0x00/0xff
filler. `length = 173` passes the driver's `>= SZ_1K` guard at
`goodix_berlin_core.c:378`.

### The length is exactly right for the driver's struct layout

`goodix_berlin_parse_ic_info()` (`goodix_berlin_core.c:319`) walks:

```
  2  __le16 length
 16  struct goodix_berlin_ic_info_version
 10  struct goodix_berlin_ic_info_feature
  4  drv_num, sen_num, button_num, force_num
  V  5 variable arrays, each 1 count byte + count * __le16
114  struct goodix_berlin_ic_info_misc
  2  trailing checksum
```

Sizes verified by compiling the structs and taking `sizeof`, not by eye:
version 16, feature 10, misc 114, and `offsetof(misc, touch_data_addr)` 44.

```
173 = 2 + 16 + 10 + 4 + V + 114 + 2   ->   V = 25 = 5 + 2 * 10
```

**V = 25 means the five count bytes sum to exactly 10.** That is a whole
number of `__le16` entries and it makes the 114-byte misc struct end exactly
at the two checksum bytes. If the driver's structs did not match this part's
blob, that sum would not have come out integral and misc would not have
landed flush against the checksum.

So `misc` starts at blob offset 57, `touch_data_addr` is read from blob
offset 101, and the `if (offset >= length) goto invalid_offset` guards at
`goodix_berlin_core.c:331` and `:338` cannot fire (57 < 173).

**Inferred, not observed:** the exact value it reads. But see §2 — LILYGO's
own driver hardcodes `0x00010308`, and `goodix_berlin_get_ic_info()` rejects
a zero `touch_data_addr` at `goodix_berlin_core.c:406` and did not, so
whatever it got was non-zero and the probe succeeded.

Also worth stating: `goodix_berlin_read_version()` at `:298` checksums a
16-byte struct read from a **hardcoded** 0x10014 and did not fail. A
mis-parse of the *layout* cannot explain that read succeeding.

## 2. LILYGO's own GT9895 driver: no init sequence at all, and it confirms the layout

`repo/canmv_k230/src/rtsmart/rtsmart/kernel/bsp/maix3/drivers/extdrv/touch/gt9895.c`,
219 lines, is the whole thing. **There is no init sequence, no reset, no
config upload, no firmware upload, and no interrupt handling.** `gt9895_init()`
(line 205) registers an RT-Thread touch device; `gt9895_register()` (line 171)
opens the i2c bus and sets `point_num = 10`, `range_x = 568`, `range_y = 1232`.
That is the entire bring-up. The part is used exactly as it comes out of
reset.

This kills the "missing config/firmware upload" hypothesis: the shipped
firmware that works on this board uploads nothing.

What it does do is **poll**, and that is where the useful register facts are.
`gt9895_read_point()` (line 86):

```c
rt_uint8_t buffer_addr[4] = { 0x00, 0x01, 0x03, 0x08 };          /* line 99  */
ret = gt9895_read_reg(..., buffer_addr, rdbuf, sizeof(rdbuf));   /* line 100 */
valid_point = rdbuf[2] & 0xf;                                    /* line 110 */
offset = 8;                                                      /* line 114 */
... x = rdbuf[offset+2] | rdbuf[offset+3]<<8;                    /* line 130 */
    y = rdbuf[offset+4] | rdbuf[offset+5]<<8;                    /* line 132 */
    w = rdbuf[offset+6];  offset += 8;                           /* line 134,136 */
```

with `rdbuf[touch->info.point_num * 9]` = 90 bytes (line 92).

Line by line against the Berlin driver:

| RT-Smart | `goodix_berlin` | agree? |
|---|---|---|
| address `0x00010308` | `cd->touch_data_addr`, from IC-info | address to derive |
| read 90 bytes | 8 hdr + 10 × 8 points + 2 checksum = 90 | yes, exactly |
| `rdbuf[2] & 0xf` | `FIELD_GET(GENMASK(3,0), hdr.request_type)`, `:477` — `request_type` is header byte 2 | yes |
| points start at 8 | `GOODIX_BERLIN_HEADER_SIZE` = 8, `:155` | yes |
| 8 bytes/point, x@+2 y@+4 w@+6 | `struct goodix_berlin_touch`, `:139-145` | yes |

**The GT9895's touch report is the Berlin report, byte for byte**, and its
`touch_data_addr` is 0x10308. There is nothing for a port to add.

Scaling constants, which matter later: `TOUCH_RESOLUTION_X 1024` and
`TOUCH_RESOLUTION_Y 2400` (lines 44–45), divided into the raw coordinates at
lines 140–141.

## 3. The decisive external evidence: the same driver works on this board with LEVEL_LOW

`caveman99/k230-linux` — already catalogued in
`docs/research/linux-on-t-display-k230.md` §2 as the strongest display lead —
has a `TOUCH-BRINGUP.md` that nobody in this project had read. It runs **the
same mainline `goodix_berlin`, backported into the same XuanTie 6.6.36 tree,
on the same LILYGO T-Display-K230**, and reports working type-B multitouch
verified under `evtest`.

Its device tree node (fetched from
`https://raw.githubusercontent.com/caveman99/k230-linux/main/dts/k230-tdisplay.dts`,
lines 43–57):

```dts
touchscreen@5d {
	compatible = "goodix,gt9895";
	reg = <0x5d>;
	interrupt-parent = <&gpio0_ports>;
	interrupts = <23 IRQ_TYPE_LEVEL_LOW>;
	reset-gpios = <&gpio0_ports 24 GPIO_ACTIVE_LOW>;
	avdd-supply = <&reg_disp_3v3>;
	vddio-supply = <&reg_disp_3v3>;
	touchscreen-size-x = <1024>;
	touchscreen-size-y = <2400>;
};
```

`TOUCH-BRINGUP.md` states, of `/proc/interrupts`: *"The IRQ appears in
`/proc/interrupts` as `gpio-k230 23 Level goodix-berlin`."*

Ours reads `87: 4 gpio-k230 23 Edge goodix-berlin`. **Same controller, same
line, same driver, same kernel — `Level` where we have `Edge`, and theirs
reports touches while ours does not.**

Reset GPIO and INT pin are identical to ours (`24` active-low, `23`), so
those were never the problem. Their doc also confirms the pads: *"INT (IO23)
and RST (IO24) are SEL0=GPIO in U-Boot; no bootloader change is needed."*
Our own 4 counted interrupts independently prove the pad is muxed to GPIO
and that the line physically moves — a mis-muxed pad would have counted zero.

### Where `IRQ_TYPE_EDGE_FALLING` came from

`arch/riscv/boot/dts/canaan/k230-canmv-v3-lcd.dts:61-67` in the pinned tree:

```dts
touchscreen@38 {
	compatible = "edt,edt-ft5306";
	reg = <0x38>;
	reset-gpios = <&gpio0_ports 24 GPIO_ACTIVE_LOW>;
	interrupt-parent = <&gpio0_ports>;
	interrupts = <23 IRQ_TYPE_EDGE_FALLING>;
};
```

An Edtech FT5306. A different part. Our node was cloned from it — the DTS
comment at `nix/dts/k230-tdisplay.dts` said as much ("The GPIOs are the same
as the reference's touch controller") — and the trigger type came along for
the ride. It was never derived from any GT9895 or Goodix Berlin source.

### Why edge-falling does not merely under-report, it dies completely

**This mechanism is inferred, not measured.** The fix does not depend on it
being right; it rests on §3's direct comparison. But it does explain "4, then
nothing":

A Goodix Berlin part asserts INT low and **holds it** until the host clears
the status byte at `touch_data_addr`. `goodix_berlin_irq()` clears that byte
only on the `out_clear` path (`goodix_berlin_core.c:595-597`). The very first
check in the handler is:

```c
if (cd->event.hdr.status == 0)
	goto out;               /* goodix_berlin_core.c:566 — NO clear */
```

So a single interrupt taken while `status` happens to read 0 leaves the line
asserted low with nothing ever clearing it, and an **edge** detector will
never see another falling edge. The line is stuck; the counter freezes. A
**level** detector re-fires immediately instead, and the handler eventually
clears it — self-healing, which is exactly why level is the correct choice
for a hold-until-acknowledged interrupt.

`drivers/gpio/gpio-k230.c:305-345` in the pinned tree handles both:
`IRQ_TYPE_LEVEL_LOW` at `:333`, `irq_set_handler_locked(d, handle_level_irq)`
at `:340`. And `goodix_berlin_probe()` requests the IRQ with `IRQF_ONESHOT`
and **no trigger override** (`goodix_berlin_core.c:780-781`), so whatever the
device tree says is what is programmed.

## 4. `touchscreen-size-x/y` — separate bug, would have bitten next

`goodix_berlin_input_dev_config()` declares the axes as `0 .. SZ_64K - 1`
(`goodix_berlin_core.c:621-624`) and then calls
`touchscreen_parse_properties()` (`:627`) to have the device tree narrow
them. With no `touchscreen-size-*` in the DT, nothing narrows them, and the
input device advertises a 65536-unit range for a sensor that reports
0–1023 × 0–2399. Any client that scales by the advertised maximum collapses
every touch into the top-left ~1.5% of the screen.

`TOUCH-BRINGUP.md` documents hitting exactly this and calls it "the key fix".
The two sources for 1024 × 2400 are independent: LILYGO's RT-Smart driver
(§2, lines 44–45) and caveman99's Linux port (§3).

The panel is 568 × 1232, so the digitizer grid is ~1.80× the pixel grid in X
and ~1.95× in Y — same portrait orientation, so no `touchscreen-swapped-x-y`
or `touchscreen-inverted-*` is wanted.

## 5. Why there is no kernel patch

The obvious driver-side change was to add a `gt9895` entry the way caveman99
did. Their `patches/goodix_berlin/` was fetched and diffed against
`nix/patches/goodix-berlin/`. For the GT9895 it is **functionally a no-op for
us**:

```c
/* caveman99 goodix_berlin_i2c.c */
static const struct goodix_berlin_ic_data gt9895_data = {
	.fw_version_info_addr = GOODIX_BERLIN_FW_VERSION_INFO_ADDR_D,  /* 0x10014 */
	.ic_info_addr         = GOODIX_BERLIN_IC_INFO_ADDR_D,          /* 0x10070 */
};
```

Identical to their `gt9916_data`, and identical to the two constants our
v6.12 backport hardcodes at `goodix_berlin_core.c:56` (`0x10014`) and `:59`
(`0x10070`). Their tree needs the struct only because they took a v6.13+
mainline snapshot that had already replaced the constants with per-chip data;
ours predates that. The rest of their diff is the v6.13 `iovdd` → `vddio`
rename, an `input_abs_set_res(..., 10)` cosmetic addition, and the
`asm/unaligned.h` fixup we already apply in `nix/kernel.nix`.

Adding `"goodix,gt9895"` to the of_match table would be tidier than relying
on our `"goodix,gt9916"` fallback compatible, but it changes no behaviour and
costs a ~20 minute kernel cross-compile. Not worth coupling to this fix.

Two smaller things deliberately left alone:

- **Regulators.** Ours get dummies (`supply avdd not found`), theirs point at
  a `reg_disp_3v3` fixed regulator on DIS_EN/IO35. The panel works, so the
  rail is on in hardware, and `regulator_enable()` on a dummy succeeds.
  Modelling the rail is correctness housekeeping, not a touch fix. Note the
  property name for our backport is `iovdd-supply`, not `vddio-supply`.
- **Reset polarity and timing.** `GPIO_ACTIVE_LOW` on line 24 matches
  caveman99 exactly, and `goodix_berlin_power_on()` already does the vendor's
  3 ms / 15 ms / 4 ms / 100 ms sequence (`goodix_berlin_core.c:247-289`). The
  controller answers i2c, which it could not do held in reset.

## 6. LILYGO's 31-patch Linux series: checked, nothing on touch

`docs/research/linux-on-t-display-k230.md` §2 enumerates the
`Xinyuan-LilyGO/T-Display-K230` patch queue (0025–0064). It is entirely DRM,
DSI, panel and DTS work. The only touch content is in `0031`, which declares
the node with `compatible = "goodix,nottingham"` — Goodix's marketing name
for the GT9895, matching a *different* out-of-tree driver that is not in our
tree. No touch driver patch, no IRQ-trigger patch, nothing to harvest.

## 7. The change

`nix/dts/k230-tdisplay.dts`, `touchscreen@5d`:

```diff
-		interrupts = <23 IRQ_TYPE_EDGE_FALLING>;
+		interrupts = <23 IRQ_TYPE_LEVEL_LOW>;
+		touchscreen-size-x = <1024>;
+		touchscreen-size-y = <2400>;
```

Verified by reproducing `nix/device-tree.nix`'s exact `cpp` + `dtc`
invocation by hand against the pinned tree
(`/nix/store/pn7bm6ck5a3x6pnk1ng30hlf24qn85jx-source`): it compiles, it
round-trips through `dtc -I dtb -O dts`, and decompiling both the old and new
DTBs shows the diff is these three properties and **nothing else**:

```
-				interrupts = <0x17 0x02>;
+				interrupts = <0x17 0x08>;
+				touchscreen-size-x = <0x400>;
+				touchscreen-size-y = <0x960>;
```

`0x17` = 23, `0x08` = `IRQ_TYPE_LEVEL_LOW`, `0x400` = 1024, `0x960` = 2400.

**UNBUILT and UNTESTED on hardware.** No `nix build` was run (a concurrent
kernel build owns that), and the board was not touched. Only the DTB was
compiled, standalone.

## 8. What would confirm or refute it, in one boot

1. `/proc/interrupts` must read `gpio-k230 23 Level goodix-berlin`. If it
   still says `Edge`, the DTB did not get deployed and nothing below means
   anything.
2. The count must climb while a finger is on the glass and stop when it is
   lifted. That alone settles the trigger question, before any input layer.
3. `evtest /dev/input/event0` must show `ABS_MT_TRACKING_ID`,
   `ABS_MT_POSITION_X/Y` and `BTN_TOUCH`, with X in 0–1023 and Y in 0–2399.

If (1) is `Level` and (2) still does not climb, the trigger type was not the
cause and the next suspect is the interrupt actually being a request-event
loop — instrument `goodix_berlin_irq()` to log `hdr.status` and
`cd->touch_data_addr` and compare the latter against 0x10308.

## Confidence

**High that touch will report; the coordinate range is near-certain.** The
IRQ fix is not reasoned from a datasheet, it is copied from a working system
with the same silicon, the same board, the same kernel version and the same
driver, whose author published the `/proc/interrupts` line that differs from
ours in exactly the one word the change alters.

The residual risk is that something else is *also* broken and the trigger
type was only the first of two faults. Nothing found suggests a second one:
the part answers i2c, the pad is muxed (4 real edges prove it), the IC-info
parse is arithmetically sound, the register layout is confirmed byte-for-byte
against LILYGO's own driver, and that driver performs no initialisation the
backport is missing.
