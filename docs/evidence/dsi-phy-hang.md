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
