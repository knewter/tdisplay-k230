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
