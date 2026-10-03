# Autonomous UART observer controller: host preparation

Source/host checks on 2026-10-03 UTC, completed at 05:55 UTC. Worktree
`~/tmp/k230-mainline-uart-observer-controller`, branch
`mainline-uart-observer-controller`, base
`9854479615d2800d53e79cf14939397a93e3fe1f`. Owned files are the new
`tools/mainline-drm-uart-observer-trial.py`, its focused test file and this note.
No board/UART or kernel/build slot was used. Existing controllers, Nix sources,
task checkboxes, normal image and dashboard were not changed.

This implements the host side of the separate optional helper/bundle
[protocol](../mainline-system-trial/uart-observer-protocol-2026-10-03.md).
The historical base is exactly
`/nix/store/5yqilsfyj35jzrcqjjqilkr6sd47qlms-k230-mainline-drm-trial-boot-files`.
Its successful protected standalone blkid result is a required private
prerequisite. That physical result does not establish a new observer bundle's
physical behavior. New bundle realization and inspection remain separate work.

Before opening UART, preparation reuses the immutable artifact/manifest and
protected normal guards, and additionally checks:

- Exact observer metadata, source and executable digests; ELF64 little-endian
  RISC-V machine 243; unique SHA coverage of `observer.json`.
- Same proven kernel path and Image bytes. Temporary DTB copies have only
  `/chosen/bootargs` deleted, then sorted `dtc` output must match. The selected
  DT bootargs must separately match the selected system's original arguments.
- Ramdisk wrapper size/header/data CRCs and byte-identical selected-system
  initrd; actual bounded newc archive inspection with no extraction. The helper
  inside that archive must equal the inspected executable. Original debug-shell
  unit hash must match, with one nonce-conditioned ExecStart override, Restart=no,
  only standard locale/timezone environment, and the version marker. Original
  TTY reset/vhangup settings remain preserved by exact unit identity; actual
  runtime ttyS0 selection and ownership remain candidate helper guard gates.
- Matching base blkid/protected-return facts and the registration-marker
  absent/dangling check in both protected normal phases.

Host requirements are Python 3.14 with `compression.zstd`, plus `dtc`, `fdtput`
and `fdtget` on PATH. The selected initrd is Zstandard; unsupported hosts fail
before serial access. CI's older Python can exercise gzip archive fixtures;
the native Zstandard test explicitly skips without that module, and actual DT
tests explicitly skip without the DT tools. A skip supplies no artifact proof.
Compression was not changed to accommodate host inspection.

After protected normal preflight, the controller recomputes exactly five
qualified controls plus three observer identity arguments using the fresh
normal boot ID and fresh nonce. It uses existing per-load counts/CRCs and exact
printed arguments before the volatile boot. No rdinit, clock-ignore or boot-time
trace argument is added. A continuous receive phase begins at candidate boot,
so early SPL/normal return cannot disappear while waiting for readiness.

Candidate reception requires the fresh kernel/manager, checksum-verified
ready/before frames and a primary prompt within the helper's observation window.
The host then sends exactly one nonce receipt. It sends no candidate input
afterward, whether the receipt is acknowledged or unknown. The helper owns its
renewed guard checks and prearranged direct return. Frames require exact sequence,
fields, byte length and CRC; inserted printk cannot be stripped into a valid
frame. Returned chunks are tracked independently of the serial buffer's rolling
limit. Partial observations and private wire size/SHA remain in the result even
after timeout or transport failure.

Fresh ordered SPL, normal 6.6.36 banner, login and prompt independently permit
protected postflight even when candidate readiness failed. Postflight must
prove exact protected identities/services/eight hashes and a different boot ID.
Missing receipt or incomplete/failed observer with recovered normal yields
`recovery-verified-diagnostic-failed`, never a pass. Unknown return leaves
`recovery-required-unknown`; there is no host reboot retry. A userspace timer
cannot guarantee return from a kernel stall, so operator reset remains possible.

Host proof commands:

```sh
python3 -m unittest discover -s tests -p test_mainline_drm_uart_observer_trial.py
python3 -m unittest discover -s tests -p 'test_mainline_drm_*trial.py'
openspec validate the-board-runs-a-mainline-kernel --strict
git diff --cached --check
```

Results: **26 focused tests passed**, **188 combined controller tests passed**,
strict change validation passed. These include real PrivateSession pumps,
split/stale/duplicate/malformed/late frames and receipts, unknown transport,
byte limits, early return without candidate banner, one-input recovery/failure
results, load/CRC/bootargs failure, actual isolated DTB compilation/comparison,
actual newc/Zstandard fixtures, ELF/unit/drop-in failures, full preparation
fixtures and a dangling registration-marker assertion. Current host skips: zero.
After the final environment-section check, the focused suite was repeated.

The bounded archive reader also read the actual historical initrd
`/nix/store/jdgads5ibbb0zflglhjfncq8ayc1jbfz-initrd-linux-riscv64-unknown-linux-gnu-7.3.0-rc5/initrd`:
2025 entries; original debug-shell unit SHA-256
`edc8fe166b94d3c9e76879662780679b6092944f88e9966a27a41f0aa2767a81`
matched. This is a host artifact check of the base, not inspection or physical
proof of an unrealized observer bundle.

The root operator must first review/realize the helper bundle, inspect its
exact identity, stage/export matching files and reserve the board. Then use
this command with `observer_bundle` set to that reviewed immutable output;
all named input/output files must be private, matching and outside the repo,
and output filenames must be fresh:

```sh
python3 tools/mainline-drm-uart-observer-trial.py \
  --bundle "$observer_bundle" \
  --manifest "$HOME/tmp/k230-mainline-uart-observer-board/candidate-manifest.json" \
  --normal-report "$HOME/tmp/k230-mainline-uart-observer-board/normal-report.json" \
  --blkid-result "$HOME/tmp/k230-mainline-blkid-board/trial-result.json" \
  --log "$HOME/tmp/k230-mainline-uart-observer-board/observer-uart.log" \
  --result "$HOME/tmp/k230-mainline-uart-observer-board/observer-result.json"
```

<!-- UNVERIFIED --> Observer hardware results, repaired receive behavior,
ordinary usable root and deliberate glass touch remain unperformed. This
diagnostic does not close mainline task 5b.5. Review/landing and matching bundle
inspection precede a separate reserved physical trial.
