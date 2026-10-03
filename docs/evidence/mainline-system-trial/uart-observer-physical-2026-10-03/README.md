# Autonomous UART observer: physical READY boundary

Evidence class: physical board UART runtime, with a separate limited private
camera observation. Source revision `11d49eb0f72d28c0f9cdc070fea4662410451c10`;
integration branch `integrate/mainline-probe-path`, bounded base `65578ff2`.
The coordinator held the build slot, then the board/serial reservation.

The matching observer bundle is `/nix/store/16cpjjiifxgwyb6bndhi39vfmlvcdw6h-k230-mainline-uart-observer-boot-files`; system
`/nix/store/k1zjqdn4ks7b5dd7b3py6cavhf85g6j6-nixos-system-nixos-26.11.20260919.20b1ddd`. Kernel remains the tested `9vdk79…` / Linux
7.3.0-rc5. Exact public artifact/source digests and immutable paths are in
[result.json](result.json). The original five-clock SD1 support is retained;
no `clk_ignore_unused`, kernel patch, persistent boot selection or normal
profile change was introduced by this diagnostic.

## Preparation and command

The first wrapper build failed because `cp -a` retained a read-only output
directory. The corrected wrapper built, but controller preparation rejected
its missing helper in the system-derived closure inventory. Both were caught
before UART. The optional system now retains the same helper through
`system.extraDependencies`; the final rebuilt bundle passed standard matching
Image/DTB/ramdisk/hash/CRC checks and the controller's full actual archive and
closure checks. These preparation limits and fixes are recorded in
[the host note](../uart-observer-host-2026-10-03.md).

The native helper's 18 tests and controller's 26 tests passed on the integrated
source. No tests were repeated to claim a physical result. Under the build
lock, `nix build .#kernelMainlineUartObserverBootFiles --no-link
--print-out-paths --max-jobs 1 --cores 16` passed. Actual initrd inspection
verified the ELF64 little-endian RISC-V helper, exact version marker/drop-in
and unchanged original debug unit. Both the kernel Image and normalized DT
hardware remained equal to the proven base. Four new closure paths (634 total
bundle closure, 630 system inventory) were exported and staged; transfer SHA,
store import, separate observer GC root and staging script returned RC=0.

From the integration worktree, with Python3.14 and `dtc` tools:

```sh
nix shell --inputs-from . nixpkgs#dtc --command \
  python3 tools/mainline-drm-uart-observer-trial.py \
  --bundle /nix/store/16cpjjiifxgwyb6bndhi39vfmlvcdw6h-k230-mainline-uart-observer-boot-files \
  --manifest "$HOME/tmp/k230-mainline-uart-observer-board/candidate-manifest.json" \
  --normal-report "$HOME/tmp/k230-mainline-uart-observer-board/normal-report.json" \
  --blkid-result "$HOME/tmp/k230-mainline-blkid-board/trial-result.json" \
  --log "$HOME/tmp/k230-mainline-uart-observer-board/observer-uart.log" \
  --result "$HOME/tmp/k230-mainline-uart-observer-board/observer-result.json"
```

## Observation and limits

Protected normal preflight passed before the volatile boot; each U-Boot load
and CRC and printed volatile bootargs passed the controller's checks. Fresh
mainline and systemd 261.2 banners were observed. One complete, fresh, CRC-checked
sequence 0 `READY` frame (83 payload bytes) was observed. It reports the guard
marker, main shell PID and 12-second window. The matched helper emits this only after
its initial guard and getter operation finish; this narrows the observed stop
but does not publish any counter values or identify a kernel cause.

No `before`/`after`/`return` frame or primary shell prompt followed. The host
reception gate therefore sent **zero receipt commands**. Return acknowledgement
was unknown after 60 seconds; passive recovery continued to the 180-second bound after READY.
No new SPL/normal boot was observed. The controller exited 2 with
`recovery-required-unknown`; no candidate input or reboot retry followed.

Final UART write timestamp: `2026-10-03T06:15:42.034494+00:00`. Controller result written: `2026-10-03T06:18:42.042507+00:00`.
Private raw UART: 53,905 bytes, SHA256
`7fefbf17759b9ea8accd808a3e6cb9fcdf92ad811cb730eba62118450ddd8427`. Its final printed kernel timestamp is 8.103408.
The raw log, volatile nonce/boot IDs and transfer URL remain private.
A separately reserved C920 camera capture showed boot text with glare; it does
not establish readable candidate identity, a usable root, or deliberate touch.
That private frame is not published.

The user pressed reset. [Protected normal postflight](operator-reset-recovery.json)
passed with a fresh boot ID, the exact system/profile/kernel/init, three active
shell services, all eight unchanged protected boot hashes and registration-marker
absence. Qualified normal Home IPC returned RC=0, and a separately reserved
private camera frame visually showed Home icons, clock and background. Glare
limits detail; it is not published and is not a mainline/touch proof. This proves operator-reset
recovery; automatic return from the observer remains **UNVERIFIED**.
Task 5b.5 remains open: ordinary usable mainline root, panel photograph,
deliberate glass touch and protected return are not satisfied by READY or host
checks. Further source review must distinguish helper early exit, kernel
progress/console output and RX delivery; none is claimed as the cause here.
