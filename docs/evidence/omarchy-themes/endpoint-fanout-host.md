# Two-receiver theme transaction: host checkpoint

Observed 2026-09-23 from pushed integration base `b21daed7`. The existing
single `/run/shell/appearance.sock` route remains available for the opt-in C
launcher trial. `omarchy-theme-set` and the JSON chooser now also accept the
pair `--rust-socket RUST --deck-socket DECK`; supplying just one is rejected.
The planned installed pair is `/run/shell/k230-shell-rust-appearance.sock` and
`/run/shell/card-appearance.sock`. The Rust reveal/route socket is a different
interface and must not receive these messages.

The two-receiver route retains protocol 1 newline JSON and exact ACK checks.
Under one bounded activation flock it sends `prepare` to both receivers before
publishing `current/active`, then commits both. A rejected or lost prepare
triggers idempotent `rollback(previous)` to both, including the receiver whose
prepare did not ACK. A failed commit or preference write restores the pointer,
preference and both receivers, requiring both rollback ACKs. Even if one
rollback fails, the coordinator attempts the other and reports the unresolved
state. An app-specific Foot sync runs only after both commit ACKs and outside
the activation lock; its result remains separate from shell acceptance.

```text
python3 tests/test_omarchy_theme_transaction.py  PASS 18 host tests
python3 tests/test_theme_catalog.py              PASS 9 host tests
python3 tests/test_omarchy_theme_activation.py   PASS 9 host tests
openspec validate the-shell-loads-omarchy-themes --strict  PASS
```

Failure fixtures cover rejection at the second prepare, loss of the second
commit ACK after the first commit, failed preference persistence after both
commits, and one failed rollback while the other is still attempted. The
legacy single-receiver tests continue to pass. Neither Rust nor Sway theme
endpoint source was installed or exercised here; a fake transport ACK is host
logic evidence, not a compositor repaint or physical panel observation.
OpenSpec task 2.2 and all physical gates remain open.
