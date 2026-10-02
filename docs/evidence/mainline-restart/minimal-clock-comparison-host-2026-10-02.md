# Minimal runtime tracing and clock comparison — host preparation

Host work at 2026-10-02 19:29 UTC uses branch
`mainline-minimal-clock-comparison`, worktree
`/home/jadams/tmp/k230-mainline-minimal-clock`, base `3e6941d7`.
Owned paths are the initrd trial controller, its narrow test file and this
note. No board, serial, kernel build, clock measurement or physical recovery
was performed by this work. Automatic restart and usable mainline root remain
**UNVERIFIED**; tasks 5d.4 and 5b.5 remain open.

## Preserve received facts when normal return times out

Previously a missing normal login after the 180-second recovery wait raised
an exception without saving the completed probe in a result. The controller
now writes a protected `mainline-initrd-diagnostic-v3` result with status
`recovery-required-normal-return-timeout`. It preserves the received probe,
including completed runtime stages, parameter readback, reboot receipt,
readiness, candidate identity and protected normal preflight. It records the
180-second deadline, reason and raw private log path, with
`normal_recovery: null` and unchanged persistent boot selection. It returns
failure and sends no further input or postflight request.

A reboot receipt is emitted before `/bin/reboot -ff`; it does not prove the
kernel reset callback ran. A verified parameter readback proves the tracing
gate only. Neither a completed probe nor a timeout establishes automatic
reset or recovered normal identities. This change handles the normal-return
deadline; serial I/O exceptions retain their existing exception path.

## Source-grounded volatile comparison

The exact candidate source is
`/nix/store/jvz4v73g8a67pqwm06v079h6s1cpqr9s-linux-mainline-k230-drm-src`,
based on Linux `72d3fcf802c45d00b300f25b848a93c3a2bd7c7e` plus the optional
restart patch. Read-only `rg -n` and `sed -n` checks confirm
[`drivers/clk/clk.c:1580–1595`](https://github.com/torvalds/linux/blob/72d3fcf802c45d00b300f25b848a93c3a2bd7c7e/drivers/clk/clk.c#L1580)
parses `clk_ignore_unused` and returns before unused-clock cleanup.
[`clk-k230.c:559–562,582–585,639–642`](https://github.com/torvalds/linux/blob/72d3fcf802c45d00b300f25b848a93c3a2bd7c7e/drivers/clk/clk-k230.c#L559)
defines SD1 card, AXI and timer gates with flags 0. The committed
[root-path audit](../mainline-display/physical-2026-10-01/mainline-root-path-audit-2026-10-02.md)
records their missing consumers and the vendor's different gate adoption.
This supports a bounded comparison of cleanup dependence. It does not
measure a gate or establish the cause of a shutdown stall.

The controller retains the existing label comparison and additionally permits
`--ignore-unused-clocks` only for minimal mode paired with
`--runtime-shutdown-trace`. Minimal without runtime tracing, root-mount and
survey reject the clock flag before preparation or serial access. Boot-time
debug remains incompatible. The new pair appends exactly one volatile
`clk_ignore_unused`; it adds no boot-time `initcall_debug` or `loglevel=8`.
Printed bootargs must match completely; duplicates, conflicting debug
arguments and a missing/extra clock flag fail validation. No permanent clock
policy, kernel, DT or boot-file content is changed.

Runtime result selection records `ignore_unused_clocks: false` for the
baseline and `true` for the comparison. Both use the same exact bundle,
passive candidate/init/primary-prompt readiness, fresh receipt, true, proc,
uptime and six runtime tracing gates, `Y` readback, single reboot command and
180-second protected normal-return wait. There are no card label reads,
root mounts, register writes, retries or shell repair in this comparison.
The flag skips global late cleanup; a different outcome cannot name one gate
or prove the last printed MMC callback is culpable. Device shutdown logging
prints entry rather than exit; later lock/PM waits can be silent.

## Host proof and remaining physical gate

At 2026-10-02 19:29 UTC:

```sh
python3 -m unittest discover -s tests -p test_mainline_drm_initrd_shell_trial.py -q
openspec validate the-board-runs-a-mainline-kernel --strict
git diff --check
```

All **96 tests** pass (20.331 seconds), retaining the previous 92 tests.
Coverage includes both baseline/comparison selectors, exact volatile args,
rejected modes/conflicts, real capped-pump readiness before either protocol,
and preservation of a complete six-stage runtime result at normal timeout.
Timeout tests verify no later serial write, login attempt, helper upload or
postflight. Strict validation and diff checks pass. Cached work-status was
run at start and launched at handoff. These are host simulations and source
reads, not physical tracing, clock or automatic-recovery proof.

After review, landing and independently verified protected normal recovery,
the sole board operator may run the comparison with fresh protected paths:

```sh
trial_stamp=$(date -u +%Y%m%dT%H%M%SZ)
python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal \
  --runtime-shutdown-trace --ignore-unused-clocks \
  --bundle /nix/store/asj7l4zj5jrjkgng4nrcx3y72p7jf7aa-k230-mainline-drm-trial-boot-files \
  --manifest "$HOME/tmp/k230-mainline-restart-board/candidate-manifest.json" \
  --normal-report "$HOME/tmp/k230-mainline-restart-board/normal-report.json" \
  --log "$HOME/tmp/k230-mainline-restart-board/runtime-clock-${trial_stamp}-uart.log" \
  --result "$HOME/tmp/k230-mainline-restart-board/runtime-clock-${trial_stamp}-result.json"
```

This command was not run by this work. Missing reception, runtime gates or
normal return must retain failure/unknown and require protected recovery.
Root owns the separate physical transcript, operator reservation and postflight.
