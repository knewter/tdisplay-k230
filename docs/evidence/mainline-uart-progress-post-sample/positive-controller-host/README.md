# Actual PostSample controller host qualification

Actual matching artifact preparation passed on 2026-10-04 from
`03:35:08.275473Z` to `03:35:10.201242Z`. This closes task 5h.4's positive host
preparation gate. It does not establish any new board check or physical marker,
receipt, recovery, ordinary root or touch result; those remain **UNVERIFIED**.
No UART access, board command or implicit build was performed by this qualifier.

Worktree `/home/jadams/tmp/k230-mainline-uart-progress-post-sample-controller`,
branch `mainline-uart-progress-post-sample-controller`, base `9248ffa4`, controller
`ea31b762477bebbcdcc1e048447fb90870541f91`. Owned for this handoff: this evidence
directory and only task 5h.4's completion note/checkbox. Root owns the matching
build, staging, board/UART and independent recovery. Cached start/handoff status
scans are host-only; no build-slot or board reservation was taken.

The actual full build receipt returned zero for frozen root revision
`75cc49df12972235be411e6eca739935ce75614d`. The qualifier first required that exact
revision and compared ASTs of its preparation functions and relevant constants
with the frozen root source. It then used the protected normal report and exact
matching manifest to run actual `prepare_trial` followed by
`prepare_uart_progress(..., uart_progress_breadcrumbs=True,
uart_progress_post_sample=True)`.

The realized identities are:

| Artifact | Store identity |
| --- | --- |
| Bundle | `/nix/store/fjmxf6kn1yq0xk9v783amgymybhcrwkb-k230-mainline-drm-trial-boot-files` |
| System | `/nix/store/5ha786snzrp5c8gkfamlzrmdw1anyj6m-nixos-system-nixos-26.11.20260919.20b1ddd` |
| Kernel | `/nix/store/xhglqk1w6xvvr1f3nbbazgf2mm9fz225-linux-riscv64-unknown-linux-gnu-7.3.0-rc5` |
| Matching dev | `/nix/store/js4by9macr407x7zp8hraykh23bb9an7-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-dev` |
| Source | `/nix/store/wnvbxaiqgbhhajsajy5mlpn36zf8alga-linux-mainline-k230-uart-progress-post-sample-src` |

Read-only queries tied the actual kernel and dev/config to the same derivation.
All six required built-in config options were present exactly once. The full
config hash is `52e7470b108ad094dbdf88b94e3e8838564edbda9e7a015b4279012e6765c9f1`.
Its derivation's immutable source had the reviewed worker SHA256
`aee68aaec5c5c0e2b23919901eb99189265fd2b4787a0e50bc11159afd81ef9b`.
The linked Image hash is
`2ef34d863f0bb2dee8886d6a2b76fa05c52354e21fe055a2ff56febb26404557`.
All four complete NUL-terminated fixed marker strings and both setup keys were
unique in that Image. Their offsets, full artifact hashes/CRCs and actual archive
executable/loader proofs are in [result.json](result.json).

Actual preparation inspected the selected compressed archive and U-Boot wrapper,
RISC-V Bash and original systemd ELF executables, shared archived ELF interpreter,
manifest hashes and five load ranges. The protected wrapper hash/size came from
the existing guarded normal report and its fixed controller CRC. There was no new
card readback. Registration absence is an assertion included in the pre/post
helper, not a protected board check performed during this host invocation.

The exact qualified volatile policy adds only
`k230.uart_progress_post_sample=1` after the inherited Breadcrumbs policy for this
selected system. The full literal U-Boot command is 419 bytes; the corresponding
prior command is 386 bytes. There is no variable expansion, appended duplicate
init/control, saveenv, card/profile selection change or new hardware DT setting.
The controller still requires exact freshly received kernel arguments before its
one builtin stimulus and never issues a candidate reboot. Host arrival labels
are not measurement timestamps. Fixed record presence does not establish its own
firmware return, and missing output cannot locate a stop.

Executed host command:

```sh
TMPDIR=$HOME/tmp python3 "$HOME/tmp/k230-mainline-uart-post-sample-host-qualification/qualify.py"
```

[qualification-command.py](qualification-command.py) preserves the exact executed
runner, SHA256
`5b8f5d1088bb13252a7dc420a86de9c2fe74eec45de1ac713bf5db78001c6beb`.
It requires fresh outputs and the protected expected-revision file. Reexecution
belongs in a new protected directory under `~/tmp`, never this public evidence
directory. Its baseline/prepared-state/transport files remain private.

The private matching manifest is available to the root operator at
`~/tmp/k230-mainline-uart-post-sample-host-qualification/candidate-manifest.json`,
SHA256 `da99e68ed9bf00f2ed689ac447b9b4eaba0876e5c9b1590e5192a75bc5d1c2ee`.
Root must review/copy it into the new private trial directory, use fresh log/result
paths, and repeat actual protected normal preflight/load CRC guards. After all
matching object/artifact/controller gates and independently verified normal
recovery, the root operator command is:

```sh
python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal \
  --same-image-shell-pid1 --uart-progress --uart-progress-breadcrumbs \
  --uart-progress-post-sample \
  --bundle /nix/store/fjmxf6kn1yq0xk9v783amgymybhcrwkb-k230-mainline-drm-trial-boot-files \
  --manifest PRIVATE_MANIFEST --normal-report PRIVATE_NORMAL \
  --log PRIVATE_FRESH_LOG --result PRIVATE_FRESH_RESULT
```

Physical tasks 5h.5–6 and ordinary root/touch task 5b.5 remain open. This receipt
proves actual host qualification, not deployment, stage/flash or hardware behavior.
