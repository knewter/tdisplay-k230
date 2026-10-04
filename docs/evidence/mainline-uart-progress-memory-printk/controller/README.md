# MemoryPrintk controller preparation

This is host source/fixture evidence for group 5l.4, whose actual matching-bundle
qualification remains **UNVERIFIED**. The typed
`--uart-progress-memory-printk` requires minimal mode and all same-image shell,
progress, Memory and no-stimulus selectors. It rejects polling, other diagnostic
selectors and non-boolean/missing dependencies before UART/log creation. Older
modes and their default transports are retained.

The source qualifier pins independently reviewed, actually realized worker
SHA256 `30e8eb1ee365d62665c9d3ffd674e973736f3d04405d53f0f5dc12c3ee23f5f2`
in `/nix/store/0l4mgw9hr1j7pj247jsrxjd478fnlfy8-linux-mainline-k230-uart-progress-memory-printk-src`.
It requires the selected kernel's same-derivation realized dev/config, built-in
PRINTK/PRINTK_TIME/SERIAL_8250_CONSOLE/SERIAL_8250_DW and disabled PRINTK_CALLER.
The selected linked Image must contain the unique new setup and exact KERN_INFO
format with leading newline; an old Memory source/Image cannot qualify. The
new gate is the sole addition to the base Memory transform for the selected
matching system/init. No nohlt, early console or logging-format override is added.
Actual linked new artifacts are not yet available; these gates have only been
exercised by fixtures in this controller checkpoint.

The source makes one ordinary `pr_info("\nK230_UMK1 ...\n")` call. Exact
printk.c prefix rendering produces a timestamped blank line after any existing
Bash prompt, followed by a clean timestamped summary. The parser ignores that
blank line and accepts only the complete UMK line, with canonical `%5lu.%06lu`
six-decimal timestamp and one separating space. CALLER is disabled because no
caller prefix is accepted. No prompt stripping, arbitrary prefix repair or
embedded-CR removal occurs. CRLF pairs alone are normalized.

New-mode parsing starts after the fresh raw 7.3.0-rc5 banner. Exact received
arguments precede a trusted summary. It additionally requires unique ordered
registration of UART0 at `91400000.serial`, ttyS0/MMIO32 address
`0x0000000091400000`, positive bounded IRQ/base-baud fields, then
`printk: console [ttyS0] enabled`. Partial, malformed, reordered or duplicated
backend markers cannot qualify the summary; stale/pre-banner/echoed markers
are not trusted. Backend parsing uses complete LF-delimited lines and retains
lone CR bytes. Old UMP/UP/UPB/UPP namespaces invalidate the selected channel.

One coherent summary, its validity, worker completion, completion timeout,
readiness and backend facts remain separate. A valid record establishes progress
through snapshot/formatting to changed Linux output; it does not prove the printk
call returned, identify prior DBCN failure or establish ordinary root. Missing
output leaves worker/observer/timer/scheduler/printk/UART unknown.

All candidate capture paths remain passive: zero receipt/input attempts,
NOT_REQUESTED receipt, RX NOT_TESTED, no retry, command, proc/identity probe,
interrupt or candidate reboot, with a 180-second bound. Later helper input is
allowed only after the independent ordered fresh SPL→normal6.6.36→login→prompt
boundary, followed by protected normal identities/distinct boot/eight hashes/
three services/registration absence. A summary or candidate normal-looking
prompt cannot authorize input. Operator recovery remains distinct from natural
normal return. Ordinary `/init`, usable root/touch and 5b.5 remain open.

Proof on 2026-10-04 UTC, Python 3.14, `TMPDIR=$HOME/tmp`:

- `python3 tests/test_mainline_uart_progress_memory_printk_controller.py`:
  20 corrected focused tests PASS. Fixtures execute strict state/prefix/backend
  parsers, real `PrivateSession.pump`, actual config/Image/source-query helpers
  and mocked full five-load/CRC/printed-argument boot transport. They cover
  prefixed blank separator rendering, split/CRLF records, bare-CR corruption,
  old/mixed namespaces, duplicates/truncation/echo/interleaving, stale/wrong args,
  integer bounds, unavailable config, enabled CALLER, old source/Image and typed
  rejection; all candidate writes stay zero, including read error/overflow/timeout.
- Previous progress-controller regressions passed in a 126-test discovery run
  (107 prior plus the then-19 new fixtures). After root's confined new-mode LF/
  wrong-channel correction, all 20 focused tests were rerun and root independently
  repeated them. No old-mode parsing was changed by that correction.
- Existing minimal, Bash-PID1 and ordinary controller suites: 100, 14 and 36 PASS.
- Root independently reviewed the corrected controller and tests: PASS.
- Source peer review: corrected 10 actual-C native tests independently PASS;
  selected observer performs one ordinary print call, no final explicit DBCN or
  fallback, and inherited worker/atomic/completion behavior stays unchanged.

No full build, UART, board action or actual new-bundle preparation occurred in
this controller task. Root owns source/object/full-build gates and the subsequent
actual host qualifier and sole physical operation. The matching positive host
receipt must be committed before 5l.4 is ticked and before a physical trial.

After every gate passes and protected normal is verified, the operator may use
fresh protected output paths:

```sh
python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal \
  --same-image-shell-pid1 --uart-progress --uart-progress-memory \
  --uart-progress-memory-no-stimulus --uart-progress-memory-printk \
  --bundle MATCHING_NEW_BUNDLE --manifest PRIVATE_MANIFEST \
  --normal-report PRIVATE_NORMAL --log PRIVATE_LOG --result PRIVATE_RESULT
```
