# U-Boot cyclic callbacks for the stage-1 animation

Research of 2026-10-30 over the source this repo builds (`.#uboot-k230`: U-Boot
2022.10 plus Canaan's overlay plus patches 0001-0005, reconstructed from the
fetched tarball and the pinned SDK commit) and over earlier board captures.
Source reading and a host/cross compile only. **Nothing here was measured on
the board; every timing figure marked "estimate" is UNVERIFIED** until the
board is back and a run is captured.

## Does the tree have the cyclic framework?

No. `common/cyclic.c`, `include/cyclic.h`, `CONFIG_CYCLIC` and `schedule()` do
not exist in 2022.10 (upstream added them for v2023.01). The only related
symbol is `CONFIG_CMD_MX_CYCLIC`, an unrelated memory test. There is no
`schedule()` anywhere in the tree.

What 2022.10 does have is `WATCHDOG_RESET()` (`include/watchdog.h`). With
neither `CONFIG_WATCHDOG` nor `CONFIG_HW_WATCHDOG` (the k230 defconfig sets
neither) it expands to `{}`. That macro is exactly the call site upstream
later turned into `schedule()`.

## Backport size

Small, because the port only needs the API shape:

| Piece | Where | Size |
| --- | --- | --- |
| `cyclic_register/unregister/run`, `schedule()` | `nix/uboot-k230-life/cyclic.h`, `k230_cyclic.c` | about 90 lines |
| route `WATCHDOG_RESET()` to `schedule()` when `CONFIG_K230_BOOT_LIFE_CYCLIC` and not SPL | hunk to `include/watchdog.h` in `0006-k230-stage1-boot-life.patch` | 8 lines |
| frame driver | `src/boot_frame.c` (`bf_begin`/`bf_advance`), `nix/uboot-k230-life/k230_boot_life.c` | existing code, restructured |

Names and signatures follow upstream (`cyclic_register(c, func, delay_us,
name)`, `cyclic_unregister(c)`, `schedule()`), so moving the vendor tree to
2023.01 or later means deleting `cyclic.h`/`k230_cyclic.c` and the watchdog.h
hunk and enabling `CONFIG_CYCLIC`. Differences from upstream are listed in the
header: no hlist, no `gd` field, no `cyclic` command, a run-level re-entrancy
guard, deadlines in timer ticks.

Honest scope of "backport": a full port of upstream's `common/cyclic.c` with
its `gd->cyclic_list`, `cyclic_init()` in the `init_sequence_r`, the `cyclic`
shell command and the many tree-wide `WATCHDOG_RESET`-to-`schedule` edits
would be a few hundred lines across 8 to 10 files and would touch
`global_data.h`; none of that is needed to run one callback, so it was not done.

## Where `schedule()` actually runs on the K230 boot path

By source reading (this tree, K230 defconfig; no board measurement):

