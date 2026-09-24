# Settings capability and action interface

This is a host-tested userspace checkpoint for the coherent shell, not a
rendered Settings surface or physical acceptance. The launcher consumes the
JSON interface asynchronously so capability reads and power commands cannot
block touch dispatch. No coherent-shell task is completed by this file alone.

## Protocol

`k230-settings status` returns `schema: 1` and a `controls` object containing
`network`, `brightness`, `keyboard` and `motion`. Each control has `state`,
`value` and `label`; optional fields include `action`, `unit` and `detail`.
States distinguish `unavailable`, `read-only`, `writable` and `action`.

- Network carrier describes `link-up` or `disconnected`, never Internet
  reachability. Unknown carrier remains unavailable. Interface identifiers,
  addresses, SSIDs and command output are not returned.
- Brightness requires exactly one real sysfs backlight with a readable actual
  value. The shell user's existing file permissions determine writability;
  the helper adds no privilege. `brightness PERCENT` reports `pending` while
  the confirmed hardware value differs, retaining that confirmed value.
- Keyboard is an action only when the current user's wvkbd process exists.
  `keyboard-toggle` targets that user and exact process name. A successful
  signal means requested, not proof that the keyboard appeared.
- Reduced motion is read-only when the integration supplies the actual
  session value in `K230_SETTINGS_REDUCED_MOTION=0|1`; otherwise unavailable.
  Runtime motion preference updates remain to be integrated with both owners.

`request reboot|poweroff` returns a confirmation label and opaque token, valid
for 30 seconds. The UI must show this separate confirmation and Cancel.
`cancel TOKEN` performs no power action. `confirm TOKEN` consumes the token
before attempting the exact noninteractive sudo/systemctl command. Replacement,
replay and expiration fail. Denial returns `failed` and a retry route, which
must start a new confirmation. Success means requested, not observed restart.

Only the two existing image sudo rules authorize power actions. The default
runtime path is `/run/shell/settings`, a mode-0700 directory owned by the
session user. Pending confirmation is transient and requires no home state.
External commands have a three-second timeout and discard their output.

## Host evidence

On 2026-09-24, `python3 tests/test_device_settings.py` passed nine tests:
actual sysfs capability parsing, absent/read-only/ambiguous controls, pending
brightness, no battery/network identifiers, fresh home, cancellation,
denial/replay, expiration/replacement, runtime ownership, and command timeout.
Sysfs fixtures and injected command results do not prove device behavior.
The tests explicitly reject the planned `scroll` and `flick-stop` cases until
those UI behaviors have their own actual input tests.

`nix build .#handheld-settings --no-link --print-out-paths --max-jobs 1 --cores 8`
also passed, producing
`/nix/store/yabiwy3maplzxbbhbnk97206jcaxl978-k230-settings`. This wraps the helper
with the cross-package Python, procps and systemd paths; it is package proof,
not a running Settings surface.

The explicit operation allowlist correction was rebuilt after review, producing
`/nix/store/46sw7cwipb8g0pfjqa7vry4x1x65345g-k230-settings`. The same nine host
tests pass, including an unexpected operation with an otherwise valid token;
it neither executes an action nor consumes the pending confirmation.

Remaining: launcher integration and asynchronous action feedback,
real Settings scroll/gesture checks, installed image and board observations.
