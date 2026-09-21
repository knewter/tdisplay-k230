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
