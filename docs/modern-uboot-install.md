# Installing the modern U-Boot (stage a): procedure and recovery

Status: **written, not performed.** Nothing in this file has been run against
the board's card. It is the review gate for task group 4 of
`openspec/changes/the-board-boots-a-modern-u-boot`; the coordinator approves
it before any step in section 3 or 4 runs. Host builds (section 1) and
read-only checks on the running system (section 2) are done.

## 0. What is written, and what is not

| Card region | Byte offset | Window | Stage a | Notes |
| --- | --- | --- | --- | --- |
| SPL copy 1 | `0x100000` | 512 KiB | **preserved** | vendor-derived SPL, DDR training |
| SPL copy 2 | `0x180000` | 512 KiB | **preserved** | byte-identical to copy 1 on this card |
| U-Boot | `0x200000` | 1 MiB | **written** | `fn_ug_u-boot.bin`, zero-padded to 1 MiB |
| Environment | `0x300000` (second copy `0x320000`) | 8 KiB / 1 MiB | **preserved** | `bootcmd=run blinux`, `bootdelay=1`; read by the modern U-Boot unchanged (same 4-byte CRC32 header, `CONFIG_ENV_SIZE=0x2000`) |
| `/boot` (ext4, p1) | partition 1 | 112 MiB | preserved; gains two files (4.1) | `fw_jump_add_uboot_head.bin` (OpenSBI 1.4) untouched |
| rootfs (p2) | partition 2 | | preserved | |

The 2022.10 slot, both SPL copies and both environment windows were read from
the running board on 2026-10-30 (read-only, over SSH) and saved to
`/mnt/MediaVolume/home/jadams/k230-card-backups/stage1-slots-20261030/`
(outside the repository: the environment holds the Wi-Fi credentials).
`SHA256SUMS` in that directory:

```
2767348bb2f6b599...  uboot-2MiB-1MiB.bin    (the rollback image; K230 magic, 385 931 bytes used)
25521b917baf3c62...  spl-1MiB-512K.bin
25521b917baf3c62...  spl-1.5MiB-512K.bin
4672110a0919024b...  env-3MiB-1MiB.bin      (CRC32 header valid: 0x5f56e8bf)
```

(first 16 hex digits shown; the full hashes are in the file.) The card is a
15.6 GB part; the running U-Boot reports itself as 2022.10 in
`/proc/device-tree/chosen/u-boot,version`.

## 1. Host build products (done on the host; evidence class: host build)

```
nix build --out-link <scratch>/root-stage1-modern .#stage1-modern
nix build --out-link <scratch>/root-trial          .#uboot-k230-modern-trial
```

`stage1-modern/SHA256SUMS` lists the five stage-1 files. `fn_u-boot-spl.bin`,
`env.env` and `fw_jump*` are byte-identical to `.#stage1`'s (the packaging
reuses the vendor-derived SPL and the same environment and OpenSBI);
`fn_ug_u-boot.bin` is the only new file. `tools/write-uboot-slot.sh --check
<fn_ug_u-boot.bin>` verifies the K230 magic and the 1 MiB window before any
write.

## 2. Read-only prerequisites (no write)

On the host: card reader and a known-good copy of the rollback image
(`uboot-2MiB-1MiB.bin` above). On the board: the charger online, SSH up,
console on the CH342 bridge (the console is **not** `/dev/ttyACM0` this week;
the coordinator names the port), and the J3 data USB-C cabled directly to this
host for `ums`.

## 2a. Amendment 2026-10-30 (coordinator): J3 is not cabled to this host

The operator has one USB lead and it is on the console, so **no `ums` proof is
run this session** (a0 step 5 and the stage-a `ums` check are recorded as not
run, with this reason) and recovery path 1 below is unavailable. Consequences:

- The slot is written **from the running Linux over SSH** with
  `K230_SLOT_SSH='ssh -F <cfg> k230' tools/write-uboot-slot.sh <image> ssh:/dev/mmcblk1`
  (same one-window write, `O_DIRECT` read-back and preserved-region hashes;
  board lock held). Nothing else changes in section 4.
- Immediately before the write, take a **fresh backup of exactly what is in the
  slot at that moment** (the Life work may have changed it) to the backup
  directory, and use that file as the rollback image.
- Rollback path 2 (at the new U-Boot prompt: `ext4load` the saved image from
  `/boot`, then `mmc write`) is rehearsed during a0 from the 2022.10 prompt
  **without writing**: load the 1 MiB rollback image to RAM, `mmc read` the
  slot into a second RAM buffer, `cmp.b` them, and require "Total of ... bytes
  were the same". The floor is the card reader, operator present.

## 3. Stage a0: run the modern U-Boot from RAM (no boot-firmware write)

The trial binary is linked at `0x4000000` (`CONFIG_TEXT_BASE`), away from the
running 2022.10 image and from the stale copy at `0x0`.

1. From Linux (SSH, board lock held): copy `u-boot.bin` of
   `.#uboot-k230-modern-trial` to `/boot/u-boot-modern-trial.bin`, copy the
   rollback image to `/boot/fn_ug_u-boot.2022.10.bin`, `sync`. Record
   `sha256sum` of both on the board and the host.
