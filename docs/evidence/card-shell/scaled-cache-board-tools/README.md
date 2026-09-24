# Scaled-cache board-session controls

The card board session now accepts `--scaled-cache off|on` and records the
choice as `scaled_cache` in its plan and session manifest. `off` is the
default. Programmatic `Session.arm` validates the value before querying or
changing normal services. The transient compositor is always launched with
an explicit `SWAY_K230_CARD_SCALED_CACHE=0` or `=1`, so an inherited value
cannot silently enable the cache in an off trial. The normal shell service
configuration is untouched.

The telemetry exporter accepts only `K230_CARD_SHELL scaled-cache` rows with
exactly four unsigned decimal fields: `hits`, `misses`, `fallbacks`, `bytes`.
It rejects missing, duplicate, extra, signed and nonnumeric fields. Existing
budget declarations and acceptance thresholds are unchanged.

Host validation: `python3 tests/test_card_shell_cache_session.py` and
`python3 tests/test_card_shell_board_tools.py`. The first runs the actual
session arm/start/collect path against a fake system, checks off/on launch
arguments and manifest values, verifies invalid programmatic values cause
no normal-service action, and tests raw prefixed telemetry filtering. This
is host proof only. A coordinator-owned same-package off/on board comparison
is still needed, as are a board observation of cache counters and the
separate real-finger and performance gates.
