# MemoryPrintk Bash prompt readiness correction

Host source/fixture proof on 2026-10-04 UTC corrects only MemoryPrintk Bash
primary-prompt detection. The completed physical capture under root
`877bec0e` contains the exact Readline bracketed-paste enable sequence
`ESC[?2004h` immediately before `sh-5.3# ` at the end of the log. The original
controller required the prompt at the beginning of its line and consequently
reported prompt/readiness false. Its original physical result is unchanged.

The new-mode prompt regex accepts only the optional exact observed sequence
before the anchored Bash 5.3 primary prompt, after fresh candidate/init milestones.
It retains exact received arguments and registered Linux backend readiness
gates, and the existing permitted suffix rules. Other ANSI sequences, repeated
prefixes, echoes, truncated prompts and embedded CR do not qualify. No ANSI
stripping or raw kernel-record repair occurs. Raw args/backend/summary parsing,
selected artifacts, kernel/source qualification, transport, zero candidate input
and independent protected normal recovery are unchanged. Older selectors retain
their original prompt detection.

```sh
TMPDIR="$HOME/tmp" python3 tests/test_mainline_uart_progress_memory_printk_controller.py
TMPDIR="$HOME/tmp" python3 tests/test_mainline_uart_progress_memory_no_stimulus_controller.py
openspec validate the-board-runs-a-mainline-kernel --strict
```

Results: 23 focused tests PASS (0.190s); 15 prior passive-controller tests PASS
(0.124s); strict validation and whitespace checks PASS. Added real-pump fixtures
cover the exact observed prefix at log end, prefix/prompt split across reads,
CRLF and a subsequent strict summary, invalid ANSI/embedded CR/echo, and explicit
proof that accepting the shell prefix never sanitizes raw args/backend/UMK lines.
Every capture fixture retains zero candidate writes.

A separate [host replay receipt](result.json) and
[executed replay command](replay-command.py) record reinterpretation of the saved
private capture with the corrected parser:

```sh
TMPDIR="$HOME/tmp" python3 docs/evidence/mainline-uart-progress-memory-printk/readiness-host/replay-command.py \
  --log "$HOME/tmp/k230-mainline-uart-memory-printk-board/trial.private.log" \
  --original-result "$HOME/tmp/k230-mainline-uart-memory-printk-board/result.private.json" \
  --output FRESH_HOST_REPLAY_RESULT
```

Replay uses the real `PrivateSession.pump` with a fixture serial read interface,
8192-byte chunks and an accelerated fake monotonic clock. It does not reproduce
original UART arrival times or the measured 180.101910858-second physical window.
It reads raw log bytes privately and emits only allowlisted fixed facts/hashes.
The original physical result and log were not modified; no UART was opened.

The replay observes primary prompt/readiness true while exact received args and
backend remain matched. Zero attempts, NOT_REQUESTED receipt, RX NOT_TESTED,
no UMK summary, no protocol errors and no natural normal return are unchanged.
This is a host-only parser reinterpretation, not another physical trial or new
worker/timer/output/return evidence. The absence of a summary remains unknown.
Protected normal recovery belongs to the sole operator; this replay performs
none. Ordinary root/touch and task 5b.5 remain **UNVERIFIED**.
