# Session notification broker

Host implementation checkpoint, 2026-09-24. No notification UI, keyboard focus,
touch interaction, or board proof is claimed here. This service supplies actual
runtime data to the coherent shell's shade rather than a mock list.

`k230-notifications serve` owns a private Unix socket, normally
`/run/shell-notifications/events.sock`. The daemon accepts one bounded newline
JSON request per connection. `k230-notifications history`, `emit`, `dismiss ID`,
`dismiss-all`, and `action ID` are CLI clients of the same protocol. A native
shell client can use the socket directly without launching a process per poll.

The `history` response has `schema: 1`, `count`, `events`, and nullable `preview`.
Each history event has `id`, `source`, `icon`, `summary`, `body`, `priority`,
`timestamp` (Unix seconds), `error`, `dismissible`, and `action_available`.
Preview has `id`, `source`, `summary`, `icon`, `priority`, `ongoing`, and
`focus: false`. The client must keep unsolicited previews outside the keyboard
and focused input; that client behavior remains to be tested.

Requests use `operation: history|emit|dismiss|dismiss-all|action`. Dismiss/action
also carry integer `id`. Emit accepts `summary`, `body`, `tag`, `priority`,
`private`, `ongoing`, and optional Sway container `target`. Sender-supplied
source labels are ignored. Linux peer credentials establish root/system or a
Nix-pinned executable identity from the `--trusted` JSON map; other session
senders are unknown, ordinary, private, with no app icon or action authority.

Unsolicited private previews reveal neither source identity nor summary/body.
Opening history reveals the retained content. Previews expire after five
seconds without deleting history; ongoing critical events retain a preview and
cannot be dismissed. Only their trusted source's matching tag can update them
to resolved. Ordinary history expires after an hour. At most 64 events remain;
a full history of ongoing critical events rejects further input. Source/tag
deduplication updates one record. Missing action targets remain in history with
an error; action always revalidates the actual Sway tree before focus and never
executes an event-supplied command.

The broker accepts at most eight simultaneous clients, 4096 request bytes, and
two seconds per connection. An unfinished client does not stall other clients.
The socket and runtime directory are private to the session user. An exclusive
broker lock supports stale-socket recovery after a killed daemon. History is
session memory, not a claim of reboot persistence or freedesktop notification
API coverage.

`python3 tests/test_notification_center.py` passed nine host tests: priority,
privacy, retention/deduplication/expiry, unknown-source downgrade, preview
timeout, disappeared target/retry, retained/resolved critical events, bounded
critical flood, and a real Unix-socket daemon with a stalled client and killed
daemon restart. UI-specific typing-focus/scroll/swipe cases deliberately remain
unimplemented and are rejected if requested; they require the actual client.

`nix build .#handheld-notifications --no-link --print-out-paths --max-jobs 1 --cores 8`
passed, producing `/nix/store/n9p1qlrflc463v3siyrhj49n5hdbh1fd-k230-notifications`.
The package uses the board package graph and excludes XWayland; an initial
overbroad dependency selection was stopped and corrected before this build.

Remaining: service integration, pinned source registration,
shade rendering and interaction, real compositor focus test, and board evidence.
