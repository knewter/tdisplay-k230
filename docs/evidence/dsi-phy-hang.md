# The hang and the dark panel are one bug: the DSI PHY never reports ready

Root cause, established on hardware 2026-09-21 after four wrong hypotheses.

## The trace

Captured by appending `softlockup_panic=1` to the kernel command line at the
U-Boot prompt. That was necessary: the ordinary soft-lockup path on this
single-hart board prints its header and then **nothing** — no modules, no
registers, no trace — because the watchdog interrupt preempts the stuck task
on the only CPU and then blocks on something that task holds. The panic path
prints fine.

```
watchdog: BUG: soft lockup - CPU#0 stuck for 26s! [kworker/0:5:44]
Modules linked in:
CPU: 0 PID: 44 Comm: kworker/0:5 Tainted: G    B    6.6.36 #1-NixOS
Hardware name: LILYGO T-Display-K230 (DT)
Workqueue: events output_poll_execute
epc : k230_dsi_config_4lan_phy+0x562/0x620
 a4 : 0000000000001fbd
status: 0000000200000120 badaddr: 0000000000000000 cause: 8000000000000005

[<..>] k230_dsi_config_4lan_phy+0x562/0x620
[<..>] canaan_dsi_encoder_enable+0x216/0x532
[<..>] drm_atomic_helper_commit_modeset_enables+0x194/0x1b4
[<..>] drm_atomic_helper_commit_tail_rpm+0x54/0xa2
[<..>] commit_tail+0x86/0x160
[<..>] drm_atomic_helper_commit+0x13c/0x170
[<..>] drm_atomic_commit+0x86/0xb6
[<..>] drm_client_modeset_commit_atomic+0x1ec/0x228
[<..>] drm_client_modeset_commit_locked+0x50/0x124
[<..>] drm_client_modeset_commit+0x2e/0x4e
[<..>] __drm_fb_helper_restore_fbdev_mode_unlocked+0x86/0xc6
[<..>] drm_fb_helper_hotplug_event+0xda/0xe8
```

`cause 0x8000000000000005` has bit 63 set: a supervisor **timer interrupt**,
i.e. the watchdog firing while the CPU spins. Not a fault. `badaddr` is 0
because nothing faulted.

## The code

`drivers/gpu/drm/canaan/canaan_phy.c`, twice:

```c
	while (readl(dsi->base + PHY_STATUS) != 0x1fbd)
		;
```

Bare infinite loops, body a single semicolon. No timeout, no iteration cap,
no sleep. `a4` in the register dump holds `0x1fbd`, the value being waited
for. The D-PHY on this board never reports it.

The vendor **did** bound the `PHY_TST_CTRL1` loop immediately above these
with `count >= 1000; break`, so the omission looks accidental rather than
deliberate.

## Why this is also the dark panel

`canaan_dsi_encoder_enable()` never returns, so the modeset never completes
and `drm_panel_prepare()` is never called — which is what would have written
the RM69A10 DCS init sequence, including sleep-out (0x11) and display-on
(0x29). The `dev_info` added at the top of `canaan_panel_prepare()` never
printed on any boot, and now we know why: execution never gets there.

This retires the earlier reading in `panel-dark.md` that the panel was being
skipped. It is not skipped; the pipeline stalls one stage earlier.

## Why it only appeared once fb0 existed

The bottom of the trace is `drm_fb_helper_hotplug_event`. The fbdev helper
performs the modeset. Before the 16 bpp fix, fbdev emulation failed
(`XR24` not advertised by the planes), no framebuffer was created, nothing
ever drove a full modeset, and so nothing hung — the panel was simply dark.
Fixing fbdev did not cause the bug; it exposed one that was always there.

## Prime suspect for *why* the PHY never reports ready

`canaan_dsi.c:383` calls `k230_dsi_config_4lan_phy()` **unconditionally**,
and only afterwards sets the real lane count at line 403 via
`canaan_dsi_set_lan_num(dsi, device->lanes)` (which accepts 1, 2 or 4).