2. `reboot`; interrupt autoboot at the `K230# ` prompt (the 1 s `bootdelay`;
   `tools/ums-session.py`'s key-hammering loop is the pattern). Drain console
   replies until 0.5 s of quiet after every command (memory note
   `k230-uboot-console-quirks`: every reply is echoed twice).
3. At `K230# `:
   ```
   ext4load mmc 1:1 0x4000000 /u-boot-modern-trial.bin
   crc32 0x4000000 ${filesize}              # must equal the host crc32
   crc32 0x20000000 0x2000000               # evicts the data cache (no dcache command)
   go 0x4000000
   ```
   `go` passes `a0 = 0` (argc minus the address), which the modern start code
   takes as the boot hart, exactly what the vendor SPL passes.
4. Expected console evidence (transcript to `docs/evidence/modern-uboot/`):
   `U-Boot 2026.10`, `DRAM:  1 GiB`, `Hit any key`, then at the prompt
   `version`, `bdinfo`, `mmc list` (`mmc@91581000: 1`), `mmc info`,
   `ext4ls mmc 1:1`, two `ext4load ... /Image` + `crc32` runs that agree
   (DMA/cache coherency), `env print bootcmd`, and `run blinux` to the NixOS
   login. A lit panel at the prompt is the splash (task 2.5).
5. `ums 0 mmc 1` from the trial U-Boot, J3 to the host: `usb-Linux_UMS_disk_0-0:0`
   with `29f1:0230` -- **NOT RUN this session (J3 not cabled; see 2a).** The
   build still contains `ums` (the `help ums` line proves only that).
5a. Rehearse rollback path 2 from the **2022.10** prompt, RAM only, no write:
   ```
   ext4load mmc 1:1 0x6000000 /fn_ug_u-boot.2022.10.bin
   mmc dev 1
   mmc read 0x7000000 0x1000 0x800
   cmp.b 0x6000000 0x7000000 0x100000
   ```
   `cmp.b` must report the buffers equal. Do **not** run `mmc write`.
6. Failure at any step: reset button or power cycle. The card is unchanged
   except for the two extra files on `/boot`, which are inert.

## 4. Stage a: write the U-Boot slot (after a0 passes and the coordinator approves)

```
# board at `K230# ` of the 2022.10 (or the trial) U-Boot, J3 to the host:
ums 0 mmc 1
# host:
./tools/write-uboot-slot.sh <result-stage1-modern>/fn_ug_u-boot.bin \
    /dev/disk/by-id/usb-Linux_UMS_disk_0-0:0
# Ctrl-C at the board console, then:
reset
```

`write-uboot-slot.sh` writes exactly one 1 MiB window at byte offset 2 MiB with
`dd bs=1M seek=2 count=1 conv=notrunc,fsync`, reads it back with `O_DIRECT`,
and hashes SPL copies 1 and 2 and the environment window before and after: any
change exits 1. It refuses a bare `/dev/sdX`, a partition, an image without
the `K230` magic, an image larger than the window, and a target under 64 MiB;
it asks for the last 12 characters of the by-id path.

Console evidence of success (cold boot; the CH342 bridge re-enumerates for
about 3.4 s on a cold power-on, so a warm `reset` is the way to see the whole
console): the SPL lines and PMU training messages of the **unchanged** SPL,
then `U-Boot 2026.10`, the splash, `ums` on J3, `blinux` to the login, and
`dmesg` containing `canaan,stage1-splash` handled as before.

## 5. Rollback

In order, cheapest first. The rollback image is
`uboot-2MiB-1MiB.bin` (1 MiB, starts with `K230`), hashes above.

1. **New U-Boot reaches a prompt and `ums` works.** `ums 0 mmc 1`, then
   `./tools/write-uboot-slot.sh uboot-2MiB-1MiB.bin <by-id>`; reset.
2. **New U-Boot reaches a prompt but `ums` does not.** At its prompt:
   `ext4load mmc 1:1 0x4000000 /fn_ug_u-boot.2022.10.bin`, check `crc32`, then
   `mmc dev 1; mmc write 0x4000000 0x1000 0x800` (2048 sectors = 1 MiB at sector
   `0x1000` = byte offset 2 MiB). The copy on `/boot` is the 1 MiB rollback
   image, so the length is fixed.
3. **New U-Boot never reaches a prompt** (silent hang, panel dark). Pull the
   card, put it in the card reader, and run
   `./tools/write-uboot-slot.sh uboot-2MiB-1MiB.bin /dev/disk/by-id/usb-...-0:0`
   (the reader's by-id path; `tools/flash.sh` documents finding it). This is
   the proven floor (`docs/uboot-ums.md` section 6; used 2026-09-22).
4. BootROM USB recovery with SW3 held: **UNVERIFIED**
   (`openspec/changes/characterise-bootrom-usb-recovery`), not relied on.

Nothing in stage a modifies the SPL, so the BootROM always reaches a working
SPL that then loads whatever is in the U-Boot slot; rollback is a one-slot
write at every level above.

## 6. What stays open after stage a

Stage b (modern SPL and DDR training) and stage c (OpenSBI v1.9) need their own
procedures; this file does not authorise either. Stage c additionally requires
`CONFIG_K230_PMP_LOCK_OTP=n` in the U-Boot that precedes it (design.md).
