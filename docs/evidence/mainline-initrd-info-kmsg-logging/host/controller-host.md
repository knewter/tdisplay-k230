# Fixed info/kmsg child: controller host proof

Prepared at 2026-10-05T03:17:11Z in branch
`mainline-initrd-info-kmsg-controller`, worktree
`~/tmp/k230-mainline-initrd-info-kmsg-controller`, based on
`b90a5318d11290f27e6d47dcc3284b9da060d3c6`. Owned paths are the ordinary trial
controller, its new kmsg test file and this note. No UART, board, camera or
build resources were reserved. This is task 5q.1 source/fixture evidence;
actual artifact preparation and physical capture are separate gates.

The typed begin-only `--initrd-info-kmsg-logging` selector requires both
`--wait-initramfs-in-initcall --without-boot-markers` and excludes debug and
info-console selectors. It selects exactly
`rd.systemd.log_level=info rd.systemd.log_target=kmsg`. Compared with the
info-console policy, only `console` → `kmsg` changes: 355 → 352 argument bytes,
373 → 370 literal U-Boot command bytes. The fixed shared selector helper checks
types and exclusivity; it does not provide a generic logging editor. Existing
safe quoting, the 512-byte bound and singleton argument checks remain.

Meaningful host fixtures cover the destination-only transform, unchanged prior
policy values, pre-output/UART invalid phase/type/parent/mode rejection,
inherited plain/initrd underscore/hyphen aliases and conflicting controls,
strict literal/live arguments, protected saved-mode continuation and old-state
default false. A full mocked begin/finish checks the selected mode and guarded
identity protocol; renewed touch preparation retains the saved selection.
The unknown-readiness fixture runs the five load/CRC steps and verifies that
`bootm` is the last input, while the private result preserves selected kmsg mode
and unverified recovery.

All prior top-level function bodies except the seven selected policy/run/CLI
functions are AST-identical to the reviewed base. This includes boot, passive
readiness, exchange, identity, protected recovery and touch observation. The
existing debug fixtures retain the actual-pump/full-private-log proof beyond
the 131072-byte rolling buffer cap. No raw-record sanitization or new readiness
rule is introduced.

Commands used `TMPDIR="$HOME/tmp"` and `PYTHONDONTWRITEBYTECODE=1`:

```sh
python3 -B tests/test_mainline_initrd_info_kmsg_logging.py
python3 -B tests/test_mainline_initrd_info_logging.py
python3 -B tests/test_mainline_initrd_debug_logging.py
python3 -B tests/test_mainline_drm_system_trial.py
openspec validate the-board-runs-a-mainline-kernel --strict
git diff --check
```

Results: new 9 tests passed in 0.755 seconds; info 10 passed in 0.644 seconds;
debug 13 passed in 0.661 seconds; ordinary 36 passed in 1.078 seconds. Strict
validation and whitespace checks passed. These tests use isolated temporary
fixtures and mocked wire/artifact responses, without actual artifact
qualification or hardware input.

```text
f5f23057119cb79228ebb868e7f92524a6f9a6f230b9931d438013d34b8da0c5  tools/mainline-drm-system-trial.py
61958e3d24a19abf6c9d511a0ebefd056099f3703bd317a5afaea7107e45b8e8  tests/test_mainline_initrd_info_kmsg_logging.py
```

The coordinator's separate actual-artifact API is
`prepare(bundle, manifest, normal_report, wait_initramfs_in_initcall=True, without_boot_markers=True, initrd_info_kmsg_logging=True)`.
After that gate and NEW protected recovery, the operator command adds
`--initrd-info-kmsg-logging` to
`begin --wait-initramfs-in-initcall --without-boot-markers`, using reviewed
artifact/normal inputs and fresh protected state/log/result paths. Exclusive
board/UART ownership and the existing 180-second bound remain required.

[The selected source audit](../../../research/mainline-initrd-info-kmsg-comparison-2026-10-05.md)
grounds kmsg opening/writing and priority-6 eligibility under console threshold
7. Systemd may fall back to console; systemd and kernel filtering/rate limiting
may drop records. Selector or argument qualification proves neither exclusive
kmsg delivery nor absence of console operations. A changed observed boundary
would show sensitivity to destination selection, without proving a blocked
call or cause. Silence cannot distinguish earlier PID1 setup, backend failure,
filtering/dropped output or scheduling. Actual p2 preparation, ordinary login,
candidate/protected normal recovery and panel/glass acceptance are not proved
here. Task 5b.5 remains **UNVERIFIED**.
