# Board diagnosis: the helper wasn't the bottleneck, `prepare()` was

Follow-up to `README.md` in this same directory, after the coordinator ran
the landed `perf/instant-theme-swap` work (`master` `b3183866`, plus the
later `d87728a4` preview-race fix) on the reserved board, system
`766yhn3l...`. This file is a **host + code-reading** diagnosis of that
board run (the board run itself is the coordinator's own, not repeated
here) plus the fix and instrumentation this worktree (`perf/instant-swap-board`,
base `master` at `d87728a4` or later) adds. No board access from this
worktree; nothing here is a new board measurement.

## The board numbers (coordinator's own run, timed directly with the
installed `k230-theme`, shell user, chooser closed)

| Command | Wall time |
| --- | ---: |
| `list --json` | 886-890 ms |
| `preview <id>` (catppuccin/-latte, already prepared, has `background.cache`) | 3950-4095 ms |
| `activate --json --expected-generation <g> <id>` | 4183-4263 ms |

`journalctl -u theme-helper --since -3min` showed no entries.
`/run/shell/theme-helper.sock` existed, owned by `shell`. Before the daemon
existed at all, `activate` took 2.8-3.5 s -- so the daemon made this
*worse*, not better.

## Root cause (found by reading the actual code path, confirmed by a host measurement)

`theme_activate.py`'s `prepare()` is called by every `preview`/`activate`,
daemon-served or not. It used to check whether the destination generation
already existed **only at the very end** -- after:

