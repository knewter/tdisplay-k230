# Same-image MemoryPrintk nohz-off controller

Source/fixture proof on 2026-10-04 UTC adds the typed
`--uart-progress-memory-printk-nohz-off` child only. It requires minimal mode and
all same-image/progress/Memory/no-stimulus/MemoryPrintk selectors; polling, point,
clock and shutdown selectors or invalid types/modes reject before preparation,
output creation or UART open. Base MemoryPrintk still rejects nohz additions
unless this exact child is selected. Arbitrary/bare/empty/alternate/duplicate
nohz/nohz_full and other argument edits fail exact reconstruction.

Actual qualification requires same-derivation realized dev/config and reviewed
MemoryPrintk source/Image/archive gates, plus built-in NO_HZ_COMMON, NO_HZ_FULL,
HIGH_RES_TIMERS, RISCV_TIMER, RISCV_SBI and HZ=250. It verifies unchanged config
and Image hashes and one linked NUL-terminated `nohz=` setup. Unset legacy
CONFIG_NO_HZ does not reject the actual supported image. Only trailing `nohz=off`
is added to qualified MemoryPrintk, giving the planned 416→425-byte literal.

The observation parser is unchanged: exact fresh received args/backend, strict
UMK framing/state rules and the narrowly qualified Readline prompt prefix.
Candidate capture remains zero-input on success/error/finally, NOT_REQUESTED
receipt, RX NOT_TESTED and 180-second passive observation. Only the independent
ordered fresh normal-return boundary and protected postflight permit helper
writes. No candidate reboot/retry, build, card/profile or source/kernel change.

Narrow proof with `TMPDIR=$HOME/tmp`:

```sh
python3 tests/test_mainline_uart_progress_memory_printk_nohz_off_controller.py
python3 tests/test_mainline_uart_progress_memory_printk_controller.py
python3 tests/test_mainline_uart_progress_memory_poll_idle_controller.py
python3 tests/test_mainline_uart_progress_memory_no_stimulus_controller.py
openspec validate the-board-runs-a-mainline-kernel --strict
```

13 new tests PASS (0.274s), 23 prior MemoryPrintk PASS, 14 polling PASS and 15
no-stimulus PASS. Strict validation/whitespace PASS. The new fixtures exercise
actual configuration/Image checks, each missing/wrong/duplicate gate, hash/setup
mismatch, exact sole transform and original transport rejection, pre-open typed
conflicts, real rolling pump/split CRLF/strict records, unknown/read-error/overflow
zero input and protected recovery separation. Full mocked transport executes the
qualifier and all five loads/CRCs/printed exact arguments; no bytes follow bootm.
The first development run exposed fixture-only argument-prefix and copied-name
errors; final fixtures correct those without changing artifact/runtime semantics.

Actual existing-artifact proof for task 5m.2 passed on the first executed run.
The [safe receipt](result.json) and [exact executed qualifier](qualification-command.py)
record UTC timestamps, controller `b99d972e`, source/config/Image/archive/manifest
identities and proof boundaries. Source peer review independently repeated all
13 focused fixtures PASS; root reviewed and repeated the affected UART pattern
143 and shell-PID1 14 tests PASS before landing the code.

```sh
TMPDIR="$HOME/tmp" python3 "$HOME/tmp/k230-mainline-uart-memory-printk-nohz-host-qualification/qualify.py" \
  --bundle /nix/store/p2kdar89q7dhwdajjy0mrhmxxzcgsalw-k230-mainline-drm-trial-boot-files \
  --dev /nix/store/24hbalyljs6gn6fzkkl24znv8a0x6jdl-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-dev \
  --normal-report "$HOME/tmp/k230-mainline-uart-memory-printk-board/normal-report.json"
```

Execution requires the existing successful frozen artifact receipt `1c59f856`,
explicit exact bundle/dev and fresh outputs in the protected directory. Python
3.14 native Zstd, `nix-store`/`nix` offline queries, `fdtget` and `sha256sum` are
host dependencies. The committed script is byte-identical to its executed private
copy and retains that protected directory/worktree contract. It reads immutable
artifacts and copies protected baseline/manifest privately; originals remain
unchanged. No implicit realization or UART is performed.

The actual selected source worker is the reviewed `30e8eb1e` variant under `0l4mgw9`;
Image SHA `c2c9663b` and config SHA `52e7470b` match previous actual MemoryPrintk
proof. Config has the required built-in gates/HZ=250 and unset legacy NO_HZ;
unique linked `nohz=` offset is 19425910. Actual archive executables/common
loader, kernel/dev, DT/chosen args, five load hashes/CRCs and manifest equal the
previous positive proof. Bundle SHA256SUMS passes. Selected bootargs/transport
are exactly baseline plus sole trailing nohz=off; five original mode transports
remain equal to frozen fcd1020f. Unchanged preparation/observation/backend AST
is compared only within its applicable function domain; the intentionally
extended transport is checked through actual original values and sole token.

Private normal report, selected helper, manifest and transport stay outside the
repository. The report is a historical host-only anchor, not a new recovery or
preflight. Registration absence is asserted in the prepared pre/post helper;
this host run does not claim a newly performed board assertion. No wrapper
readback/copy or flash is added. No initial actual-artifact failure occurred.
No UART/board or physical nohz-off trial was performed for this checkpoint.
Task 5m.3 still needs NEW protected normal recovery, reviewed host gate and one
reserved operator capture. Received token and linked support do not prove runtime
tick policy, hardware timer IRQs, output-call return or cause. Ordinary root/touch
and 5b.5 remain **UNVERIFIED**.


After NEW protected normal recovery and reviewed host gates, the sole operator
may use fresh protected log/result paths:

```sh
python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal \
  --same-image-shell-pid1 --uart-progress --uart-progress-memory \
  --uart-progress-memory-no-stimulus --uart-progress-memory-printk \
  --uart-progress-memory-printk-nohz-off \
  --bundle /nix/store/p2kdar89q7dhwdajjy0mrhmxxzcgsalw-k230-mainline-drm-trial-boot-files \
  --manifest PRIVATE_MANIFEST --normal-report PRIVATE_NORMAL \
  --log PRIVATE_LOG --result PRIVATE_RESULT
```
