# Picker row repaint: first physical pair

The board received **software-injected input events**, not a real finger. Both runs used the same active appearance generation, eight backgrounds, compositor PID/start identity, current system and normal launcher wrapper. Each restarted the UI/helper, waited for Settings and a twelve-second picker warmup, then ran six theme and six background swipes: 240 pixels over 200 ms followed by 1.2 seconds at rest. Both 60-second bounded trace pairs have zero dropped events and no exporter warnings. Native PNGs were captured after timing, at grim scale 0.6. These captures show the picker and resolved previews; they are not camera recordings.

Baseline executable: `/nix/store/8cikjd811d7b7hsdhn7nnb3lnipf3vwp-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust` (coherent runtime source `b57ba41ccf6755c54039fc85b0a54145001b186a`). Candidate source: `42e22d4353e35d9c4f6367ed5b159c80b489ec5d`; exact coherent-configuration output `/nix/store/2mprr7lqh4hznwz9z1zmv7vamf5nbnna-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0`. Its direct runtime references exactly match the baseline. The generic standalone cross-package output was deliberately excluded from this comparison because it links different Cairo/Pango/librsvg outputs.

| Measured result | Baseline | Candidate |
| --- | ---: | ---: |
| Presented frames in bounded recording | 105 | 127 |
| Active presentation gap median | 134.121 ms | 76.641 ms |
| Active presentation gap p95 | 210.765 ms | 153.287 ms |
| Active presentation gap p99 | 229.923 ms | 191.602 ms |
| Theme phase overlay draw median thread CPU | 96.443 ms | 78.363 ms |
| Background phase overlay draw median thread CPU | 62.014 ms | 34.015 ms |
| Theme phase full scene rebuilds | 50 | 12 |
| Background phase full scene rebuilds | 43 | 4 |

The row repaint mechanism reduced complete scene rebuilding and improved this pair's cadence. **Jank is not resolved.** This is one pair, not a statistical confidence claim or a matched-pixel microbenchmark. The input programs match, but the existing step-integrated momentum behaves differently with the changed frame cadence: the final selected preview is Lupine in the baseline and matte-black in the candidate. Active appearance remains identical. The continuous elapsed-time motion correction belongs to task group 18 and was not included in this candidate. Presentation summaries cover the entire bounded recording including picker opening; per-row CPU summaries use only each swipe and its following 1.2-second rest. Overlapping span medians are not additive. Background decode/preparation may already be in flight; the new policy stops new speculative admission during motion, rather than cancelling an existing worker.

## Sources and replay

The executed [capture script](capture.py), its [input helper](baseline.py), raw bounded numeric traces, exporter summaries and [comparison](comparison.json) are frozen here. SHA256 values are in [sha256.json](sha256.json). Traces identify CLOCK_MONOTONIC timestamps; they contain no external collector or cross-host timestamp rebasing. The helper's unused standalone collector mode remains in the frozen source; this pair invoked only its verified virtual-device and native-touch functions.

Coordinator only: stage these scripts on the reserved board as `pair-capture.py` and `baseline.py`, and stage the reviewed Goodix descriptor whose device name is `K230 injected touchscreen`. The script refuses a physical input device. Use the board Python interpreter and installed normal service wrapper. `PROTECTED_UPLOAD_URL` must come from the local protected transfer endpoint, outside Git; it is used only after restoration to collect fixed allowlisted files.

```sh
BOARD_PYTHON=/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3
systemd-run --quiet --wait --collect --unit=k230-theme-row-base \
  --property=RuntimeMaxSec=150s \
  --setenv=PATH=/run/current-system/sw/bin:/run/current-system/sw/sbin \
  "$BOARD_PYTHON" /root/tmp/k230-theme-row-trial/pair-capture.py \
  base "$PROTECTED_UPLOAD_URL" \
  /nix/store/8cikjd811d7b7hsdhn7nnb3lnipf3vwp-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust
# Repeat with unit/label candidate and the exact 2mpr candidate ELF above.
python3 tools/runtime-trace-export.py \
  docs/evidence/theme-picker/row-repaint/pair/candidate-rust.json \
  docs/evidence/theme-picker/row-repaint/pair/candidate-helper.json \
  --timeline NEW_TIMELINE.json --summary NEW_SUMMARY.json
```

The exact host cross-build used the committed flake's `nixosConfigurations.k230-coherent-shell.pkgs.callPackage (f.outPath + "/nix/rust-shell-client") {}` with one job/eight cores. Host checks: 418 library tests passed, one existing ignored; 22 binary route tests passed; nine Python runtime-trace checks passed. Two new full-render pixel oracle tests cover fractional movement, reversal, pressed feedback and semantic/route/size invalidation; prepare-ahead tests cover both-row rest admission. Source build and traces are separate evidence classes.

Both trials used an independent 180-second service-restoration timer plus `finally` cleanup, preserving the installed wrapper environment and replacing only its final ELF. After candidate collection the normal 8cik executable was running and shell/shell-ui/theme-helper were active; both owned trial drop-ins were absent. Normal boot Image, initrd, DTB, boot arguments and firmware hashes still match the previously committed physical normal-boot recovery evidence. No boot selector or system profile was written. Earlier setup attempts aborted before timed input on stale input-unit/preflight identity/generation checks; those failed attempts are not successful results in this pair.

**Remaining:** combined latest source installation (picker plus subsequently landed visual polish), exact installed runtime inspection and task 14.4 real-finger acceptance. Wider group 13/15 gates and the motion target remain open. This candidate was restored after the comparison, so it is not claimed as the persistent current shell.
