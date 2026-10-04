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

Actual existing-artifact proof for task 5m.2 will be appended after execution.
No UART/board or physical nohz-off trial was performed for this checkpoint.
Task 5m.3 still needs NEW protected normal recovery, reviewed host gate and one
reserved operator capture. Received token and linked support do not prove runtime
tick policy, hardware timer IRQs, output-call return or cause. Ordinary root/touch
and 5b.5 remain **UNVERIFIED**.
