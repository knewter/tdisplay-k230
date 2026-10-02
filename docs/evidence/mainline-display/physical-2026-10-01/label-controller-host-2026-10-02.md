# Bounded label discriminator: host proof, 2026-10-02

This implements the next source-only discriminator ranked in
[the root-path audit](mainline-root-path-audit-2026-10-02.md), within open task
5b.5. Worktree `/home/jadams/tmp/k230-mainline-root-path`, branch
`audit/mainline-root-path`, base `4f20383167ede1fd4fd0bc8997ae8f7df5ec3e01`.
Owned paths are `tools/mainline-drm-initrd-shell-trial.py`, its named test file,
and this note. No board, serial device, staging operation, reboot, Nix build,
or build slot was used. This is not a clock-driver fix or permanent boot policy.

`--mode label` retains receipt, `/bin/true`, `/proc` directory/mount, and
uptime prerequisites. Only after those succeed does it send separately
bracketed `/dev` directory setup, devtmpfs setup, and builtin
`test -b /dev/mmcblk1p2`. The devtmpfs stage uses builtin reads of
`/proc/mounts` to avoid remounting an existing devtmpfs; it does not print that
file. Each setup's returned RC gates the next command. A failed setup or absent
node stops before the label child and before reboot, with recovery required.

The one label child is exactly `/bin/e2label /dev/mmcblk1p2`, without a second
argument. Its stdout is captured only in a shell variable and its stderr is
discarded. Fixed fresh-token begin/end markers publish only RC and an exact
`NIXOS_SD` match boolean. No raw label, cmdline, interrupts, or unrelated
partition survey is emitted by this mode. Command receipt supplies volatile
`PATH=/bin:/sbin`; all external commands use absolute `/bin` names. The original
gf3 initrd's `/bin` resolves to
`/nix/store/fdxwq7dnxazi7g8bhkv1k8ra0qv3hn7d-initrd-bin-env/bin`, with `/sbin`
its sibling; its e2label resolves into
`8mzskyv8clj8a83y8xkgpaf5x9pmgj09-e2fsprogs-riscv64-unknown-linux-gnu-1.47.4-bin`.
The exact archive inspection and other utility roots are recorded in the
linked audit. Utilities in a newly selected bundle must be reviewed before
physical use; this note does not claim their execution on the board.

Completed label results use `k230-initrd-label-v1`; failed earlier prerequisites
use `k230-initrd-label-prerequisite-failure-v1`. A missing protocol marker in
label mode records `mainline-initrd-label-unknown-v1` with status
`recovery-required-unknown-no-reboot-requested`. No retry, reboot, exit or Ctrl-C
is sent after that unknown boundary. Setup and minimal stages retain the
30-second default marker deadline; the label child has a fixed 60-second
deadline. At most eight fresh-token builtin receipt attempts remain allowed,
each bounded to one second. A controller timeout stops observation, not a
possibly blocked child or kernel request.

When the label's final marker is complete, a match, nonmatch, or nonzero RC may
follow the existing `/bin/reboot -ff` recovery path because the proc/uptime and
shell acknowledgements have succeeded. The existing five-second reboot-marker
wait and 180-second normal-login bound remain. A chroot refusal, absent normal
login or failed protected postflight remains failed/pending recovery. A returned
nonmatch or nonzero label RC never becomes a diagnostic pass merely because
normal recovery succeeds. Recovery prerequisites and the reserved operator's
physical fallback remain necessary.

`--ignore-unused-clocks` is accepted only with `--mode label`; other modes reject
it before host preparation or serial access. It appends exactly
`clk_ignore_unused` to the otherwise identical diagnostic arguments via volatile
U-Boot `setenv`, with no `saveenv` or artifact mutation. An existing clock token
is rejected when requesting this addition. The selected system's sole `init=`
and `rdinit=/bin/sh` checks remain, and the full printed U-Boot assignment must
match, including the clock token. Label results record the flag explicitly.
Minimal/survey defaults, commands and existing schemas remain unchanged.

## Host verification

On 2026-10-02, the following commands passed in the worktree above (UTC
observation `2026-10-02T16:16:43Z`):

```sh
python3 -m unittest discover -s tests -p test_mainline_drm_initrd_shell_trial.py
python3 -m py_compile tools/mainline-drm-initrd-shell-trial.py tests/test_mainline_drm_initrd_shell_trial.py
openspec validate the-board-runs-a-mainline-kernel --strict
git diff --check
```

All 48 tests pass: the previous 36 plus 12 label tests. They cover command
ordering, prerequisite/setup/node failures, match/nonmatch/nonzero RC,
stale/echoed/duplicate/truncated/reversed markers, no child retry or recovery
input after missing markers, shell syntax and absolute read-only utility use,
and clock selection/identity checks. An outer-controller host fixture verifies
that a label timeout writes the distinct unknown/recovery-required result,
closes the fake session, and never enters normal-login recovery. Its lock and
files are confined to a temporary host directory; it uses no real serial
session or board lock. Existing candidate-selection tests continue to prove
fail-closed manifest/artifact/range/protected-normal checks before serial.

## Remaining operator gate

UNVERIFIED: no label read, clock comparison, usable mainline root, restart,
panel or deliberate touch proof was obtained. Task 5b.5 remains open. Root
must first review a matching restart bundle and its exact manifest, verify the
initrd utilities, and establish physical automatic recovery; reserve the
board and retain protected normal preflight/postflight and physical fallback.
The existing historical bundle remains the CLI default, but is not implied
to have automatic recovery merely because this controller now supports label
mode.

These are future command templates, not executed commands:

```sh
python3 tools/mainline-drm-initrd-shell-trial.py \
  --bundle /nix/store/EXACT_REVIEWED_RESTART_BUNDLE \
  --manifest /path/to/MATCHING_MANIFEST.json \
  --normal-report /path/to/FRESH_STRUCTURED_PROTECTED_NORMAL.json \
  --mode label

# Only if the first direct label read fails or times out, after recovery:
python3 tools/mainline-drm-initrd-shell-trial.py \
  --bundle /nix/store/EXACT_REVIEWED_RESTART_BUNDLE \
  --manifest /path/to/MATCHING_MANIFEST.json \
  --normal-report /path/to/FRESH_STRUCTURED_PROTECTED_NORMAL.json \
  --mode label --ignore-unused-clocks
```

Replace placeholders with reviewed artifacts; keep the same candidate payload
and all other arguments across the pair, using a fresh protected normal report
for each recovered boot. RC 0 plus a match would prove one direct superblock
read at that instant. A nonmatch would distinguish root identity, while a
nonzero RC or timeout would locate a failed read without identifying its cause.
A clock-assisted improvement would support an unused-clock dependency but
would not identify a gate or prove the driver/root path. No improvement would
not exclude other clock or driver issues. No mount, activation or login is
performed by label mode. Review, merge, push and physical work remain with the
coordinator.
