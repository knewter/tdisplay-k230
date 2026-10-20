# Current splash investigation: source baseline, not a fix

Task 4.1 of `the-mainline-kernel-keeps-the-boot-splash` remains open
(8/9 tasks complete). The October 12 films show transient logo corruption;
they do not establish whether it reproduces on the currently installed
kernel. This directory records a read-only source audit on October 20, 2026,
after the operator accepted the native Settings top drawer. No new film,
reproduction, kernel change or removal of the corruption is claimed.

## Installed baseline and provenance

The separately committed ordinary-boot observation in
[`../../shade-status/persistent/README.md`](../../shade-status/persistent/README.md)
records the accepted system and cleanup. This audit reuses that boot's
protected kernel journal; it performs no additional SSH command, reboot or
board mutation. The board and build slot are released. Landscape remains
1232×568 with output transform 270.

| Identity | Value |
| --- | --- |
| Audit worktree revision | `8b0ef828bcbec5f2c11d3c37cc3892284e2f50c8` |
| Ordinary boot ID | `9cc88abc-dc62-490e-8035-5d4832558a41` |
| Running, booted and persistent system | `/nix/store/p501mchy0dq9lyjnaxwkx5s2pdm4i2yj-nixos-system-nixos-26.11.20260919.20b1ddd` |
| Kernel GNU build ID | `7a61d8cea3e26df94695189b766de3fd66fa6860` |
| Kernel output | `/nix/store/21lz5c6pkk329c0xcac9bzlx40dplrlk-linux-riscv64-unknown-linux-gnu-7.3.0-rc5` |
| Kernel derivation | `/nix/store/0zq193wki0mimhnmsr0gq406g901c5gx-linux-riscv64-unknown-linux-gnu-7.3.0-rc5.drv` |
| Configured source | `/nix/store/1sr18plbky4kzy5x1gjqmy4pqdm68zbc-linux-mainline-k230-drm-src` |

[`source-audit.json`](source-audit.json) records the original audit time,
source hashes, protected input hash, selected journal lines and limits.
[`current-boot-allowlist.log`](current-boot-allowlist.log) contains only the
selected safe lines. The full journal stays outside Git because unrelated
boot messages can contain private data. These are printed journal monotonic
timestamps; no camera-to-kernel clock mapping has been qualified from them.

## What the source establishes

- `nix/patches/mainline/drm/canaan_vo.c`, `canaan_dsi.c`, `canaan_drv.c`
  and `panel-canaan-universal.c` are byte-identical to the four corresponding
  files in the configured source above. This identifies the source used by
  the installed kernel's derivation, rather than an unrelated source fixture.
- `canaan_vo_probe` already calls `devm_clk_bulk_get_all_enabled` before
  unused-clock cleanup. `git blame` attributes those lines to
  `ad627a2bf10c331602c7721efb5badb46d67a29d`, dated October 5, 2026, before
  the October 12 glitch films. Merely adding that safeguard again cannot be
  presented as a new fix.
- The reused journal records `leaving fbdev unset` at 7.378308, unused-clock
  cleanup at 7.383367, real-root module loading at 28.667394, and preservation
  of VO/panel/DSI at 49.137026/49.154606/49.559692. These establish the logged
  sequence. They neither show the glass nor identify when a bad frame occurs.
- `canaan_vo_irq_handler` writes `0xffffffff` to `VO_DISP_IRQ_STATUS`
  without reading or recording its pending value. This source does not
  establish an underrun or correlate a hardware status bit with corruption.

<!-- UNVERIFIED: reproduction on this kernel, the cause of any corruption,
and removal of the defect. Clock gating, FIFO, memory bandwidth and probe
activity remain hypotheses. No speculative register writes were performed. -->

## Repeat the source checks

From the repository at the audit revision, with the recorded store paths
still present:

```sh
kernel=/nix/store/21lz5c6pkk329c0xcac9bzlx40dplrlk-linux-riscv64-unknown-linux-gnu-7.3.0-rc5
nix-store --query --deriver "$kernel"
nix derivation show /nix/store/0zq193wki0mimhnmsr0gq406g901c5gx-linux-riscv64-unknown-linux-gnu-7.3.0-rc5.drv
python3 docs/evidence/mainline-boot-splash/current-baseline-2026-10-20/check-source.py
git blame -L 900,914 -- nix/patches/mainline/drm/canaan_vo.c
```

The recorded Nix JSON format is version 4: the derivation entry's
`structuredAttrs.src` selects the source. An earlier exploratory read of the
legacy `env.src` field failed with `KeyError` before any mutation or evidence
claim; it is not a build failure. `check-source.py` repeats the derivation
and hash checks and verifies the committed allowlist hash. It does not fetch,
build, access the board or claim to re-read the protected full journal.

## Next physical capture and its timing gate

The original [board evidence](../board/README.md#transient-scanout-glitches-on-the-splash-system-open)
places the corruption near kernel 17/27 seconds, with approximately ±2 seconds
of clock uncertainty. Its complete-boot films are evidence of the old defect,
but that timing does not meet task 4.1's ±0.1-second requirement. Earlier
camera helpers' first FFmpeg progress message is a process-start bound,
not an exposure timestamp or a kernel/video synchronization event.

At the source-audit check, `/dev/video*` and `/sys/class/video4linux` had no
camera devices, and no camera connector tool was available. A request for
the board-facing camera to be reconnected, or its live feed URL, is pending.
The accepted ordinary reboot above was **not filmed**.

Once a camera is available, the next bounded board action is:

1. Reserve the board with `/tmp/k230-board.lock`; inspect the current boot
   identity, profile and rollback roots before changing anything. Preview the
   camera, select the actual panel ROI and a static off-panel control, and
   record exposure/frame-rate controls. Reusing an old ROI is insufficient.
2. Qualify how camera exposure/packet timestamps map to a host clock and how
   that clock maps to this boot's kernel clock. Record measured intervals,
   buffering, clock drift assumptions and the resulting uncertainty. A
   separately observed optical marker with a bounded kernel presentation
   timestamp is another possible anchor. The combined bound must be at most
   ±0.1 seconds; loose SSH arrival times or compositor-config log offsets
   cannot substitute. Choose and validate the method against the available
   feed before counting a film as proof.
3. Record a complete normal warm reboot of the current accepted default,
   covering every frame from logo appearance through the compositor's first
   frame. Keep landscape. Use SSH through the protected configuration for
   the reboot and post-boot identity; no USB data cable is required. Preserve
   the raw film, packet timestamps, identity and logs, and extract all
   candidate corruption frames against the static control. Hash and account
   for binary evidence before committing it.
4. If corruption reproduces, correlate qualified frame intervals with logs
   before selecting a narrow kernel change. Build and prove that change,
   then repeat the full default-boot film. If it does not reproduce, record
   only that bounded observation; absence in one film alone does not explain
   removal of the historical defect. Release the board after capture.

The task remains unchecked until its actual fix and named physical proof
exist. No archive, cold-power claim, scope reduction or waiver follows from
this source audit.
