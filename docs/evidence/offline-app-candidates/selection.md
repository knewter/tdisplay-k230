# Offline application candidate selection

This is a host-only selection note for the pinned riscv64 candidates. It does
not claim image startup, injected touch behavior, physical finger accuracy, or
final panel readability.

The closure comparison uses baseline
`/nix/store/24h4sb1msncgbasnwl3ckdlxqf9v2g6r-nixos-system-nixos-26.11.20260919.20b1ddd`.
The delta is the sum of `narSize` for realized closure paths absent from that
baseline.

| Candidate | Recorded derivation/output | Host result | Recursive closure | New-path delta |
| --- | --- | --- | ---: | ---: |
| `nano` | `ddlmrxj9qxwm2k22b7qh4qyzkx8v8y8s-nano-riscv64-unknown-linux-gnu-9.2.drv` / `r6vhwss7namz6kh9h4w2b2zx1v75hzxm-nano-riscv64-unknown-linux-gnu-9.2` | Built/realized | 51,564,232 B | **0 B** |
| `nnn` | `y6ljii8gl8x4xh5frb1ck32mmvzgwcvb-nnn-riscv64-unknown-linux-gnu-5.3.drv` / `x4lhz9qljs7159byrzjffzhaa8p2sxc0-nnn-riscv64-unknown-linux-gnu-5.3` | Built/realized | 51,692,184 B | **441,408 B** (`nnn` output) |
| `lf` | `bzkn9wjy9kx9i2b56gzc7iy11dxnz011-lf-riscv64-unknown-linux-gnu-42.drv` / `n6h8qfjwppv9y5radx5vrdl9vjb9737q-lf-riscv64-unknown-linux-gnu-42` | Output/closure recorded; the uncached Go module derivation prevented treating this as a completed supported build | 41,839,520 B | **5,788,696 B** (`lf` plus `iana-etc`) |

The provisional host recommendation is `nano` as the editor and `nnn` as the
file browser. Together they add one new realized path and 441,408 NAR bytes to
the stated baseline. `lf` is omitted because its recorded delta is much larger
and its host build evidence is incomplete; this is a provisional package
decision until the remaining candidate and image checks finish.

The candidates do not all provide the same desktop-entry shape. `nano` has no
upstream desktop entry, so the image will need a project-owned
`k230-editor.desktop` with `Terminal=true`. `nnn` provides `nnn.desktop`, and
`lf` provides `lf.desktop`; each selected entry still needs catalog discovery
and launch verification through the existing Foot bridge.

The remaining checks are package/image integration, desktop catalog launch and
return, Help and paging behavior, injected board workflow, startup observation,
and the evidence index. No board result is inferred here.

