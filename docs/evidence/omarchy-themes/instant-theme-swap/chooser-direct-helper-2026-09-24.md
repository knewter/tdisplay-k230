# The chooser talks to theme-helper.service directly; discover/prepare_entry caching

Follow-up to `board-diagnosis-2026-09-24.md` in this same directory, after
the coordinator's re-run confirmed the earlier fix (`master` `7a302cd1`,
installed as system `46vdy1dy...`): the daemon path itself now answers in
~250-270 ms, but the Rust chooser still spent about 1.0 s of every call
just starting `theme_client.py`'s Python interpreter (plus `runuser`) to
*reach* that daemon. Worktree `perf/chooser-direct-helper`, base `master`
`7a302cd1`. Host + `cargo test`/`python3 -m unittest` only; no board access
from this worktree.

## Board numbers this task starts from (coordinator's own run)

| | Wall time |
| --- | ---: |
| `list` | 923-1028 ms |
| `preview` (cold) | 3.3-4.5 s |
| `preview` (warm) | 1.06-1.08 s |
| `activate` | 1.27-1.38 s |

`THEME_TIMING` for one `activate`: `handle activate` total 245 ms
(`discover` 42, `prepare_entry` 73, `activate_generation` 128,
keyboard-deferred dispatch 3.6), `helperd` total 265 ms, `client
socket_round_trip` 270 ms `path=daemon`, `exchange` prepare 10-20 ms /
commit 7-14 ms per receiver, `keyboard_deferred sync_and_restart` 300 ms
off the critical path. The daemon itself is fast; the remaining ~1.0 s per
call is `theme_client.py`'s own Python-interpreter-plus-`runuser`
subprocess start-up, paid by the Rust chooser on every single theme
request.

## What changed

### 1. Direct helper-socket bridge (`nix/rust-shell-client/src/theme_catalog.rs`)