This panel is `panel-dsi-lane = <2>`. If `0x1fbd` encodes "all four lanes
ready", the two absent lanes can never assert their bits and the wait can
never succeed. **Unverified** — there is no register documentation in the
tree, and the bit layout of `PHY_STATUS` is unknown.

## What was changed

Both loops are bounded and now report what the PHY actually says:

```c
{ int _w = 0; u32 _s = 0;
  while ((_s = readl(dsi->base + PHY_STATUS)) != 0x1fbd && _w++ < 2000)
          usleep_range(100, 200);
  if (_s != 0x1fbd)
          dev_err(dsi->dev, "PHY_STATUS 0x%x != 0x1fbd after %d tries, continuing\n", _s, _w); }
```

This is deliberately a diagnostic, not a fix. It converts an unkillable hang
into a logged value. The observed `PHY_STATUS` is the evidence needed to
decide the real fix — whether the expected value should depend on lane
count, and if so what it should be for two lanes.

## Four hypotheses this replaces

| Hypothesis | How it was disproved |
| --- | --- |
| The DSI **write** spins forever | `CMD_PKT_STATUS_TIMEOUT_US` is 20 ms and `panel_simple_sleep()` sleeps. Wrong function: the spin is in PHY **config**, not packet write. |
| fbcon's console take-over holds `console_lock` | Hung identically with `CONFIG_FRAMEBUFFER_CONSOLE=n`. |
| `canaan_get_temp()`'s unbounded `while (1)` | Hung identically with that loop bounded. (Still a real latent bug; the bound stays.) |
| The 62 MB kernel overran its load region | Loaded by hand from U-Boot: `62445056 bytes read`, then `STILL_ALIVE`. |

Every one of those cost a build and a flash, because the kernel could not
print a backtrace: `k230_defconfig` sets `CONFIG_SOFTLOCKUP_DETECTOR=y` with
no `FRAME_POINTER`, so `dump_stack()` emitted nothing. The lesson is to fix
the instrument before forming the fifth theory, not the first.

## Resolved: the display power domain was the cause

Pinning `K230_PM_DOMAIN_DISP` at probe — `pm_runtime_get_sync()` in
`canaan_drm_probe()` rather than only in `canaan_drm_open()` — fixed the
whole SoC-side chain. On the next boot, every symptom above is gone:

```
[ 3.055734] canaan-mipi-dsi 90850000.dsi: Attached device universal
[ 3.136970] [drm] Initialized canaan-drm 1.0.0 20230501
[ 3.162288] [drm] fb0: canaan-drmdrmfb frame buffer device
[ 3.179270] [drm:canaan_drm_bind] Canaan K230 DRM driver register successfully
[ 3.299730] canaan-panel-dsi 90850000.dsi.0: canaan_panel_prepare: entered, init_set_v1_flag=1
```

- **No `PHY_STATUS 0xffffffff`.** The PHY now reaches `0x1fbd`, so the
  bounded wait succeeds instead of timing out 2001 times.
- **No `failed to write dcs cmd: -110`.** All 20 init commands are written.
- **`canaan_panel_prepare: entered` appears for the first time on any boot.**
- No soft lockup; the board boots to a login prompt.

This also retires the guess that `0x1fbd` was a four-lane encoding an
unreachable for a two-lane panel. It was reachable all along; the block was
simply unpowered.

## The panel is still dark, and it is now a panel-side problem

State read off the running board:

```
crtc[46]: canaan_crtc
	enable=1
	active=1
plane[33]: plane-1  crtc=canaan_crtc  crtc-pos=568x1232+0+0
	format=RG16 little-endian   size=568x1232  pitch[0]=1136
	dma_addr=0x000000001e100000
connector[48]: DSI-1
gpio-534 (dsi_reset)      out hi
gpio-537 (backlight_gpio) out hi
```

`dd if=/dev/urandom of=/dev/fb0` wrote 1400832 bytes — the whole
framebuffer — and a webcam pointed at the board shows no change. Note that
writing a pattern was necessary to test this at all: an all-zero
framebuffer on a working panel is indistinguishable from a dark one.

