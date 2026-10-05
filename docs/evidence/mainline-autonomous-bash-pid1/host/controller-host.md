# Fixed autonomous Bash-PID1 controller preparation

This checkpoint implements group 5n.2 from base `703e91050375aa260a9b44472e605d390530d3e5` on branch `mainline-autonomous-pid1-controller`. It is host source/fixture evidence, with no UART, board operation or build. Actual artifact preparation and the native proof are separately required by 5n.3; the physical comparison remains UNVERIFIED.

The typed `--autonomous-bash-pid1` flag requires `--mode minimal --same-image-shell-pid1` and rejects competing diagnostics before preparation or UART. It generates one fresh 32-character lowercase hexadecimal nonce and only the reviewed 154-byte Bash body. For the selected p2 system, the raw arguments are 477 bytes and the single, single-quoted old-Hush `setenv bootargs` command is 503 bytes (504 including CR). Backslashes are doubled for the pinned old Hush parser. There is no generic script option. The prior literal transport and default modes remain unchanged.

Before UART, the controller qualifies the existing MemoryPrintk source, Image, actual same-derivation dev configuration and original archive. It then removes every reporter/trace/tick gate from the selected volatile policy. It inspects executable RISC-V ELF64 `/bin/sh` and `/bin/sleep`, their shared archived loader, and the defined Bash `printf_builtin`, `test_builtin` and `exec_builtin` exports. These are archive/ABI/export checks, not evidence that those programs executed on hardware.

The native gate pins receipt SHA256 `1a718d596a9c31b65651738df4128687a77f3e00cb0c0922544959dca07f42b7` from source-agent commit `21974c021f2b7c697d622028661248d9c784060d`. It checks every fixture/test hash, selected Linux source-file bytes, Hush capture facts, selected Linux recovered argv and independently reconstructed fixed vector before UART. Missing or changed native evidence fails closed. Native capture hooks do not prove the installed firmware command-handler ABI or runtime execution. The source agent owns these separate native files; this controller commit does not duplicate them.

Capture lasts at most 60 seconds, accepts only complete fresh nonce B/E records after the fresh exact received kernel arguments, Linux ttyS0 backend and `/bin/sh` milestone, and permits CRLF framing without repairing embedded CR, ANSI, echoes or interleaved lines. Missing, malformed, duplicate or reversed records retain unknown/incomplete facts. Begin, end and the primary prompt are independent observations: a record's presence does not prove its own output call returned. The end record supports earlier begin-printf success and sleep return under the fixed script; a later primary prompt supports subsequent exec/startup. Neither is RX, root or touch acceptance.

The controller sends zero candidate bytes after `bootm`, including timeout, read-error and overflow paths. It never requests candidate reboot or exit. Only an independently ordered fresh SPL/vendor-kernel/login/normal prompt permits protected normal postflight input; exact normal identities, all eight hashes, three services, absent registration marker and a fresh boot must still pass. Otherwise NEW operator recovery is required. The historical report used for host preparation is not a fresh preflight or recovery proof.

Narrow proof (2026-10-05 UTC):

```
TMPDIR="$HOME/tmp" PYTHONDONTWRITEBYTECODE=1 python3 tests/test_mainline_autonomous_bash_pid1_controller.py
```

16 tests PASS in 0.144 seconds. Fixtures exercise fixed syntax/nonce/type/conflict rejection, native receipt/fixture/source/vector corruption and missing-proof pre-UART failure, real pump split/CRLF B/E capture, stale/echo/ANSI/embedded-CR/order/duplicate/truncation failures, independent normal return, read errors/byte bounds, archived ELF export validation, and all five load/CRC checks plus exact printenv/boot transport with zero post-boot writes. Their mocked hardware/archive data is fixture evidence only.

Affected existing proofs also passed: NoHz controller 13 tests; MemoryPrintk controller 23 tests; same-image shell PID1 14 tests; minimal controller 100 tests. Strict mainline validation and whitespace checks passed. No physical result is claimed; 5n.4 and ordinary root/touch task 5b.5 remain open.