1. hashing the whole theme source tree (`source_digest`, reading every
   background image's full bytes) and the whole `omarchy-theme-tools`
   tree,
2. staging: copying every background image and config file into a scratch
   directory (`checked_copy`, a second full read-and-write of the same
   bytes `source_digest` just read),
3. invoking the external `omarchy-theme-color --all` helper (a bash
   script that itself spawns several `awk` subprocesses per call for
   colour mixing),
4. invoking `omarchy-theme-set-templates` (another bash script, which
   itself re-invokes `omarchy-theme-color --all` *again* internally, then
   runs `sed -f <script>` per template file),
5. (only for a *new* generation) building the wallpaper cache.

For an **already-prepared** generation, none of steps 2-5 do anything
useful -- the exact same output already exists on disk -- but all of it
ran anyway, every single call, and was thrown away the moment the
(previously last-checked) `destination.exists()` test finally ran. This is
real, subprocess-spawning, disk-I/O work, unrelated to Python interpreter
start-up (which `theme-helper.service` already correctly eliminated), so
removing the interpreter cost alone could never have fixed it -- consistent
with the board showing the daemon reachable yet the numbers not improving.

`theme_client.py` compounded this. Its `--helper-timeout-s` default was
`0.3` s, sized for "how long should Python start-up take", not "how long
can a real `prepare()` legitimately take". Since a real `preview`/`activate`
routinely took several seconds (per above), the client's socket read timed
out on an **already-working** daemon reply almost every time, abandoned
it, and fell back to the full in-process path -- paying the wasted `0.3` s
*and* the ~1.2 s import chain *and* `prepare()`'s cost a second time. This
fully explains the board's `activate` number landing *above* the
pre-daemon baseline: `0.3 + 1.2 + ~2.7 (prepare) ≈ 4.2 s`, matching the
observed 4.18-4.26 s almost exactly.

`journalctl -u theme-helper` showing nothing was not a sign of failure --
neither `theme_helperd.py` nor `theme_catalog.py` printed anything on
success or failure. There was nothing to see, not evidence the daemon
wasn't being used.

## The fix

- `tools/theme_activate.py`: `prepare()` now computes the generation's
  content-addressed identity (two digests already computed first, plus a
  cheap background-name directory listing -- no asset bytes copied, no
  external helper spawned) and checks for an existing destination
  **before** any staging/external-helper/wallpaper-cache work. A cache hit
  returns the on-disk `report.json`, patched only for the one field that
  is genuinely request-specific (a since-removed remembered background
  choice), never rewriting the shared, immutable generation. Host-measured
  on this machine: a repeat `prepare()` for the same generation dropped
  from 240-370 ms (cache miss, external helpers included) to 1.5-2.7 ms
  (cache hit) -- see `tests.test_omarchy_theme_activation`'s own captured
  `THEME_TIMING` lines.
- `tools/theme_client.py`: `DEFAULT_TIMEOUT_S` raised from `0.3` to `10.0`
  -- comfortably above every board number seen so far (including the
  *slow*, pre-fix ones), so a legitimate daemon reply is never abandoned
  in favour of the strictly worse fallback path.
- `tools/theme_timing.py` (new): a tiny `Stopwatch`/`log()` helper, wired
  into `theme_activate.prepare()`, `theme_transaction.exchange()`,
  `theme_catalog.handle()`, `theme_helperd.handle_line()`, and
  `theme_client.py`, emitting one `THEME_TIMING <component> <action>
  phase=Xms ...` line per request via `syslog` -- deliberately never
  `print(..., file=sys.stdout/stderr)`, because `theme_catalog.rs`'s
  `command_error()` parses a failing CLI's stderr as JSON byte-for-byte,
  and any stray text there turns a real error message into a generic
  "theme command failed". `journalctl` captures syslog by default, tagged
  with the emitting process's own systemd unit when it has one.
- `nix/rust-shell-client/src/theme_catalog.rs`: `execute()` now logs
  `rust-shell <ms>ms theme-command <action> <id> duration=<ms>ms` (the
  existing `rust-shell <ms>ms <event>` shape `tools/theme-swap-jank.py`
  already parses), timing the chooser's own wait on the `k230-theme`
  subprocess -- confirming (by inspection: `nix/shell.nix`'s
  `shell-ui.service` sets `K230_THEME_COMMAND` to the `theme_client.py`
  wrapper, the exact same binary the coordinator ran by hand) that the
  chooser path already goes through the daemon-aware client; no code
  change was needed there, only the timing.
- `nix/handheld-theme-command.nix`: added the missing
  `install -m 0644 ... theme_timing.py` line -- every module above now
  imports it, and it was not being installed into the packaged
  `libexec/handheld-theme/` directory, which would have made every
  `k230-theme` invocation on a freshly built system fail with
  `ModuleNotFoundError` the moment this change's own instrumentation
  shipped. Caught here, before any board install, by rebuilding
  `.#handheld-theme-command` after adding the instrumentation and noticing
  the derivation's own file list.

## Test-suite proof (host only)

- `python3 -m unittest tests.test_omarchy_theme_activation`: 12 cases
  (2 new), including the two that assert `checked_copy`/`invoke` raise if
  called on a cache hit.
- `python3 -m unittest tests.test_theme_helper_daemon`: 6 cases (1 new),
  including a daemon reply mocked to take 0.6 s (past the old 0.3 s
  default, inside the new one) asserting the client never falls back.
- `python3 -m unittest tests.test_theme_timing`: 5 cases, asserting the
  log helper never touches stdout/stderr and never raises.
- `python3 -m unittest tests.test_theme_catalog tests.test_omarchy_theme_transaction`
  plus the full existing theme suite: unaffected (131 cases total across
  this worktree's touched files, all passing).
- `cargo test --offline` (nix/rust-shell-client): 138 cases, all passing.
- `nix build --no-link --print-out-paths --max-jobs 1 --cores 6
  .#handheld-shell-rust .#handheld-theme-command .#handheld-theme-default
  .#card-shell`: all four build for riscv64:
  - `/nix/store/i1xa32amsa0r5zxlivwsmq91mldi2mqm-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0`
  - `/nix/store/rsmbxhf0j5xfg6lj76kfqm5a78bxx4wl-handheld-theme-command-0.1`
    (rebuilt after the `theme_timing.py` packaging fix below; the first
    build of this attr, before that fix, silently omitted the file --
    caught here by listing the derivation's own installed files, not by a
    board failure)
  - `/nix/store/m3vwvnnckr7m9mkcpnbhbhc0c4hz3p8i-handheld-theme-default-28ceaae7`
  - `/nix/store/fq1i1fmhqa4a35amc61nx2z0wbr2a5yz-k230-card-shell`
- `openspec validate the-shell-swaps-themes-without-a-python-stall --strict`:
  valid.

## QEMU smoke test of the actual packaged binary (not just host unit tests)

Built `.#handheld-theme-command` fresh from this worktree
(`/nix/store/rsmbxhf0j5xfg6lj76kfqm5a78bxx4wl-handheld-theme-command-0.1`,
a riscv64 package) and ran its `bin/k230-theme` wrapper under
`qemu-riscv64-static` (via this host's registered `binfmt_misc` handler, so
the wrapper script runs exactly as it would from a board shell), no daemon
socket present (fallback path, so this exercises `theme_activate.prepare()`
and `theme_timing`'s real `syslog` calls in a real riscv64 interpreter, not
this host's own Python):

```
list --json:                 1.735 s
preview <id> --json (cold):  5.920 s
preview <id> --json (again): 1.799 s   -- byte-identical output to the cold run
```

Confirms, independent of the host unittest numbers above: `theme_timing.py`
is correctly packaged (no `ModuleNotFoundError`), stdout carries nothing
but the JSON result in both the cache-hit and cache-miss case (`syslog`
never leaks into it, even where `/dev/log` may not exist in this qemu-user
environment -- `theme_timing.log()`'s own `except Exception: pass` holds),
and the cache-hit `preview` matches `list`'s own baseline cost almost
exactly (~1.7-1.8 s, all qemu-user-emulation + Python-start-up overhead,
nothing left from staging/external-helper work), while the cache-miss
`preview` pays for two additional emulated subprocess trees
(`omarchy-theme-color`/`omarchy-theme-set-templates`, each themselves
spawning several `awk`/`sed` children) at roughly 3x the cost. This is
still qemu-user overhead dominating the *absolute* numbers, never the
K230's own in-order core -- only the *relative* cache-hit-vs-miss
comparison (and the packaging/stdout-cleanliness proof) is meaningful from
this host.

## Exact board commands for the coordinator

Confirm the daemon picked up the new build and is reachable:

```sh
systemctl status theme-helper --no-pager
ls -la /run/shell/theme-helper.sock
```

Repeat the exact timed sequence from the original report (same theme ids,
so this lands on the *same*, already-prepared generation and exercises the
new cache-hit fast path), as the shell user with the shell session's own
runtime dir and display:

```sh
sudo -u shell env XDG_RUNTIME_DIR=/run/shell WAYLAND_DISPLAY=<shell's own value> \
  bash -c 'time k230-theme list --json' >/tmp/list.json
sudo -u shell env XDG_RUNTIME_DIR=/run/shell WAYLAND_DISPLAY=<shell's own value> \
  bash -c 'time k230-theme preview --json <catppuccin-or-latte-id>' | tee /tmp/preview.json
GEN=$(python3 -c "import json,sys;print(json.load(open('/tmp/preview.json'))['generation'])")
sudo -u shell env XDG_RUNTIME_DIR=/run/shell WAYLAND_DISPLAY=<shell's own value> \
  bash -c "time k230-theme activate --json --expected-generation $GEN <same-id>"
```

Expected: `preview`/`activate` well under 500 ms each now that the
generation is already prepared (task 4's own target). Pull the new
self-diagnosing timing from the journal right after:

```sh
# Every THEME_TIMING line from every process on the machine (client,
# daemon, and the two-phase exchange), regardless of which one emitted it:
journalctl -t k230-theme-timing --since "-5 min" --no-pager

# The daemon's own view specifically (same lines, scoped to its unit):
journalctl -u theme-helper --since "-5 min" --no-pager
```

Look for, per the coordinator's own diagnostic questions:

- `THEME_TIMING client <action> ... path=daemon outcome=ok` -- confirms
  the client actually used the daemon, not the fallback (`path=fallback`
  would mean it didn't, with `outcome`/`reason` saying why).
- `THEME_TIMING prepare <name> ... cache=hit` with a `total=` of a few ms
  -- confirms `prepare()` skipped staging/helper-invocation/wallpaper-cache
  entirely for the already-prepared theme. `cache=miss` (with
  `omarchy_theme_color=`/`omarchy_theme_set_templates=` phases) is expected
  and correct for a theme prepared for the first time; `cache=race` is the
  rare concurrent-preparer path.
- `THEME_TIMING exchange <phase> endpoint=<...> generation=<...> ms=...`
  -- the Rust/deck ack round trip time, per phase per receiver.
- `THEME_TIMING handle activate ...` -- the daemon's own per-action
  breakdown (`discover`/`prepare_entry`/`activate_generation`/
  `keyboard_deferred_dispatch`/`total`).
- `THEME_TIMING keyboard_deferred activate ... state=applied|failed|superseded`
  -- confirms the deferred keyboard thread (task 3.3a) actually ran and
  finished, separately from `handle()`'s own (fast) return.

Then, separately, actually use the on-screen theme chooser (not just the
raw CLI) to exercise the Rust catalog bridge end to end, and pull its own
timing:

```sh
journalctl -u shell-ui --since "-5 min" --no-pager | grep 'theme-command'
```

Look for `rust-shell <ms>ms theme-command <action> <id> duration=<ms>ms`
-- the chooser's own wait on each `k230-theme` call, which should now
track the fast `path=daemon`/`cache=hit` numbers above rather than the
multi-second numbers from before this fix.

None of the commands in this section have been run by this worktree;
`/dev/ttyACM0` was not opened.
