# Offline application candidate selection

This records the host closure comparison for the pinned riscv64 candidates.
Board results are linked separately below.

The closure comparison uses baseline
`/nix/store/24h4sb1msncgbasnwl3ckdlxqf9v2g6r-nixos-system-nixos-26.11.20260919.20b1ddd`.
The delta is the sum of `narSize` for realized closure paths absent from that
baseline.

| Candidate | Recorded derivation/output | Host result | Recursive closure | New-path delta |
| --- | --- | --- | ---: | ---: |
| `nano` | `ddlmrxj9qxwm2k22b7qh4qyzkx8v8y8s-nano-riscv64-unknown-linux-gnu-9.2.drv` / `r6vhwss7namz6kh9h4w2b2zx1v75hzxm-nano-riscv64-unknown-linux-gnu-9.2` | Built/realized | 51,564,232 B | **0 B** |
| `nnn` | `y6ljii8gl8x4xh5frb1ck32mmvzgwcvb-nnn-riscv64-unknown-linux-gnu-5.3.drv` / `x4lhz9qljs7159byrzjffzhaa8p2sxc0-nnn-riscv64-unknown-linux-gnu-5.3` | Built/realized | 51,692,184 B | **441,408 B** (`nnn` output) |
| `lf` | `bzkn9wjy9kx9i2b56gzc7iy11dxnz011-lf-riscv64-unknown-linux-gnu-42.drv` / `n6h8qfjwppv9y5radx5vrdl9vjb9737q-lf-riscv64-unknown-linux-gnu-42` | Built/realized, including the initially uncached Go module | 41,839,520 B | **5,788,696 B** (`lf` plus `iana-etc`) |

The selected image set is `nano` as the editor and `nnn` as the
file browser. Together they add one new realized path and 441,408 NAR bytes to
the stated baseline. `lf` is omitted because its recorded delta is much larger;
all three candidates cross-build successfully. Its board startup/RSS sample
remains outstanding, so candidate evaluation task 1.2 stays open.

The candidates do not all provide the same desktop-entry shape. `nano` has no
upstream desktop entry, so the image supplies a project-owned
`k230-editor.desktop` with `Terminal=true`. `nnn` provides `nnn.desktop`, and
`lf` provides `lf.desktop`; both selected entries are discovered and launched
through the existing Foot bridge in the final-image trial.

Final-image boot, desktop discovery and injected Help/app evidence are recorded
separately in [the image trial](../offline-wifi-image/README.md). No physical-finger
or final-glass claim is inferred from those injected checks.

