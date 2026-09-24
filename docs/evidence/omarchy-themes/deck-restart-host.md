# Sway deck selected-generation restart guard

Observed 2026-09-24 on `origin/master` `b2478b5d`. Existing
`card_appearance_start()` already resolves the private `current/active`
pointer before its initial scene apply. Its `load()` path guard requires an
exact canonical `generations/<24 lowercase hex>` child and matching report
and appearance identities. A new native receiver fixture now checks the
behavior directly across process restarts:

```sh
python3 tests/test_card_shell_appearance.py
# 7 tests, PASS
```

An active pointer to a valid selected generation produced `APPLY
222222222222222222222222 2 1 1` before `READY`. A pointer to a directory
outside the prepared cache and a dangling pointer each produced the pinned
default `APPLY 111111111111111111111111 1 1 0`. The test did not change
production C source. It proves native startup selection and fallback, not a
new QEMU/board reboot, panel presentation, or installed service wiring.
