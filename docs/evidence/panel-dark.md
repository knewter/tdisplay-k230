# The panel probes, sets a mode, and stays dark

Observed 2026-09-20, after `the-screen-comes-up-under-linux` task 2.3 passed.
Everything up to the glass works; nothing appears on it.

## What works

- `canaan-mipi-dsi 90850000.dsi: Attached device universal`
- `canaan-drm` binds `vo` and `dsi`, `/dev/dri/card0` exists
- `modetest` reports `DSI-1 connected`, 44x95 mm, `568x1232 @ 39.63` preferred
- A modeset **succeeds** and the CRTC scans out: `drm_handle_vblank` fires
  repeatedly and `canaan_crtc_atomic_flush` runs

## What does not happen

During a successful `modetest -M canaan-drm -s 48:568x1232@AR24`, with
`drm.debug` at `0x1f`, 171 debug lines are produced and **not one** matches
`panel`, `prepare`, `dcs`, `atomic_enable` or `bridge_enable`. The commit
reads:

```
drm_atomic_helper_check_modeset] [CONNECTOR:48:DSI-1] keeps [ENCODER:47:DSI-47], now on [CRTC:46:canaan_crtc]
drm_atomic_commit] committing ...
canaan_crtc_atomic_flush] Flush the configuration
drm_handle_vblank] vblank event on 1021, current 1021
```

`keeps` and a bare `flush`, with vblank already counting past 1000: the CRTC
was **already active**, so this is not a full enable. `atomic_enable` is the
only path that reaches the panel —

```c
/* drivers/gpu/drm/canaan/canaan_dsi.c */
412:  drm_panel_prepare(dsi->panel);
427:  drm_panel_enable(dsi->panel);
```

— and `canaan_panel_prepare()` is what sends the init sequence:

```c
if (p->init_set_v1_flag)
    panel_simple_xfer_dsi_cmd_seq(p, p->init_seq_v1);
```

So the DSI link is running video into a panel that was never sent its
initialisation DCS commands, including sleep-out (0x11) and display-on
(0x29). A dark screen with a perfectly healthy modeset is exactly that.

## Ruled out

- **Reset polarity.** `dsi_reset` (GPIO22) reads `out hi`, which looks like a
  panel held in reset, but that is the driver's intended final state:
  `canaan_panel_dsi_probe()` drives it high, low, then high again, and every
  vendor board declares `GPIO_ACTIVE_HIGH` exactly as we do.
- **Backlight GPIO.** `gpio-537 (backlight_gpio) out hi`.
- **Wrong property name.** `panel-init-sequence` is what the driver reads
  (`panel-canaan-universal.c:286`) and it is present in our DTB with all 297
  bytes, ending `05 01 01 11` (sleep out) and `05 01 01 29` (display on).
- **A missing init sequence.** It parses; `init_set_v1_flag` is set on the
  same path.

## Why nothing ever did a full enable

At boot, DRM's generic fbdev emulation is what normally performs the first
modeset. On this board it **fails**:

```
[drm] bpp/depth value of 32/24 not supported
[drm] No compatible format found
[drm] *ERROR* fbdev: Failed to setup generic emulation (ret=-22)
```

`canaan_drv.c:272` asks for 32 bpp (`XRGB8888`); the driver's RGB planes
advertise `AR24 AR12 AR15 RG24 RG16 BG24` and not `XR24`. So no framebuffer
is created, no initial modeset happens, and by the time `modetest` runs the
CRTC is in a state where the helpers see nothing to enable.

**Hypothesis, not yet confirmed:** patching that call to 16 bpp (`RGB565`,
which those planes do advertise) restores the boot-time modeset, which calls
`drm_panel_prepare()`, which sends the init sequence — lighting the panel and
putting the console on it in one go. The patch is in `nix/kernel.nix`; the
image built from it has not been flashed yet.

If that turns out not to light the panel, the next step is a `dev_info` in
`canaan_panel_prepare()` to confirm whether it is reached at all, rather than
more inference from the absence of log lines.

## Update: two more hypotheses killed, and a real trace at last

### The soft lockup was never the panel

Later boots gained `/dev/fb0` (the 16 bpp fbdev fix below) and then hung: a
kworker soft-locking ~30s in, right as udev began coldplugging. Three
explanations were tried and each is disproved on hardware:

| Hypothesis | Disproved by |
| --- | --- |
| The DSI write spins forever | `CMD_PKT_STATUS_TIMEOUT_US` is 20 ms and `panel_simple_sleep()` uses `msleep`/`usleep_range`. That path cannot hold a CPU for 22 s. |
| fbcon's console take-over holds `console_lock` | Hung identically with `CONFIG_FRAMEBUFFER_CONSOLE=n`. |
| `canaan_get_temp()`'s unbounded `while (1)` | Hung identically with the loop capped and sleeping. |

The reason each took a boot to rule out is that **the kernel could not print
a backtrace**. `k230_defconfig` sets `CONFIG_SOFTLOCKUP_DETECTOR=y` and no
`FRAME_POINTER`; on RISC-V the default unwinder walks frame pointers, so
every lockup printed its header followed by an empty stack dump. The
evidence needed to settle it in one boot was configured out.

### With FRAME_POINTER on, the board tells us exactly what it is doing

Enabling `FRAME_POINTER` and `STACKTRACE` immediately produced a real trace
— of a *different* fault, one introduced by adding `KALLSYMS_ALL` in the
same change:

```
status: 0000000200000100 badaddr: 000000000000000c cause: 000000000000000d
[<...>] do_raw_spin_lock+0x10/0x134
[<...>] _raw_spin_lock_irqsave+0x2a/0x36
[<...>] complete+0x26/0x82
[<...>] module_kobj_release+0x1a/0x22
[<...>] kobject_put+0xa0/0x1fe
[<...>] locate_module_kobject+0xd8/0x10c
[<...>] param_sysfs_builtin_init+0x54/0x1d8
[<...>] do_one_initcall+0x62/0x26a
Kernel panic - not syncing: Attempted to kill init! exitcode=0x0000000b
```

`cause 0xd` is a load page fault, `badaddr 0xc` a near-NULL pointer. This is
the known 6.6-era bug in which `locate_module_kobject()` fails, `kobject_put()`
then invokes `module_kobj_release()`, and that calls `complete()` on the
`kobj_completion` of a synthetic builtin-module object, which is NULL.

`KALLSYMS_ALL` only adds data symbols and is not needed for backtraces, so it
is dropped; `FRAME_POINTER` alone is what makes `dump_stack()` work.

### Boot-chain facts established while bisecting

Driven by hand from the U-Boot prompt, with the serial port already settled:

```
ext4load mmc 1:1 0x8000000 /fw_jump_add_uboot_head.bin   270792 bytes read
ext4load mmc 1:1 0x200000  /Image                      62445056 bytes read in 2189 ms
echo STILL_ALIVE                                        STILL_ALIVE
```

So the 62 MB kernel load is clean and U-Boot survives it. An earlier theory
that the kernel had outgrown its load region and was overwriting U-Boot is
**wrong**.

Two artifacts of the harness, not the board, also became clear and are worth
recording because both were mistaken for hardware faults:

- **The CH342 emits a burst of garbage when the port opens.** Readable text
  resumes immediately after. Some of what earlier logs show as mid-boot
  "corruption" is USB re-enumeration noise.
- **A single keypress cannot stop U-Boot autoboot.** The port opens before
  the countdown starts, so the key is consumed too early. `tools/capture-boot.py`
  gained `--hammer`, which sends a key every 100 ms through the window.