So every stage the SoC controls is verified good: domain powered, PHY
locked, DCS accepted, CRTC active, plane bound to a real buffer at the
right geometry and format. What remains is between the DSI output and the
glass.

Remaining suspects, in the order worth testing:

1. **The init sequence content.** Transcribed from LilyGO's RT-Smart
   `rm69a10.c` into `panel-init-sequence`. It is *accepted* by the DSI
   controller, which says nothing about whether it is correct for this
   panel. `docs/evidence/rm69a10-init-sequence.md` has the per-command
   provenance.
2. **Panel supply rails.** `canaan_panel_prepare()` has its `power_on`
   assertion commented out by the vendor exactly like the reset pulses
   were; the GPIO reads high, but whether GPIO25 is the AMOLED's VCI/ELVDD
   enable or something else is unverified.
3. **`vth_line`.** Ours is 9, the vendor reference uses 10. Unlikely to
   cause total darkness, but it is a known divergence
   (`docs/evidence/dts-divergence.md`).
4. **DCS read-back is unimplemented.** `canaan_dsi_dcs_read()` is a stub
   returning 1, so the panel's ID registers cannot be read to confirm it is
   responding at all. Implementing it would turn "the panel is silent" into
   a measurement.

### Also ruled out: the framebuffer pixel format

The DSI wire format is set to RGB888 (`dsi->format = MIPI_DSI_FMT_RGB888`,
`panel-canaan-universal.c`), while the fbdev fix made the framebuffer
RGB565. That mismatch looked like a candidate, so it was tested directly
without a rebuild:

```
modetest -M canaan-drm -s 48:568x1232@AR24
```

ARGB8888, held open, no error reported. A webcam frame taken while it was
driving the panel is indistinguishable from the one taken with the RGB565
framebuffer: still dark. The format is not the problem.

### Also ruled out: the panel power GPIO

`canaan_panel_prepare()` has its `power_on` assertion commented out, which
looked like the reset-pulse bug repeating. It is not: probe does
`gpiod_direction_output(ctx->power_on, 1)` unconditionally
(`panel-canaan-universal.c:338`), and `/sys/kernel/debug/gpio` confirms
`gpio-537 (backlight_gpio) out hi` on the running board.

### Where this leaves it

Everything the SoC drives is verified correct, and three panel-side
theories are dead. The two things still untested both point the same way:

- **The init sequence is accepted, not validated.** The DSI controller
  ACKing 20 writes says the bus works, not that the bytes are right for
  this panel.
- **`canaan_dsi_dcs_read()` is a stub** (`// TODO`, returns 1), so the
  panel cannot be asked anything — not its ID, not its power mode, not
  whether it received the sequence.

Implementing DCS read is therefore the highest-value next step. It converts
"the panel is silent" from an inference into a measurement, and would
distinguish a panel that is not responding at all from one that is
responding but not lighting.

### Also ruled out: vth_line

Set to 10, matching every Canaan board dts in the vendor tree, replacing an
ungrounded 9. Boot is clean — `Attached device universal`,
`canaan_panel_prepare: entered, init_set_v1_flag=1`, no PHY error, no DCS
error, reaches a login prompt — and a webcam frame taken with 1400832
bytes of urandom in `/dev/fb0` is still dark. The change is kept because 9
had no source, but it is not the fix.

## Everything cheap is now exhausted

Verified correct, each on hardware or by mechanical comparison:

| | |
| --- | --- |
| Display power domain | on (pinned at probe) |
| DSI PHY | locks, `PHY_STATUS` reaches `0x1fbd` |
| DCS writes | all 20 accepted, no `-110` |
| Init sequence bytes | byte-identical to vendor, 20 cmds / 297 bytes |
| Init sequence delays | ours 1 ms vs vendor 300 us / 100 us |
| Send ordering | LP (`lpdt_init`) before HS (`set_dsi_enable`) |
| Pixel format | dark at both RG16 and AR24 |
| Panel power GPIO | asserted at probe, reads `out hi` |
| Reset pulses | restored in `prepare`, before the sequence |
| CRTC | `enable=1 active=1`, plane bound, real dma_addr |
| `vth_line` | 9 and 10 both dark |
| Clock config | no `MIPI clock not support` |

