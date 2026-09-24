# Host transaction transport checkpoint

Observed 2026-09-23. `tools/theme_transaction.py` is a protocol client for a
future shell receiver, not an installed service. It serializes generation
switches with `flock`, requires matching `prepare` and `commit` replies on a
total-deadline Unix socket exchange, and restores the previous atomic `active`
symlink if commit fails. It requires a `rollback` reply and reports if that
reply fails. Lock acquisition has its own total wait limit; even an idempotent
repeat re-acknowledges receiver state. A failed sync after pointer replacement
also enters restoration. Prepared generations remain available independently of a source
checkout's later removal. It does not launch apps or reload app appearance.

```text
python3 tests/test_omarchy_theme_transaction.py
  PASS: 10 host tests: commit and repeat acknowledgement, prepare rejection,
  commit failure restoration, rollback failure reporting, mismatched and
  slow-drip real-socket replies, cache-boundary rejection, relative state,
  post-replace sync failure recovery, and lock wait limit.
```

The shell receiver and scene-boundary acknowledgement do not exist yet, so
OpenSpec tasks 2.1 and 2.2 stay open. A host reply fixture does not prove a
visible frame swap, normal-session persistence, client reload, or physical
rollback. The next source checkpoint must define/install the receiver, verify
peer identity and late reply ordering, and connect it to the shell's common
appearance generation before enabling a public `omarchy-theme-set` command.
