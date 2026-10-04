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

Fixture evidence is separate from actual archive/artifact preparation.
Actual group 5j.2 host preparation passed on controller `c62ad389` using
`TMPDIR=$HOME/tmp python3 "$HOME/tmp/k230-mainline-uart-memory-no-stimulus-host-qualification/qualify.py"`.
The [safe receipt](result.json) preserves command/time/hash identities; the
[exact executed qualifier](qualification-command.py) preserves fail-closed checks.
Its private expected-root-revision.txt contained the reviewed original full build
revision `7af8f7b8b5849c75df61d39ee772c2cc8f38542c`. The actual build receipt
returned zero and both selected bundle and matching dev output already existed.
No implicit build or UART action occurred.

The qualifier ran actual `prepare_trial` and
`prepare_uart_progress(..., uart_progress_memory=True)`, accepted the same
protected manifest, and verified exact equality with previous Memory source,
Image, linked summary/gate, config, archive, system, DT and arguments. The
selected policy adds zero kernel tokens and retains the exact 381-byte literal
transport. Preparation functions/constants are AST-identical to both the frozen
build controller and reviewed 5j base `136dbf91`. The receipt's legacy
`prior_literal_transport_bytes=353` is the progress-only parent comparison;
the one-stimulus Memory command and zero-stimulus command are both 381 bytes.
The immutable selected kernel/dev derive from the same exact kernel derivation:

- Kernel: `/nix/store/zk5rbsrgqgp40bk1314mj0i50qhn260m-linux-riscv64-unknown-linux-gnu-7.3.0-rc5`.
- Dev: `/nix/store/1pvqbm4r3gqcvsabgkz5wvrpxfbk5k1v-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-dev`.
- Source: `/nix/store/f7xg031sjb9dy3bswm5s3qjr9xwx1g02-linux-mainline-k230-uart-progress-memory-src`,
  worker SHA256 `307d7c0588499dd32826c1d05476e0bf6d46ca0c8939d42e0b4f7180545b98dc`.

Actual wrapped initrd inspection verified archived Bash, original systemd and
common dynamic loader; Image byte identity and compiled unique summary/setup
were verified separately from `.config`. The historical protected normal report
and existing wrapper CRC anchored this host-only preparation; the previous
verified board readback is not a new host wrapper readback or current preflight.
Registration absence is asserted by the future pre/post helper, not performed
on hardware by this qualifier. Python 3.14 native Zstd supports the actual archive
inspection. All raw/prepared baseline material remains in a protected private
directory. Physical zero-stimulus comparison and new protected recovery remain
UNVERIFIED.
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
