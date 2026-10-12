# CPU0 started from Linux through remoteproc, 2026-10-12

Coprocessor task 5.1: a fully booted Linux (mainline 7.3.0-rc5 on CPU1, the
shell compositor running) loads the echo payload into the CPU0 carveout,
writes the CPU0 boot vector and pulses `RST_CPU0` through the standard
remoteproc `state` file, then exchanges requests with CPU0 through the
shared slot page.

**Evidence class:** physical board, one serial-console session (host-stamped)
plus a native `grim` capture of the panel's compositor output. No camera.
One run.

**Authorization.** The operator answered "yeah go for it" on 2026-10-12 to
running task 5.1 as a one-off boot of the trial kernel and DT with the
installed default unchanged. CPU0 release on the normal card was authorized
earlier ("Yes, go"; see `../echo-physical-2026-10-12/README.md`).

## What ran

| Item | Value |
| --- | --- |
| Driver | `nix/patches/mainline/k230_cpu0_rproc.c` (this commit): `.load` copies the raw image to the carveout base and zeroes the rest up to the end of the slot page; `.start` writes the carveout base to `0x91102100`, reads it back, then `reset_control_reset()` on `RST_CPU0`; `.stop` still returns `-EOPNOTSUPP` (task 5.2). `cpu0_echo` attribute posts one request and polls its response line (100 ms bound). |
| Kernel | `.#kernelMainlineDrmRproc`, `/nix/store/i29ldf7sl1w9lj1i5ppb85qi8v39l1vf-…-7.3.0-rc5`, `Image` SHA-256 `93148fa3f30dc0c98141264ae36cb96c7ce0e031159c92b2b952ae2831fdb5d6` |
| Module | `k230_cpu0_rproc.ko.xz` SHA-256 `f7c3a94d03cdb8967bbd0169e175cf1ac24b425c71345d79f9aaa6e16c880225` (no build warnings for the file) |
| DT | `.#deviceTreeMainlineDrmHotplugCpu0`, SHA-256 `66fa0cdc75c69a5879f3bb39ec94a4566d94d7c2c40cd3582aaadd3f219b54ab`. Decompiled and diffed against the installed bundle's `k230-tdisplay.dtb`: the only differences are the `cpu0-firmware@7000000` no-map node, the `remoteproc@91102100` node, phandle renumbering, and the bundle's embedded `chosen/bootargs` (U-Boot sets bootargs either way). |
| Payload | `/boot/small-core-echo.bin`, 224 bytes, SHA-256 `2ec68316…46cc` (task 3.2) |
| Rest of boot | installed default `kc3iyr4c…` (splash system): its staged `bootargs.txt`, `initrd.uimg`, and backup OpenSBI `fw_jump` |

Trial files were copied over SSH to `/var/lib/k230/cpu0-trial/` (hashes
matched on the board). Command, under the board lock:

```
flock /tmp/k230-board.lock tools/cpu0-linux-start-session.py --out run-1.txt \
  --stage /var/lib/k230/coherent-boot/kc3iyr4cnjlswa87kkpi81qgc1is6hli-20261012f \
  --bundle /nix/store/kjlnrxv8vdk92lh84w2bkd1v0mx456hy-k230-coherent-shell-boot-files \
  --image <kernel>/Image --dtb <dtb>/k230-tdisplay-mainline-drm-hotplug-cpu0.dtb --hold 45
```

Excerpt: [run-1-serial-excerpt.txt](run-1-serial-excerpt.txt) (escape and
OSC sequences removed; they carried terminal titles and systemd session
identifiers). The full raw transcript stays private.

## Result

U-Boot loaded all five files with matching CRC32 (Image `cbfe8fd7`, DTB
`8ecd8d13`, initrd `c5a9d6cc`, fw_jump `99b89787`, bootargs `762be152`) and
booted. Linux logged
`OF: reserved mem: 0x0000000007000000..0x00000000070fffff (1024 KiB) nomap non-reusable cpu0-firmware@7000000`.

Before the start (Linux uptime ~207 s, `systemctl is-system-running` →
`running`, `shell` and `seatd` active, `swaymsg -t get_version` answered):

- `insmod` → 0; `remoteproc0` named `k230-cpu0`, state `offline`.
- `cpu0_status`: `boot_vector 0x91200000` (value left by reset and stage 1;
  not ours), `reset_status -524` (`-ENOTSUPP`: reset-k230 has no `.status`,
  as the skeleton predicted), `carveout [mem 0x07000000-0x070fffff]`,
  `slot_magic 0x00000000`.
- Pre-start request `0x5a5a5a5a` → `No such device`. That is the driver's
  magic check refusing to post, not a measurement of CPU0; it shows the slot
  page held no echo magic before the start.

Start (`echo start > state`, kernel 208.058 s):

```
remoteproc remoteproc0: powering up k230-cpu0
remoteproc remoteproc0: Booting fw image small-core-echo.bin, size 224
remoteproc remoteproc0: CPU0 released at 0x07000000
remoteproc remoteproc0: remote processor k230-cpu0 is now up
```

