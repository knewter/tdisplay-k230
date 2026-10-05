# Fixed info/console child: controller host proof

Prepared at 2026-10-05T02:47:30Z in branch `mainline-initrd-info-controller`,
worktree `~/tmp/k230-mainline-initrd-info-controller`, based on
`6bb1e8eed3e5ed1c2d71a3f03575c329130cf359`. Owned paths are the ordinary
controller, the new info test file and this note. No UART, board, camera or
build reservation was taken. This is source/fixture proof for task 5p.1.

The typed begin-only `--initrd-info-logging` selector requires
`--wait-initramfs-in-initcall --without-boot-markers` and excludes
`--initrd-debug-logging`. It selects exactly
`rd.systemd.log_level=info rd.systemd.log_target=console`. The only difference
from the debug comparison's arguments is `debug` → `info`: 356 → 355 argument
bytes and 374 → 373 literal U-Boot command bytes. The existing safe literal
transport and 512-byte bound remain. A small common helper checks both logging
selectors' types/exclusion and supplies their fixed controls; inherited alias
and competing-control rejection is shared without changing unselected policy.

Protected state records the typed info selection, restores it for touch/finish,
and defaults false for old states. Invalid modes/types/combinations, malformed
saved selections and inherited plain/initrd logging aliases fail before output
creation or UART opening. Exact live arguments retain both singleton controls.
The new fixtures exercise successful mocked begin/finish, resumed touch
preparation, five guarded loads/CRCs through the shared transport, and a failed
readiness run that preserves the selection without further candidate input.

The common boot/readiness/identity/exchange/recovery functions are AST-identical
to the reviewed base. The existing debug tests therefore continue to provide
the actual-pump proof of split fresh readiness beyond the 131072-byte rolling
buffer cap with complete private logging and unknown-no-input write spies.
No kernel record/argument sanitization or new readiness rule is introduced.

Commands used `TMPDIR="$HOME/tmp"` and `PYTHONDONTWRITEBYTECODE=1`:

```sh
python3 -B tests/test_mainline_initrd_info_logging.py
python3 -B tests/test_mainline_initrd_debug_logging.py
python3 -B tests/test_mainline_drm_system_trial.py
openspec validate the-board-runs-a-mainline-kernel --strict
git diff --check
```

Results: new 10 tests passed in 2.450 seconds; debug 13 passed in 1.831 seconds;
ordinary 36 passed in 2.827 seconds. Strict validation and whitespace checking
passed. The initial new-test run failed only because an AST fixture referred
to a nonexistent `candidate_checks` function; changing the fixture to the
actual `identity` function produced the final pass. This was a host harness
error, without hardware involvement. Tests use isolated scratch paths and
mocked wire/artifact responses; they do not perform actual artifact preparation.

```text
7239be4923e15cb699d96cf8465ca6345d8f5900ef95c3667f4bf261bbe95beb  tools/mainline-drm-system-trial.py
09be7251413a98676a359bf4b1635455b13d14a14e24b72a30ae175e1b9e25ec  tests/test_mainline_initrd_info_logging.py
```

Actual preparation is a separate coordinator gate:
`prepare(bundle, manifest, normal_report, wait_initramfs_in_initcall=True, without_boot_markers=True, initrd_info_logging=True)`.
It must qualify the same immutable p2 artifacts and normal anchors before an
operator uses fresh protected state/log/result paths with
`begin --wait-initramfs-in-initcall --without-boot-markers --initrd-info-logging`.
That physical use requires NEW protected recovery and the operator's exclusive
board/UART reservation. This note establishes neither a fresh normal preflight
nor a physical comparison/recovery result.

[The selected source and bounded comparison analysis](../../../research/mainline-initrd-info-console-comparison-2026-10-05.md)
ties systemd 261.2 to exact official commit/archive hashes and raw-file startup
and logging references. The prior debug/console result lacked a systemd banner;
it did not establish `/init` exec success or a blocked console operation. A
change in observed progress with info would show sensitivity to one changed
value, without identifying a call or hardware cause. Silence cannot separate
earlier PID1 setup from console open/write. Ordinary root/panel/glass acceptance
and task 5b.5 remain **UNVERIFIED**.