Every stage that can be observed from the SoC side reports success, and
the panel emits nothing.

## The one instrument still missing

`canaan_dsi_dcs_read()` is a stub:

```c
static int canaan_dsi_dcs_read(struct canaan_dsi *dsi,
			       const struct mipi_dsi_msg *msg)
{
	// TODO
	return 1;
}
```

So the panel cannot be asked anything. Reading DCS `0x04` (RDDID) or `0x0A`
(RDDPM, power mode) would distinguish, for the first time, between:

- the panel is not receiving the sequence at all, and
- the panel is receiving it, acknowledging it, and still not lighting.

Every remaining hypothesis — wrong panel variant, a missing supply the
board provides elsewhere, a DSI timing parameter the controller accepts but
the panel rejects — is untestable without that. Six theories have now died
here, and the pattern is consistent: the ones that died cheaply were the
ones where an instrument existed.

Implementing DCS read is the next step, not another guess.

## The measurement: the panel does not answer

With `canaan_dsi_dcs_read()` implemented and a caller added to
`canaan_panel_prepare()`, the board reports:

```
[3.270] canaan-panel-dsi 90850000.dsi.0: canaan_panel_prepare: entered, init_set_v1_flag=1
[3.489] canaan-panel-dsi 90850000.dsi.0: RDDID (0x04) failed: -22
[3.539] canaan-mipi-dsi  90850000.dsi:   DCS read 0x0a: panel did not answer (status 0x50015)
[3.548] canaan-panel-dsi 90850000.dsi.0: RDDPM (0x0A) failed: -110
```

`0x50015` against the driver's own bits (`canaan_dsi.c:37-42`):

| bit | name | state |
| --- | --- | --- |
| 0 | `GEN_CMD_EMPTY` | set — the read command was sent and drained |
| 2 | `GEN_PLD_W_EMPTY` | set |
| **4** | **`GEN_PLD_R_EMPTY`** | **set — the read payload FIFO is empty** |

The command went out; nothing came back; the wait timed out at `-110`.

### Why this changes the reading of every earlier result

"All 20 DCS writes accepted, no errors" has been treated as evidence the
panel receives the init sequence. **It is not.** A DSI write reports only
that the controller's own FIFO drained — the panel never acknowledges it.
A read is the first operation on this link that requires the panel to
respond, and the panel is silent.

That single fact is consistent with every hypothesis that died here:

- the init sequence is byte-identical to the vendor's — irrelevant if it
  is not arriving
- the delays are longer than the vendor's — same
- LP-before-HS ordering is correct — same
- RG16 vs AR24 made no difference — same
- the CRTC is `active=1` with a bound framebuffer — same

None of them were wrong about what they measured. They were all measuring
the SoC side of a link whose far end is not responding.

### Next suspects, now much narrower

1. **Panel supply.** `backlight_gpio`/`power_on` is asserted, but that is
   one GPIO; an AMOLED needs VCI and ELVDD, and nothing in the device tree
   or driver models them. If the panel is unpowered it cannot answer.
2. **The physical DSI link.** Lane mapping, polarity, or a connector
   issue. The PHY reports lock (`PHY_STATUS == 0x1fbd`) but that is the
   SoC's own PHY, not proof of a working link to the panel.
3. **The part is not an RM69A10** with these addresses.

### A bug of mine in the above

`RDDID (0x04) failed: -22` is EINVAL, not a timeout: the request asked for
3 bytes and `canaan_dsi_transfer()` only routes `MIPI_DSI_DCS_READ` when
`msg->rx_len == 1`, falling through to `default: -EINVAL`. The RDDPM read
used one byte and exercised the new code correctly, so the conclusion
stands, but the RDDID call should either request one byte or the
dispatcher should be widened.

## Leading hypothesis: the PHY is configured for 4 lanes, the panel has 2

Found by reading LilyGO's RT-Smart driver for this exact panel against the
Linux driver.

