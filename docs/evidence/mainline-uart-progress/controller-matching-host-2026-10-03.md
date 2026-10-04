# Matching controller qualification

Evidence class: host preparation against the completed immutable diagnostic bundle;
no UART, board staging, candidate execution, recovery or panel interaction.

The coordinator used `integrate/mainline-probe-path` at `e7aca4d4`, worktree
`/home/jadams/tmp/k230-mainline-probe-integration`. The protected normal baseline
was retained in a private run directory. A new manifest was made from the exact
built bundle bytes and that baseline's protected boot wrapper. No runtime secrets
or protected baseline contents are published.

The narrow host qualification imports `tools/mainline-drm-initrd-shell-trial.py`
and runs these existing functions in order:

```python
prepared = prepare_trial(PRIVATE_MANIFEST, BUNDLE, PRIVATE_NORMAL_REPORT)
prepared = prepare_uart_progress(prepared)
```

Both passed against the `gmsmqkjcb8vmh6h44xvq7y59dd9xihsh` bundle. The
[fixed host receipt](controller-matching-host.json) records immutable identities,
config hash and archived executable hashes. Manifest/load ranges, original
artifact arguments, archived Bash/systemd and their common RISC-V loader, eight
archived executable tools, same-derivation realized kernel.dev config and the
bounded literal transport all qualified. Reporter/dependencies are built-in.
Only the volatile transport selects the reporter and Bash PID1 comparison.

The focused controller tests passed (20 tests); existing trial discovery passed
(214 tests). Prior source/native and Bash tests remain distinct evidence.
This completes task 5f.4's actual matching qualification gate. Tasks 5f.5–6 and
ordinary-root/panel/glass task 5b.5 remain UNVERIFIED.

Next, root must reserve the board/UART, stage the exact candidate closure and
boot files, run the task 5f.5 command with these private paths, and record the
finite observations and protected recovery. No candidate reboot is permitted
by this controller. A host preparation pass does not prove receipt of input,
firmware return, scheduler progress or a usable mainline system.
