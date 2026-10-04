# Breadcrumb controller host preparation — 2026-10-03

This implements the host portion of mainline task 5g.4. No new kernel, initrd,
DTB or matching bundle was built or staged, and no board/serial action occurred.
Positive qualification of the new realized bundle/source/config and physical
breadcrumb output remain **UNVERIFIED**. Tasks 5g.4, 5g.5 and 5b.5 stay open.

Worktree `/home/jadams/tmp/k230-mainline-uart-progress-breadcrumbs-controller`,
branch `mainline-uart-progress-breadcrumbs-controller`, base `8e66e299`.
Owned paths: existing minimal controller, new focused test file, this host note
and only the 5g.4 preparation note. No board or build slot is reserved.

## Selected variant proof before UART

Typed `--uart-progress-breadcrumbs` requires `--mode minimal`,
`--same-image-shell-pid1` and `--uart-progress`. Original selectors/defaults,
numeric record parsing and protected normal checks retain their paths. It
preserves the [original progress qualification](../../mainline-uart-progress-controller/README.md):
manifest/count/hash/CRC, exact ordinary artifact arguments, archived RISC-V
programs/common loader, matching selected-system kernel and the same kernel
derivation's already-realized dev config. Registration absence, including a
dangling marker, is asserted in both protected normal helpers.

`CONFIG_K230_UART_PROGRESS=y` alone does not qualify the new variant. An
additional bounded read-only host query uses the same verified kernel drv:

```text
nix --offline --extra-experimental-features nix-command derivation show SELECTED_KERNEL_DRV
```

It accepts the observed Nix JSON v4 wrapper with basename-keyed derivations
and `structuredAttrs.src`, or the legacy exact-drv map with `env.src`.
Unknown schemas, missing source or a different derivation fail closed. The
actual immutable source's `drivers/soc/canaan/k230-uart-progress.c` must match
the frozen reviewed applied worker SHA256:

```text
7207dcae9462694a07bd4f7d37d1d9ea43a536496f1b96dd94fed3dfa78c6a22
```

The selected Image, already manifest/hash-bound to that system, must contain
each exact compiled marker string once (including leading/trailing LF and
terminating NUL), and the unique `k230.uart_progress_breadcrumbs=` setup key.
The result preserves source, worker/Image hashes and literal byte offsets.
This is combined source/config/compiled-byte qualification; strings alone do
not prove configuration, placement, ABI execution or hardware output. Full
build/exact-object lifetime/alignment/DT evidence belongs to 5g.2–3.

No guessed dev source symlink is used: the actual old dev output's source tree
contains headers rather than the full patched worker. A missing source or dev
output is never built/fetched by the controller. Host dependencies are Nix,
Python with native Zstd archive support (operator Python 3.14), and the existing
pyserial environment for eventual operation.

The full literal volatile U-Boot command differs from the existing qualified
progress value by exactly one token: `k230.uart_progress_breadcrumbs=1`.
Immutable init, sole serial console, marker suppression, `initramfs_async=0`,
`rdinit=/bin/sh`, existing reporter flag and the three qualified controls remain.
Unsafe/duplicate/alternate values or oversized input fail before UART; printed
U-Boot arguments and exactly one fresh matching kernel-received command line
still gate the sole receipt. No `saveenv`, profile/card changes or candidate
reboot are added.

## Fixed bytes and interpretation

The only accepted complete breadcrumb lines are:

```text
K230_UPB1 point=worker-entry
K230_UPB1 point=first-post-sleep
```

Their producer adds literal leading and trailing newlines. The parser accepts
one of each at most, in order, before numeric samples. Unknown versions/points,
extra fields, echo, duplicates, reordered points, post-sample points, partial
or interleaved text are incomplete/unknown. Split transport chunks may combine
into the original exact bytes; arbitrary console text is not removed or repaired.

The bounded capture starts at `bootm` and ignores the pre-existing rolling
session buffer. It retains direct markers that arrive before the printed Linux
banner, but trusts them only after the fresh selected banner and exact received
arguments qualify that same attempt. Stale/unqualified output never authorizes
input. Missing banner/arguments, byte overflow or transport failure keep facts
unknown; independent fresh normal-return recognition remains available.

Breadcrumb presence/completeness, numeric records and receipt are separate
fields. Neither breadcrumb authorizes input. Only fresh init entry and primary
prompt, after received-argument qualification, permit one fresh builtin receipt.
Qualified complete breadcrumb/numeric lines may follow that prompt in the same
read. There is no retry, proc/identity probe, exit, or candidate reboot afterward.
Capture retains the existing 90-second readiness and 180-second passive
observation deadlines, actual elapsed time and independent protected normal
postflight. Missing/malformed breadcrumbs remain diagnostic-incomplete even
when all numeric samples or normal recovery appear.

With the selected source and gates qualified, worker-entry establishes reaching
its output call, not that the call returned or sleep began. First-post-sleep
establishes that the first sleep and existing stop checks passed and the earlier
entry call returned; earlier output may still have been partial/zero/error.
A later numeric sample establishes progress beyond the post-sleep call and
snapshot/formatting, not the firmware return count or healthy UART/TTY delivery.
Missing any point may reflect scheduling, sleep, output or later work; absence
alone diagnoses none of them. A complete UART record still does not prove that
its own firmware call returned. `observed_after_stimulus` is host arrival order,
not causal sampling time or per-byte RX timing. The existing counter limits,
manual recovery distinction and open ordinary-root/glass gate remain unchanged.

## Host proof

Checks completed 2026-10-04 01:11 UTC (2026-10-03 local):

```text
python3 tests/test_mainline_uart_progress_breadcrumbs_controller.py  # 17 passed, 0.065s
python3 tests/test_mainline_uart_progress_controller.py              # 20 passed, 0.572s
python3 -m unittest discover -s tests -p 'test_mainline_drm*trial.py'   # 214 passed, 31.007s
python3 tests/test_mainline_shell_pid1_comparison.py                  # 14 passed, 1.406s
```

The new tests exercise actual parser/transport functions and the real capped
pump with isolated fixtures: early/split/late markers, prompt-plus-marker in one
read, fresh args, strict failures, one/no stimulus, source/compiled-byte gates,
pre-serial rejection and a full mocked five-load/CRC/preflight path. Fixtures
do not open UART or build. Existing progress tests retain transport-failure,
rolling/overflow and protected return guards.

Two additional read-only checks passed locally: the author's applied worker
file SHA matches the pin; and the actual cached old reporter kernel derivation
resolves to original `4av3w0…` source and is rejected as the wrong worker despite
its enabled reporter config. The query used the observed JSON v4 schema.
This is an actual negative host artifact gate, not new-bundle positive proof.
Strict OpenSpec validation/diff checks are recorded at commit handoff.

After reviewed source/full-build/config/exact-object proof and actual positive
host preparation, the sole board operator may use fresh private output paths:

```sh
python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal \
  --same-image-shell-pid1 --uart-progress --uart-progress-breadcrumbs \
  --bundle BUNDLE --manifest PRIVATE_MANIFEST --normal-report PRIVATE_NORMAL \
  --log PRIVATE_LOG --result PRIVATE_RESULT
```

No operator action was performed here. Root retains the separate board
reservation, physical result, protected recovery and deployment responsibilities.
