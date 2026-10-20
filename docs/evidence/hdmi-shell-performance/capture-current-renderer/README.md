# Prepare capture for current renderer diagnostics

The current renderer emits eight additional numeric fields in each
`K230_PIXMAN_DRAW` row (source/destination format, source geometry, mask,
sampling, operator and opaque-interior selection). The old exact six-field
allowlist silently dropped those complete rows. Capture now retains both
complete schemas and rejects partial/unknown extensions, nonnumeric fields,
invalid transforms/booleans and arbitrary path strings. The log still contains
only the fixed public diagnostic grammar. No runtime logging was added.

The injected diagnostic used six IPC motions in a burst followed by50ms rest.
It now spreads35 moves over a nominal700ms with800ms settling, so moving
scenes can span multiple frames. IPC processing adds time: actual accepted
input timestamps remain in the trace. Context records collector SHA-256 and
nominal workload parameters. Repeat both sides with the same collector and
workload; do not compare these paced runs with the historical burst fixture.
This is compositor IPC injection, not native-uinput, physical contact or
optical latency evidence. The comparison's real-contact gate remains
INCOMPLETE for injected runs.

The named host command `python3 tools/hdmi-shell-capture-board.py --self-test`
exits0 with11 tests. The capture fixture observes at least600ms between first
and last motion commands, catches a return to an instantaneous burst, and
retains cleanup/overflow checks. The current-format fixture preserves all
numeric fields and rejects arbitrary journal values. Exact helper hash and
results are in identity.json and host-tests.txt. Host fixtures do not prove
that a physical compositor accepts the workload or achieves a frame budget.

The next board step is the existing task1.2: connect the portrait HDMI monitor,
reserve the board, record output/runtime identities and actual controlled
baseline/candidate cost traces at unchanged geometry. Separate bounded
profiling must retain cap/observer limits. The nine remaining physical/profile
and acceptance tasks are open. No renderer, Nix default, board configuration
or installed package changed in this host preparation.
