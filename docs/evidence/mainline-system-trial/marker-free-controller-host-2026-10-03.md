# Same-image marker-free comparison — controller host proof

2026-10-03 UTC. Coordinator worktree
`/home/jadams/tmp/k230-mainline-probe-integration`, branch
`integrate/mainline-probe-path`, implementation base
`b837f213865c200a084b6b98055bfc717b8617ad`. Owned paths: ordinary system
trial controller, focused tests, this note and mainline task progress.
Independent read-only review approved the source and all 36 focused tests.
No kernel build, transfer or board command was used for this source increment.

The preceding same-image `initramfs_async=0` comparison reached
`init-exec-exit` but no login. Its retval, final SBI return and first userspace
instruction remain unknown; see
[physical comparison](initramfs-initcall-physical-2026-10-03/README.md).
A subsequent user reset passed protected normal recovery and restored Home.

Begin-only `--without-boot-markers` requires `--wait-initramfs-in-initcall`.
It first qualifies the original exact base/SBI-only enable tokens, immutable
init/root and sole serial console, then removes **both** exact enable tokens
from volatile arguments. It retains `initramfs_async=0`, all three original
qualified controls, ordinary logging and the same staged artifacts.
In exact source `26hzn5…/init/main.c:1510` the false base gate makes all
helper sites return immediately. Appending `=0` would not clear a previously
parsed `=1`; removing only SBI-only would restore the legacy printk path.
This is runtime diagnostic suppression, not removal of kernel source.

The literal full-value U-Boot command is validated before any serial input:
strict safe characters, no expansion/quotes/semicolon/backtick/newline,
no residual flag names and length below 512 bytes. Default/previous mode
keeps its original command. Printed arguments and subsequent live cmdline
must match exactly. Five loads/five CRCs, single bootm, passive 180-second
readiness, exact normal/candidate identity and persistent-file gates remain.
Typed mode provenance is saved/restored for touch/finish; old states default
false, invalid combinations reject before UART, resume CLI reselection rejects.
No saveenv, protected profile/boot-file rewrite, console-null or loglevel change.

```sh
python3 -m unittest discover -s tests -p 'test_mainline_drm_system_trial.py'
openspec validate the-board-runs-a-mainline-kernel --strict
openspec validate --all
git diff --check
```

**36 focused tests passed**, including independent review. Seven new tests
exercise actual command transport, original-token qualification/removal,
unsafe/oversize rejection before initial input, printed mismatch before bootm,
unknown readiness with no later input, exact live cmdline, typed saved-mode
finish and CLI begin-only constraints. This is host/mock evidence, not board
or deliberate-glass proof. CI already runs this focused test command.

Actual `prepare()` against the realized matching bundle passed in both modes.
System/kernel/PID1/manifest/helper/normal and diagnostic controls are identical;
arguments differ only by removal of the two exact enabling tokens. The actual
literal command is 317 bytes. Private result:
`~/tmp/k230-mainline-marker-free-board/host-prepare.json`.
The already staged Image/initrd/DT/wrapper/bootargs and complete closure are
reused; no new build or staging is needed. Fresh protected normal baseline
was updated after this comparison's operator reset.

## Physical gate and operator command

Reserve board/UART for one attempt:

```sh
python3 tools/mainline-drm-system-trial.py begin \
  --wait-initramfs-in-initcall --without-boot-markers \
  --bundle /nix/store/brmp1qf9cz65yciazabc8yg5j39nn643-k230-mainline-drm-trial-boot-files \
  --manifest ~/tmp/k230-mainline-marker-free-board/candidate-manifest.json \
  --normal-report ~/tmp/k230-mainline-marker-free-board/normal-report.json \
  --state ~/tmp/k230-mainline-marker-free-board/ordinary-state.json \
  --log ~/tmp/k230-mainline-marker-free-board/ordinary-uart.log \
  --result ~/tmp/k230-mainline-marker-free-board/ordinary-result.json
```

No diagnostic labels are expected. A positive login/guarded ordinary-root
result would establish progress with this changed instrumentation. Another
quiet failure would remain unknown. A ready candidate still needs its own
panel capture, deliberate glass `touch --real-touch` and protected `finish`.
No production, root/glass/automatic-return or archive acceptance is claimed;
task 5b.5 stays open. Unknown readiness releases UART without guessed recovery.
