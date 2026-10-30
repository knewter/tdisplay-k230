# Proposed install and recovery procedure for the Game of Life U-Boot

**Status: PROPOSAL ONLY. Nothing here has been run. No boot firmware has been
written to any board by this change.** It waits for the coordinator. It reuses
the procedure the 2026-10-20 DMA-request trial already performed and recorded
(`docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/`:
`backup-preflight.json`, `deploy-candidate.py`, `deployment.json`).

## What would be written

One artifact: `fn_ug_u-boot.bin` from `.#stage1-boot-life`
(`packagingOf` over `.#uboot-k230-boot-life`; build recorded in
`docs/evidence/game-of-life/uboot-build.txt`). It replaces only the
U-Boot-proper slot: 1 MiB at byte offset 2 097 152 (2 MiB) of `/dev/mmcblk1`,
the same slot the DMA trial wrote (candidate then 385 932 bytes; the slot
limit is 1 048 576 and the writer asserts it). SPL (both copies), the
environment at 3 MiB / 3.5 MiB, the partition table and every `/boot` file are
not touched. The candidate is compiled with `CONFIG_K230_BOOT_LIFE=y` but the
animation is dormant unless the U-Boot environment variable `boot_life` is
`1` (it is not set in `firmware/stage1/tdisplay.env`), so a first install boots
exactly like today's U-Boot. The only difference at boot is the extra
`k230_life` console command.

## Preconditions

1. The coordinator names an operator and a reservation of the one board and its
   serial port (`flock /tmp/k230-board.lock`), and the charger is online.
2. The running system and boot ID are recorded; the board is at its normal
   daily default.
3. Fresh backup of the first 4 MiB of `/dev/mmcblk1` taken on the board
   (`dd ... iflag=direct`), copied to the host, SHA-256 equal on both sides, kept
   outside Git (the region holds the saved U-Boot environment, which may carry
   Wi-Fi credentials). The 2026-10-20 backup is of the pre-DMA-fix U-Boot and is
   **not** the current rollback image; a new one is required.
4. Host check: `python3 tools/check-boot-life-memory.py` reports OK against the
   DTB the board boots; the candidate's `fn_ug_u-boot.bin` K230 header, length
   and SHA-256 are verified by the writer exactly as `deploy-candidate.py` does.

## Install (once only, guarded)

Adapt `deploy-candidate.py`: the remote step refuses unless the boot ID,
`/run/current-system`, partition start (8192 sectors) and every `/boot` file hash
match the preflight, the direct 4 MiB read equals the backup, and the payload
is a valid K230 firmware image with length below the slot. It writes the
payload at offset 2 097 152, fsyncs, re-reads 4 MiB with `iflag=direct`, and
**restores the original slot automatically if the readback differs from
backup-with-payload-spliced-in**. Recorded in a `deployment.json`.

## First boot and first use

1. Warm reboot with the serial console attached
   (`flock /tmp/k230-board.lock python3 tools/console.py`, then the quirks in
   the `k230-uboot-console-quirks` note: drain until 0.5 s of quiet after each
   command). Expect the normal splash, the normal Linux boot, and the same
   `/chosen/canaan,stage1-splash` flag. The new U-Boot must show no
   `boot life:` line, because `boot_life` is unset.
2. Interrupt autoboot (bootdelay is 1 s; hammer the console as in the
   `board-access-and-usb-flashing` note), then run `k230_life` once at
   `K230#`. Expect `boot life: 40 generations, instance 0x..., grid hash 0x...`.
   Capture the serial transcript. Run `boot`. After Linux is up, read the
   chosen property and the record's `ownership pause` journal line.
3. Only after step 2 works on glass, and only on the coordinator's say-so,
   consider `setenv boot_life 1` for one boot (not `saveenv`), then a later
   decision about saving it. Writing the environment is a separate approval.

Each step keeps the board recoverable by reset, because the animation never
runs unless asked.

## Recovery

* **U-Boot boots Linux but misbehaves** (for example the new `k230_life`
  command hangs): reset; the default boots without running it. To remove the
  candidate, restore the 1 MiB slot from the verified backup with the recorded
  slot-only command:
  `dd if=<backup>.bin of=/dev/mmcblk1 bs=512 skip=4096 seek=4096 count=2048 conv=notrunc,fsync`
  and verify the whole first 4 MiB hash equals the backup (this is the command
  `backup-preflight.json` recorded for the DMA trial; the slot offset and size
  are identical).
* **U-Boot does not start** (dark panel, no console after a reset, the case the
  write guards are meant to make unlikely): the card is no longer a working
  boot device. Recover by one of, in order of preference:
  1. U-Boot is not needed to reflash the slot if the card is mounted elsewhere:
     power off, remove the TF card, write the same slot from the verified
     backup on the host with `dd ... seek=4096 count=2048 conv=notrunc` against
     the card reader, verify, reinsert. Needs a person at the board.
  2. BootROM USB recovery per `docs/uboot-ums.md` section 5 (hold `SW3` while
     applying power via J3, drive `k230_flash`). **Not yet proven on this
     hardware** (the document states the path "should" work); it is the second
     choice for that reason.
  The CH342 cold-boot limit (`board-access-and-usb-flashing`) means the first
  seconds of a cold boot cannot be captured on serial; use a warm reboot to
  observe the new U-Boot.
* The vendor-card board (`flashing-a-vendor-card-board` note) is not a target:
  its U-Boot has no `ums` and its card must not be written through the gadget.

## Evidence that would close the board-side tasks

Serial transcripts of `k230_life`, the property in `/proc/device-tree/chosen`,
the early-Linux journal lines, and the owner's takeover of the same boot's
grid; a camera/operator observation of the stage-1 frames and the pause (task
2.3, camera not usable in this session, so an operator video: boot with the
camera running, `tools/capture-boot-camera` or the operator's own phone, then
the transcript). None of this is claimed here.
