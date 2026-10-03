# Root-mount marker interleave: host parser correction

Recorded `2026-10-03T03:51:10Z`. Worktree
`/home/jadams/tmp/k230-mainline-root-marker-interleave`, branch
`fix/mainline-root-marker-interleave`, base
`63bdaa90789d8c3165c041fffef776031dd71ba3`. Owned paths are
this note, `tools/mainline-drm-initrd-shell-trial.py` and its existing test
file. No board/build slot; the coordinator retains the board and UART.

The coordinator reports that the root-mount controller stopped unknown at
mount, while its private capture contains a complete fresh END nonce and RC
split by an EXT4 informational printk. The sanitized host fixture preserves
the split position, timestamp, message, RC, CR/LF and prompt shape; only the
nonce and filesystem UUID are replaced:

```text
K230_RDINIT_ROOT_END 0123456789a[    6.030241] EXT4-fs (mmcblk1p2): mounted filesystem 11111111-2222-3333-4444-555555555555 ro without journal. Quota mode: disabled.
bcdef0123456789abcdef STAGE=mount RC=0
```

This correction affects only the mount stage's parser view. It rejoins a
nonce only when the inserted line is exactly the complete mmcblk1p2 EXT4
read-only/no-journal/disabled-quota message, with bounded timestamp and
canonical UUID, between two nonempty nonce fragments whose concatenation
equals the supplied fresh 32-hex token. Complete final newline, BEGIN/END
ordering, unique markers and RC 0–255 remain required. The exact installed
kernel source's `fs/ext4/super.c:5870` formats this informational message.
The parser does not infer RC from the mount message or shell prompt.

Other kernel lines, messages, fields, stages, malformed UUIDs/timestamps,
multiple insertions, stale/echoed/duplicate/truncated markers remain unknown.
No global printk removal, protocol commands, schema, timeout or recovery path
changed. Raw session buffers/logs remain unchanged; the original failed
controller result is separate evidence and is not rewritten into a pass.

Host verification:

```sh
python3 -m unittest discover -s tests -p test_mainline_drm_initrd_shell_trial.py
git diff --cached --check
openspec validate the-board-runs-a-mainline-kernel --strict
python3 tools/work-status.py
```

All 100 controller tests passed. New coverage uses the captured sanitized
split, all 31 internal nonce split positions and returned RC 0/32/255;
rejects partial final responses, unknown/malformed/duplicate/echo/stale
messages; and proves the protocol proceeds to fresh flags, selected-path
tests and explicit unmount only after a recognized mount response. Unknown
interleave still stops without flags, cleanup, reboot or another command.
The first integration fixture omitted the next command echo's newline after
the captured prompt and failed at flags; adding that real shell boundary
made the test model the UART sequence correctly. No parser behavior was
broadened to handle that fixture error.

Strict OpenSpec validation and staged diff check passed. Cached status start
and handoff run idle with private output outside the repository. The source
correction has coordinator review; merge/push remain coordinator work.

No private capture was read or board command sent here. The coordinator may
parse the saved original response with the reviewed parser, then independently
gate fresh candidate identity, mount flags, executable paths, unmount and
protected normal recovery. Those physical checks remain **UNVERIFIED** in
this host note; ordinary init and deliberate touch task 5b.5 stay open.
Future console framing or logging changes require separate review; this
correction supplies no general method for discarding arbitrary kernel text.
