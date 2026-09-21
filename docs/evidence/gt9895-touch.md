# GT9895 touch: the backport plan was wrong

Change 3's spec says the GT9895 "is in mainline since approximately 6.7,
so this is a backport, not new work". Both halves of that are wrong.

## What mainline actually has

`goodix_berlin` landed in **v6.9**, not 6.7 — `goodix_berlin_core.c` is
404 at v6.7 and v6.8, 200 at v6.9.

More importantly, **mainline has never supported the GT9895**. As of
**v6.18**:

```c
static const struct of_device_id goodix_berlin_i2c_of_match[] = {
	{ .compatible = "goodix,gt9916", .data = &gt9916_data },
	{ }
};
```

and the binding `goodix,gt9916.yaml` enumerates exactly two parts:

```yaml
    enum:
      - goodix,gt9897
      - goodix,gt9916
```

So `compatible = "goodix,gt9895"` — which `nix/dts/k230-tdisplay.dts`
currently uses — matches nothing upstream, at any version. Backporting the
driver as written would not make this panel's touch work.

## What we do have

LilyGO ships a GT9895 driver for RT-Smart:

    repo/canmv_k230/src/rtsmart/rtsmart/kernel/bsp/maix3/drivers/extdrv/touch/gt9895.c

It is not a Linux driver, but it is a working register-level description of
this exact part on this exact board, which is the strongest kind of source
this project recognises.

## Three ways forward, none yet chosen

1. **Try `goodix,gt9916` and see.** The Berlin generation shares a
   programming model, and the GT9895 may be close enough that the existing
   driver drives it. Cheapest to test — a one-word device tree change — and
   costs nothing to find out once the board boots. Try this first.
2. **Teach the mainline driver the GT9895.** Add a `gt9895_data` chip entry
   and a compatible string, informed by the vendor driver. Upstreamable if
   it works.
3. **Port the vendor driver.** Most faithful to what is known to work on
   this hardware, least likely to be accepted upstream, most work.

Option 1 is not a guess to be recorded as a plan — it is an experiment
whose result is cheap to obtain and which decides between 2 and 3.

## Consequence for the device tree

`nix/dts/k230-tdisplay.dts` keeps `goodix,gt9895` for now, deliberately:
it is what the hardware is, the node is inert without a matching driver,
and an inert node is more honest than a compatible string chosen to make
something bind. The panel is unaffected either way.

UNVERIFIED throughout: no touch controller has been probed under Linux on
this board.

## The backported driver has no per-chip table, which changes task 4.1b

Established by reading `nix/patches/goodix-berlin/`, without hardware.

`goodix_berlin_core.c` contains **no chip data structure and no match data**.
There is no `goodix_berlin_chip_data`, and no call to
`of_device_get_match_data()`, `device_get_match_data()` or
`i2c_get_match_data()` anywhere in the three files. The only chip-specific
thing in the whole driver is the match string itself:

```c
static const struct of_device_id goodix_berlin_i2c_of_match[] = {
	{ .compatible = "goodix,gt9916", },
	{ }
};
```

Everything else is discovered from the part at runtime.
`goodix_berlin_get_ic_info()` reads a blob from `GOODIX_BERLIN_IC_INFO_ADDR`
(`0x10070`) and takes `touch_data_addr`, `cmd_addr`, `fw_state_addr` and the
rest out of it; `goodix_berlin_read_version()` reads and checksums a firmware
version struct.

**Consequence.** Task 4.1b is written as "either add a `gt9895_data` chip entry
to the backported driver or port LilyGO's RT-Smart `gt9895.c`". The first
branch does not exist — there are no chip entries to add one to. The real
choice is:

1. **The GT9895 is a Berlin-family part.** Then the runtime IC-info read
   succeeds, every address is learned from the chip, and the
   `"goodix,gt9895", "goodix,gt9916"` fallback added to the device tree is
   sufficient on its own. **No driver patch at all.**
2. **It is not.** Then nothing in a chip table would have rescued it, and the
   remaining option is the second branch already named: port LilyGO's
   RT-Smart `gt9895.c`.

Which one holds is decided by two specific log lines, so the next boot should
be read for them rather than for "did touch work":

- `goodix_berlin_read_version()` failing its checksum, or
- `goodix_berlin_get_ic_info()` failing the read at `0x10070`

Either means case 2. A clean probe means case 1 and the work is already done.
Task 4.1b's first branch should be restated accordingly.