`ThemeWorker` now speaks `theme-helper.service`'s own line protocol
directly over a Unix socket (`K230_THEME_HELPER_SOCKET`, defaulting to and
explicitly set in `nix/shell.nix` to `/run/shell/theme-helper.sock` --
`theme_client.py`'s own `DEFAULT_SOCKET`): one JSON request line
(`helper_request()` builds the exact object
`tools/theme_client.py`'s own `as_request()` sends), the write half
half-closed, one JSON reply line (`{"result": ..., "exit_code": ...}`).
No new protocol -- `tools/theme_helperd.py`'s `request_argv()` is what
actually validates and acts on it either way, whichever caller reaches it.

On anything that should not be trusted as a real answer -- socket missing,
refused, timed out (`HELPER_SOCKET_TIMEOUT = 10s`, matching
`theme_client.py`'s own widened default and reasoning), or a malformed
reply -- `execute()` falls back to the existing `k230-theme` subprocess
path unchanged, which itself still tries the same daemon and falls back
further, so a socket that is merely slow to *start* still degrades no
worse than before this task. An empty `K230_THEME_HELPER_SOCKET` disables
the direct attempt entirely, matching `K230_THEME_COMMAND`'s own
unset-env convention (useful for headless-QEMU test harnesses that set
neither and have no real daemon).

A daemon-*reported* error (`exit_code != 0`) is returned as the real error
message directly -- never retried through the subprocess, since the
daemon already validated and rejected that request on its own merits, not
because it was unreachable.

Logs `rust-shell <ms>ms theme-command <action> <id> path=socket
ms=<duration>` (and `path=subprocess ms=<duration>` for the fallback,
timed independently), the exact `rust-shell <ms>ms <event>` shape
`tools/theme-swap-jank.py`'s `RUST_LOG_RE` already parses.

### 2. `discover()` caching (`tools/theme_catalog.py`)

`discover()` is now a cached wrapper (`_discover_uncached` does the real
walk) keyed by `(user_themes, builtins)`, invalidated by
`_catalog_signature()` -- a stat-only fingerprint (name, mtime, is-dir) of
exactly the directory levels `discover()` itself reads: each root's own
top level, and one level under a user-origin entry's own `themes/`
collection. Never a content read, never the identity-hashing/
`find_preview()`/`path.resolve(strict=True)` work `discover()` itself
does on a genuine (un)cached walk. A bare CLI process only ever calls this
once per invocation (empty cache each time, no behaviour change); the
daemon serves many requests against a catalog that, in the ordinary
preview-then-activate chooser flow, has not changed between them.

### 3. `helper_digest()` caching (`tools/theme_activate.py`)

`prepare()`'s `helper_hash = source_digest(tools)` is now
`helper_digest(tools)`, caching the result indefinitely per the tools
directory's own resolved path. `tools` is `theme_helperd.py`'s own fixed
`--tools` startup flag (a Nix store path in production), immutable for the
daemon's entire lifetime -- unlike the theme's own `source_hash`,
deliberately left uncached, since a person can edit their own theme's
files while the daemon keeps running.

## Test-suite proof (host only)

- `cargo test --offline` (nix/rust-shell-client): 184 cases (5 new, in a
  new `tests/theme_catalog_module.rs`), all passing:
  - a working helper-socket reply is used, and the subprocess (a "poison"
    script that marks a file if it ever actually runs) is never invoked;
  - a daemon-reported error (`exit_code=1`) is returned directly, without
    retrying via the subprocess;
  - a missing helper socket falls back to the subprocess;
  - a malformed helper-socket reply falls back to the subprocess;
  - an empty `K230_THEME_HELPER_SOCKET` disables the direct attempt
    entirely.
- `python3 -m unittest` across the full existing theme suite (133 cases,
  2 new): `test_discover_is_cached_until_the_catalog_directory_actually_changes`
  (an unchanged catalog is not re-walked; adding or removing a theme is
  still noticed on the very next call) and
  `test_helper_digest_is_cached_across_repeated_preparations` (counts
  `source_digest` calls across two `prepare()` calls for the same tools
  path: 3 on the first cache-miss call, only 1 more -- the theme's own
  `source_hash` -- on the second cache-hit call).
- `nix build --no-link --print-out-paths --max-jobs 1 --cores 6
  .#handheld-shell-rust .#handheld-theme-command .#handheld-theme-default
  .#card-shell`: all build for riscv64.
- `nix eval .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel.drvPath`:
  evaluates cleanly.
- `openspec validate the-shell-swaps-themes-without-a-python-stall --strict`:
  valid.
- `python3 tools/blob-scan.py`: exit 0.
- `tests/rust_theme_chooser_qemu.py` (the existing synthetic-command QEMU
  proof, unmodified -- it sets neither `K230_THEME_HELPER_SOCKET` nor a
  real daemon, so this exercises the unchanged subprocess-fallback path
  end to end in the real Sway/Rust stack): attempted twice against this
  worktree's build and once against an unmodified `master` build, all
  three failing identically at the same early `--surface settings`
  IPC round trip ("route timed out") under this host's current load
  (`uptime` showed 16-17 -- lower than the 23-28 seen in the previous
  task's flake, but still contended by other agents per
  `tools/work-status.py`) -- confirmed **not** a regression from this
  branch by reproducing it against `origin/master` unmodified, same as the
  previous task's `test_paired_theme_endpoints_runtime.py` flake. Not
  re-run to a pass on this host; the direct-socket logic itself is proven
  precisely by the 5 new `theme_catalog_module.rs` cases above (a fake
  Unix-socket daemon and a fake subprocess), which do not depend on the
  full Sway/touch harness or this host's current load.

## Honest expectation for the board re-run (not claimed as measured)

`discover`/`prepare_entry` should drop by roughly their `_catalog_signature`/
`helper_digest` cache-hit share of the 42 ms / 73 ms board numbers above
(not measured here -- no board). `activate_generation`'s 128 ms is
unchanged by this task, deliberately: it is the two-phase exchange plus
`app_appearance`/preference-commit filesystem work, load-bearing for
correctness, not a caching candidate. The direct socket bridge should
remove essentially all of the ~1.0 s subprocess/Python-start-up cost the
coordinator's own board run isolated. Putting those together, this
worktree's own honest estimate lands close to, and may not fully clear,
the ~150 ms target purely from `activate_generation`'s own remaining cost
-- the board run below is what actually answers it, not this estimate.

## Exact board commands for the coordinator

Confirm the new build is installed and the socket is where the Rust
binary now expects it:

```sh
systemctl status theme-helper --no-pager
systemctl status shell-ui --no-pager
ls -la /run/shell/theme-helper.sock
```

Use the on-screen chooser itself (tap through Settings -> Themes -> a
theme -> Apply) rather than the raw CLI this time, so the measurement is
the Rust chooser's own request path, then pull:

```sh
journalctl -u shell-ui --since "-5 min" --no-pager | grep 'theme-command'
```

Expect `rust-shell <ms>ms theme-command <action> <id> path=socket
ms=<ms>` for each `list`/`preview`/`activate` the chooser issued while
`theme-helper.service` was up, with `ms=` now close to the daemon's own
`THEME_TIMING handle`/`helperd` totals (no separate subprocess start-up
line before it). Then, as before:

```sh
journalctl -t k230-theme-timing --since "-5 min" --no-pager
```

Look for `THEME_TIMING prepare <name> ... cache=hit` (now reachable via
the direct socket, not a subprocess) and confirm the overall tap-to-visible
feel and the `activate` timing (`rust-shell ... path=socket ms=...`)
against the ~150 ms target from this task's own ask.

None of the commands above have been run by this worktree; `/dev/ttyACM0`
was not opened.