* **`udelay()` (`lib/time.c`)** calls `WATCHDOG_RESET()` once per call (and per
  `CONFIG_WD_PERIOD` chunk). The K230 uses this generic `udelay`
  (no arch override; only x86's `tsc_timer.c` defines `__udelay`). This is the
  main hook.
* **SD/eMMC reads.** The board's MMC is `snps_sdhci` on the generic
  `drivers/mmc/sdhci.c`. `sdhci_transfer_data()` polls with `udelay(10)` per
  iteration (up to 10^6 iterations), so a hooked `udelay` calls `schedule()`
  roughly every 10 microseconds for the whole of every `ext4load`. The
  command-phase loop uses `get_timer()` without `udelay` and `sdhci_reset`
  and clock setup use `udelay(1000)`.
  `drivers/mmc/mmc.c`, `fs/ext4` and `cmd/ext4.c` contain no `WATCHDOG_RESET`
  of their own.
* **Autoboot countdown.** `common/autoboot.c` spins with `tstc()` and
  `udelay`, so the one-second `bootdelay` also calls it.
* **bootm legacy-image checks.** The data CRC check (`Verifying Checksum`) uses
  `crc32_wd`, but in `lib/crc32.c` the `WATCHDOG_RESET()` inside it is only
  compiled `#if defined(CONFIG_HW_WATCHDOG) || defined(CONFIG_WATCHDOG)`, so it
  is NOT a call site in this configuration. A 27 MB CRC at software speed is
  an uncovered gap of well under a second (estimate).
* **Decompression.** None on this path: the boot files are an uncompressed
  Linux image and an uncompressed ramdisk uImage
  (`Image Type: ... (uncompressed)` in
  `docs/evidence/mainline-boot-splash/board/idle-kernel-serial-excerpt.txt`).
  The LZMA, zlib and gunzip loops that do call `WATCHDOG_RESET` are not used.
  The ramdisk "Loading Ramdisk to ..." step is a `memmove` with no hook.
* **Console prompt.** An idle `K230#` prompt calls `tstc()` without `udelay`;
  the animation pauses there (acceptable: its frame budget also caps it).

## The boot window and realistic frame rate

From the captured warm-boot log (`idle-kernel-serial-excerpt.txt`, a hold run,
so inter-command gaps are the driver's, but each read time is U-Boot's own):
`logo.xrgb` 118 ms; `Image` 42 745 856 bytes in 1 773 ms (23 MiB/s);
`initrd.uimg` 27 330 502 bytes in 1 136 ms (22.9 MiB/s); `dtb` 6 ms; firmware
17 ms. So the SD reads alone are about **3.1 s** of `udelay`-driven polling,
preceded by the one-second `bootdelay` (also `udelay`-driven) and followed by
the checksum and relocation phase (uncovered, short).

Because the hook fires about every 10 microseconds, the callback rate is bounded
by the period requested and by callback cost, not by hook frequency. Callback
cost (estimate, not measured): one Life generation is about 44 000 cells x 9
bit reads, a few milliseconds to low tens of milliseconds on the C908, plus a
differential redraw and a flush of the changed pixel rows only (`dirty_off`/
`dirty_len`, `src/boot_frame.h`). A period of 80 ms (about 12 frames per
second) therefore costs somewhere under 25 percent of the CPU during loads;
at roughly 4 s of window that is on the order of 40 to 50 frames, to be
confirmed. The build prints `mean` and `max` callback microseconds at bootm so
the first board run measures this directly.

## Cost against boot time, watchdog and timer constraints

* **No sleep is added.** The blocking loop adds `frames x frame_ms` (2 s for 40
  frames at 50 ms) plus compute. The cyclic loop adds only the callback CPU time
  that overlaps with waiting. SDHCI transfers continue under the controller's
  own flow control while the CPU is in the callback; SDMA mode stalls at
  its 512 KiB boundary until the CPU rewrites the address, so a slow callback
  at that moment delays the read by up to one callback duration. The
  command-phase timeout (`SDHCI_READ_STATUS_TIMEOUT`, 1 s) and the data poll
  budget (10^6 x 10 us) are far larger than any callback.
* **Watchdog.** None is enabled in this configuration (the macro was empty), so
  routing it to `schedule()` replaces no watchdog kick. If a watchdog were
  enabled later, `schedule()` would have to call it too (upstream's does).
* **Timer.** Deadlines use `get_ticks()` (RISC-V timer, the same source
  `udelay` uses); no interrupt is involved. Callbacks run in the context of
  whoever called `udelay`, so they must not sleep or touch MMC. The framework
  refuses to re-enter, so a `udelay` called by the callback is harmless.
* **Per-call overhead** when nothing is due is one tick read and compare, about
  100 000 times a second during loads (estimate: under one percent).
* **SPL** is unaffected: the hook is compiled out under `CONFIG_SPL_BUILD`, and
  the default `.#uboot-k230` output is unchanged.

## What changes in the record and the handoff

* The last frame is no longer "generation N after a fixed 40 frames". It is
  whatever the cyclic hook drew before the kernel handoff. The hook stops from
  `ft_board_setup()` (`k230_boot_life_stop()`), the last U-Boot code that runs
  before the jump, so the record Linux reads is final and its checksum matches
  the frame on the glass. Each publish is complete before the next frame
  starts; a callback cannot be interrupted mid-record.
* Generation count at handoff therefore varies with load speed. Linux must not
  assume a number; it already continues from whatever generation the record
  carries (`life_load()`).
* If the user stops at the `K230#` prompt, drawing pauses there (no `udelay`
  call), the record stays valid, and `k230_life stop` freezes it explicitly.
* The ownership pause after U-Boot is unchanged by this decision: the panel
  holds the last cyclic frame from `ft_board_setup` until the Linux owner takes
  the scanout.

## Fallback

`CONFIG_K230_BOOT_LIFE_CYCLIC=n` builds the blocking driver only. With it on,
`k230_life block` runs the blocking loop by hand, and if the cyclic session
cannot start (window outside the reservation, bad configuration) the glue
falls back to the blocking loop and says so.

## For the text-effects producer

Any `bf_source` (src/boot_frame.h) runs under this hook unchanged: draw into the
target in `start()`/`step()`, report the changed byte range in
`dirty_off`/`dirty_len`, publish a record with the common prefix. The callback
budget is the constraint: a step that costs more than a few tens of milliseconds
holds up the SD reads at SDMA boundaries. Do all heavy work (layout, rasterising
glyphs) in `start()`, before the first frame, and keep `step()` incremental.

## Evidence still needed (board offline at the time of writing)

Serial capture of `k230_life` and of a normal boot with `boot_life=1` showing
the `cyclic stopped at generation N after M callbacks, mean X us, max Y us`
line; boot time with and without the animation measured from the serial
timestamps; and a camera or operator view of the frames. None exists.
