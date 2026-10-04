# Memory controller with no candidate stimulus

This host-only change implements group 5j.1. The optional typed
`--uart-progress-memory-no-stimulus` requires minimal mode and all of
`--same-image-shell-pid1 --uart-progress --uart-progress-memory`. Existing
Memory source/config/Image/initrd qualification, boot arguments, five protected
loads/CRCs, and literal U-Boot transport are unchanged. No kernel argument is
added by the new selector. Other modes retain their previous behavior.

After `bootm`, this policy sends zero candidate bytes: no receipt, carriage
return, interrupt, command, retry, guard or reboot. It records receipt status
`NOT_REQUESTED`, zero stimulus attempts and RX `NOT_TESTED`. Fresh Bash
readiness is a historical observation; it cannot authorize input. The capture
remains passive for at most 180 seconds, including missing/malformed output,
read errors and unknown completion. Strict summary validity, worker completion,
completion-wait timeout, readiness and protected recovery remain independent.
A valid complete summary can qualify this diagnostic without a receipt only
when this explicit policy is selected; it proves neither RX delivery nor usable
root/touch acceptance. Missing output does not identify a worker, firmware,
scheduler or hardware fault.

The only later host writes permitted are protected normal postflight helpers
following ordered fresh SPL, exact normal 6.6.36 banner, login and normal prompt.
Candidate normal-looking text cannot authorize them. Exact normal identities,
fresh boot ID, eight protected hashes, three services and registration-marker
absence still require independent guarded verification. Otherwise operator
recovery remains required. There is no candidate reboot path in this mode.

Host fixture proof on 2026-10-04 UTC (Python 3.14, `TMPDIR=$HOME/tmp`):

- `python3 tests/test_mainline_uart_progress_memory_no_stimulus_controller.py`:
  15 tests passed. Real `PrivateSession.pump` and write spies cover split/same-batch
  readiness and summary, CRLF, stale/echo/duplicate/truncated/interleaved/embedded
  CR output, absent/wrong/duplicate arguments, no prompt, read error, overflow,
  timeout, typed pre-open rejection and guarded independent normal return. The
  full mocked boot protocol checks five loads/CRCs, exact identical default and
  no-stimulus boot commands, and zero candidate writes after boot.
- `python3 -m unittest discover -s tests -p 'test_mainline_uart_progress*controller.py'`:
  93 tests passed (15 new plus 78 previous progress-controller tests).
- Existing minimal, Bash-PID1 and ordinary controllers: 100, 14 and 36 tests
  passed respectively (243 total across these commands).
- Independent read-only source review by `mainline_boot_path`: PASS; the reviewer
  repeated all 15 focused tests and checked unchanged transport and no-input
  boundaries.

Fixture evidence is separate from actual archive/artifact preparation. The
existing-artifact proof for 5j.2 will be appended after actual host qualification;
physical zero-stimulus comparison and new protected recovery remain UNVERIFIED.
The preceding Memory trial still needs its newly requested operator reset.
Task 5b.5 remains open.

After protected normal recovery, the sole board operator may run the reviewed
controller with fresh private output paths and matching baseline/manifest:

```sh
python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal \
  --same-image-shell-pid1 --uart-progress --uart-progress-memory \
  --uart-progress-memory-no-stimulus \
  --bundle /nix/store/lznjjfx1kzm8mp2j0r06c87h2vdymkhd-k230-mainline-drm-trial-boot-files \
  --manifest "$HOME/tmp/k230-mainline-uart-memory-no-stimulus-board/candidate-manifest.json" \
  --normal-report "$HOME/tmp/k230-mainline-uart-memory-no-stimulus-board/normal-report.json" \
  --log "$HOME/tmp/k230-mainline-uart-memory-no-stimulus-board/trial.private.log" \
  --result "$HOME/tmp/k230-mainline-uart-memory-no-stimulus-board/result.private.json"
```

The normal report for this physical command must follow the new verified reset;
a historical host-qualification report is not a live preflight or recovery proof.
