# Initrd debug prompt followed by boot output: host correction

Evidence class: host regression tests against a coordinator-provided safe
physical prompt boundary. No board, serial, build or live-session modification.
This corrected controller's physical diagnostic and automatic recovery remain
**UNVERIFIED**; task 5b.5 stays open.

Worktree `/home/jadams/tmp/k230-mainline-initrd-debug-readiness`, branch
`fix/mainline-initrd-debug-readiness`, base
`3f07e8efa2f3f166485d65df8e27edebb485fb39`. Sparse checkout contains the owned
controller/tests/note and their read-only dependencies. No board/build slot.
Cached `python3 tools/work-status.py` start/handoff both returned zero at idle
priority; the coordinator owns physical evidence and protected recovery.

The coordinator observed the exact candidate Linux/systemd 261.2 followed by
the primary `sh-5.3# ` prompt. Asynchronous systemd status then appeared directly
after the prompt on the same line and continued for twelve lines. The earlier
readiness check required the prompt at the current buffer tail, so it sent no
IDBG receipt/diagnostic commands and timed out. This is a controller readiness
limitation; it does not demonstrate unit/worker state or a new kernel cause.

Only `wait_ready()` changes. It now records a primary prompt starting at a
fresh line, optionally preceded by bash's bracketed-paste enable, strictly
after the fresh 7.3.0-rc5 banner and subsequent exact systemd 261.2 marker.
Later boot status may share that line or follow it. It does not strip kernel
output or infer that a command completed. The exact tail/quiet command-frame
parser, fresh receipt, candidate/PID1/shell/TTY ownership, initrd/no-sysroot/
pending-root-job gates, private snapshots and renewed recovery guards remain
unchanged. A prompt is only the input-timing gate.

The regression fixture uses only the supplied safe boundary: bracketed-paste
enable, `sh-5.3# `, colored systemd status and an interleaved filesystem-target
printk. No raw private UART log or secret-bearing preflight was copied.
Whole and split real-session pumping accept that boundary. Negative cases
reject prompts before the candidate banner or manager marker, vendor/wrong
kernel banners, a 261.20 manager marker, echoed/continuation/nonprimary prompts
and incomplete prompt text. Existing fail-closed protocol/guard tests still pass.

Commands and results:

```sh
python3 -m unittest discover -s tests -p test_mainline_drm_initrd_debug_trial.py -v
openspec validate the-board-runs-a-mainline-kernel --strict
git diff --cached --check
```

All 24 narrow tests pass. Strict validation and staged whitespace checks pass.
Independent read-only peer review reproduced the 24 passes and approved the
final source, including rejection of prompt-like text on the manager line.
The operator invocation remains the one in the
[controller host note](initrd-debug-controller-host-2026-10-03.md), with fresh
private output paths and the successful matching blkid prerequisite. Review/
merge/push, protected preflight and a separately recorded corrected physical
trial remain before claiming diagnostic readiness or automatic return.