`start_rc=0`, state `running`, `boot_vector 0x07000000`, `slot_magic
0x4f484345 (echo payload)`, `served 0` — the magic was zeroed by `.load`, so
CPU0 wrote it in this boot.

Echo requests, each a different value, answered by CPU0:

| seq | value | rsp (value+1) | inv (~value) | served | latency µs |
| --- | --- | --- | --- | --- | --- |
| 1 | `0x00000000` | `0x00000001` | `0xffffffff` | 1 | 80 |
| 2 | `0x12345678` | `0x12345679` | `0xedcba987` | 2 | 85 |
| 3 | `0xfffffffe` | `0xffffffff` | `0x00000001` | 3 | 66 |
| 4 | `0xffffffff` | `0x00000000` | `0x00000000` | 4 | 82 |
| 5 | `0xdeadbeef` | `0xdeadbef0` | `0x21524110` | 5 | 80 |
| 6 | `0x00000001` | `0x00000002` | `0xfffffffe` | 6 | 87 |
| 7 | `0x80000000` | `0x80000001` | `0x7fffffff` | 7 | 76 |
| 8 | `0x7fffffff` | `0x80000000` | `0x80000000` | 8 | 89 |

Then 1000 more requests (values 0–999) in a shell loop: `ECHO_BULK ok=1000
of 1000`, last `seq 1008 value 0x000003e7 rsp 0x000003e8 inv 0xfffffc18
served 1008 OK`. Every answer is checked in the driver (`rsp == value+1`,
`inv == ~value`, `rsp_seq == seq`); a mismatch or a 100 ms timeout fails the
write. Latency is from the `req_seq` store to the poll that saw `rsp_seq`,
and includes the poll's `usleep_range(10, 50)`, so it is an upper bound at
that granularity.

After the start (immediately, and again after a 45 s hold):

- remoteproc state `running`; `systemctl is-system-running` → `running`;
  `shell` and `seatd` `active`; `swaymsg -t get_version` answered (sway 1.12).
- `grim` capture of the compositor output succeeded (`grim_rc=0`):
  [cpu0-start.png](cpu0-start.png), SHA-256
  `a6a8591d874042351b5785b57b87277c1af63eeb007045ebb220960a896a03e8`; it
  shows the shell's terminal prompt on the panel's 568×1232 output.
- Requests `seq 1009` and `seq 1010` (`0xa5a5a5a5` → `0xa5a5a5a6`/`0x5a5a5a5a`)
  answered, `served 1009`/`1010`.
- `dmesg --level=err,warn` holds only boot-time lines (dummy regulators,
  DRM plane blend notice, a BTF mismatch note for modules, the 8189fs taint);
  nothing after the module load or the start.

Then `reboot`. The board returned to the installed default: over SSH,
`/run/booted-system` is `kc3iyr4c…`, `/sys/class/remoteproc` does not
exist, the DT has no remoteproc node, `shell` active.

## Notes and limits

- **Linux side, no cache maintenance.** The driver maps the no-map carveout
  with `devm_memremap(..., MEMREMAP_WC)`; on this kernel
  (`CONFIG_RISCV_ISA_SVPBMT=y`, a non-RAM range) that goes through
  `ioremap_wc` and is expected to be an Svpbmt NC mapping. The page-table
  attribute itself was **not inspected** (UNVERIFIED); what was observed is
  that 1010 exchanges were correct with no Linux-side cache maintenance at
  all, while CPU0 runs `l2cache.ciall` per poll. Contrast the U-Boot run,
  where CPU1's cacheable view gave 0/4 until it was evicted.
- **Task wording.** Task 5.1 names `reset_control_deassert()`. The binding
  decision (`../mainline-reset-binding-decision.md`) and the spec delta
  supersede that: `RST_CPU0` has only `.reset` (a pulse), and the driver
  uses it. No other reset line, power register or mailbox register is
  written.
- **Daily modules on the trial kernel.** The installed system's modules
  (same version string) loaded into the trial kernel; the only notice was
  "Kernel module BTF mismatch detected". Not a concern for the daily boot,
  which never runs this kernel.
- **Session tool fix after the run.** The shell-readiness poll looked for
  `\nactive`, but bash's bracketed-paste reset puts `\x1b[?2004l\r` before
  the answer, so the poll ran to its 120 s limit (100–217 s) although every
  answer was `active`. The match was changed to the line ending after run 1;
  nothing else in the tool changed. The measurements above were taken after
  that wait.
- **Not shown.** Stop/restart without a reboot (5.2: no held reset exists),
  repeated start cycles or a concurrent workload (5.3), interrupts or the
  hardware mailbox, a camera view of the panel during the run, and touch
  interaction with the shell. "Shell responsive" here means the serial root
  shell answered every command, systemd reported `running`, the compositor
  answered IPC and produced a frame for `grim`.