**RT-Smart sets the PHY to 2 lanes for the RM69A10**, in
`rm69a10_set_phy_freq()`:

```c
mipi_phy_attr.phy_lan_num = K_DSI_2LAN;
connector_set_phy_freq(&mipi_phy_attr);
```

And it is the *only* vendor panel that does. Across
`mpp/kernel/connector/src/`:

| connector | lanes |
| --- | --- |
| `st7701.c` (the reference board's panel) | `K_DSI_4LAN` |
| `ili9806.c` | `K_DSI_4LAN` |
| `lt9611.c` (HDMI bridge) | `K_DSI_4LAN` |
| **`rm69a10.c` — this panel** | **`K_DSI_2LAN`** |

**The Linux driver has no 2-lane path at all.** `canaan_phy.c` exports
exactly one PHY configuration function, `k230_dsi_config_4lan_phy()`, and
`canaan_dsi.c:383` calls it unconditionally:

```c
k230_dsi_config_4lan_phy(dsi, m - 2, n - 1, voc, 0x96);
```

`canaan_dsi_set_lan_num(dsi, device->lanes)` at line 403 sets the lane
count in the *DSI controller*, but nothing tells the *D-PHY*. The driver
was evidently developed against the 4-lane panels; ours is the exception.

This fits the measurement better than anything else so far. The SoC's own
PHY reports lock (`PHY_STATUS == 0x1fbd`) because both PHY instances are
configured and happy — but the data is being striped across four lanes
into a panel wired for two. The panel would see malformed traffic,
respond to nothing, and never light. Writes would still "succeed", because
a DSI write only reports the controller's FIFO draining.

It also explains why `0x1fbd` is reachable: it is the all-PHYs-ready value
for the 4-lane configuration the driver always programs.

### Why this is not a quick patch

`k230_dsi_phy0_config()` and `k230_dsi_phy1_config()` interleave writes to
the second PHY instance (`dsi->base + 0x400 + ...`) throughout, and there
is no register documentation in the tree for `TXDPHY_PLL_CFG0/1`,
`TXDPHY_CFG0/1` or the `PHY_STATUS` bit layout. Producing a correct
2-lane configuration means working out which of those writes belong to the
second lane pair and what the ready mask becomes — reverse engineering,
not an edit.

`connector_set_phy_freq()`, which would show the vendor's own mapping from
`phy_lan_num` to registers, is declared in the RT-Smart tree but
implemented outside it, so the delta cannot simply be read off.

### Confirmed against the schematic: the panel is physically 2-lane

`repo/schematic/T-Display K230_V1.0_NEW.pdf`, the LCD FPC connector
(J101x group) carries exactly:

```
DSI_CLK_P / DSI_CLK_N
DSI_D0_P  / DSI_D0_N
DSI_D1_P  / DSI_D1_N
LCD_RST, LCD_VDD
```

`DSI_D2_*` and `DSI_D3_*` appear **only** at the SoC pinout (balls Y7,
Y11 and neighbours) and are never routed to the panel connector.

So `panel-dsi-lane = <2>` is correct and matches both the schematic and
RT-Smart. The defect is that the Linux driver programs the D-PHY for four
lanes regardless.

This also rules out the cheap experiment that suggested itself here
earlier — setting `panel-dsi-lane = <4>` to see if the *2* was ours to
blame. The board says 2. That test would have been a wasted build.

### Suggested work from here

**Implement the 2-lane PHY path**, using `k230_dsi_config_4lan_phy()` as
the template and gating the second-instance writes (`dsi->base + 0x400 +
...`) on lane count. Expect the `0x1fbd` ready mask to need changing too:
it is the all-ready value for a four-lane configuration. The bounded wait
added earlier will print whatever a 2-lane configuration actually
produces, which is exactly the information needed to pick the new mask —
so the first build of this does not have to guess the constant, it can
read it.

Worth noting what makes this tractable now and was not before: the read
path exists, so a 2-lane attempt can be judged by whether the panel
*answers* rather than by whether the screen lights.
