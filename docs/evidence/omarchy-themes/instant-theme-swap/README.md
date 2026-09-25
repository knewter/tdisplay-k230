# Instant theme swap: buffer-swap commit, chooser prepare-ahead, deferred wvkbd

Implements OpenSpec tasks 3.1b, 3.2, and 3.3a from
`openspec/changes/the-shell-swaps-themes-without-a-python-stall/tasks.md`,
against the user's stated target: the new theme visible within about 100 ms
of the Apply tap, touch and animation never stalling. This is a **host +
headless-QEMU-under-`qemu-riscv64-static`** result: no board, glass, or
real-finger observation. Worktree `perf/instant-theme-swap`, base `master`
`64c38998`.

## What changed (see the OpenSpec change's `tasks.md`/`proposal.md` for the full design)

- `nix/rust-shell-client/src/background_decode.rs`: `BackgroundCache` is now
  a bounded 4-entry LRU instead of a single slot, so browsing a second
  candidate no longer evicts a first one's decode before its own commit.
- `nix/card-shell/appearance.c`/`appearance.h`: a new advisory
  `card_appearance_prepare_fn` callback, invoked once per successfully
  validated `prepare`, before its ack; never able to affect prepare's own
  accept/reject decision.
- `nix/card-shell/adapter.c`: `appearance_prepare` uses that hook to
  pre-build the deck's gradient (`card_brush_scene`) for a *candidate*
  generation, disabled/detached until a matching commit;
  `appearance_canvas_refresh` adopts it at commit (destroy old, promote
  pointer, enable+position) instead of repainting, falling back to the
  original inline build whenever nothing warm matches.
- `nix/rust-shell-client/src/theme_ui.rs` (`ThemeView::poll_prepare_ahead`/
  `prepare_ahead_submitted`/`prepare_ahead_reply`) and `main.rs`'s existing
  per-tick carousel-settle loop: once the Themes list carousel has been
  centred, at rest, on the same (non-active) theme for 220 ms, the chooser
  submits the existing `preview` request directly to the shared
  `ThemeWorker` as a background warm-up, bounded to one in flight, whose
  reply is discarded before it can reach `ThemeView::accept`.
- `tools/theme_catalog.py`: `activate`'s keyboard recolour/restart
  (`keyboard_appearance.sync_and_restart`) now runs on a background
  (non-daemon) thread; the response reports `{"state": "deferred"}`
  immediately instead of waiting for the restart.
- Two new named stage markers in `main.rs`'s own event log
  (`appearance-prepare-accepted`, `appearance-commit-accepted`) and in
  `adapter.c`'s `sway_log` (`K230_CARD_SHELL appearance-canvas-gradient-
  adopted`/`-built`), both already readable by
  `tools/theme-swap-jank.py`/`tools/analyze-theme-swap-jank.py`'s existing
  journal parsing, for task 1's per-stage instrumentation.

## Test-suite proof

- `cargo test --offline` (nix/rust-shell-client): 101+7+14+8+8 = 138 cases,
  all passing, including three new `theme_ui` tests for the debounce/
  dedupe/stray-reply behavior and one new `background_decode_module` test
  (`multiple_recent_candidates_stay_warm_without_evicting_each_other`).
- `python3 -m unittest tests.test_theme_catalog tests.test_theme_helper_daemon
  tests.test_omarchy_theme_transaction tests.test_omarchy_theme_activation
  tests.test_omarchy_theme_resolution tests.test_omarchy_theme_sources
  tests.test_omarchy_theme_tools tests.test_handheld_keyboard_theme
  tests.test_handheld_theme_bundle tests.test_handheld_theme_default
  tests.test_theme_preferences tests.test_theme_background_metrics
  tests.test_theme_background_status tests.test_card_shell_appearance`:
  101 cases, all passing, including a new `test_theme_catalog` case
  (`test_activate_reports_keyboard_sync_as_deferred_but_it_still_completes`)
  and `test_card_shell_appearance`'s extension for the new `prepare` hook
  (a `PREPARE <id> <card> <selected> <wallpaper>` line, printed by
  `tests/fixtures/card_appearance_receiver.c`, asserted before each
  successful prepare's own ack).
- `python3 tools/blob-scan.py`: exit 0 ("every binary is accounted for").
- `nix build --no-link --print-out-paths --max-jobs 1 --cores 6
  .#handheld-shell-rust .#card-shell .#handheld-theme-command
  .#handheld-theme-default`: all four built cleanly for riscv64 (the C
  changes only compile against real wlroots/Sway types, so `.#card-shell`
  is this task's actual C compile-check, not just a unit test).
- `nix eval .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel.drvPath`:
  evaluates to a `.drv` path (`nixos-system-nixos-...`), no eval error.
- `openspec validate the-shell-swaps-themes-without-a-python-stall --strict`:
  valid.

## Headless-QEMU runtime proof (real Sway + real Rust shell, not synthetic)

Store paths (`perf/instant-theme-swap`, this worktree):
- sway (with this change's C telemetry):
  `/nix/store/ajdxjvqp303gnbdqbm67jnfk9pw8nbn4-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`
  (`nix-store -qR` of `.#card-shell`)
- rust shell: `/nix/store/qdh605prj11a2kbwy3kq3gayk1x4fyjv-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust`
  (`.#handheld-shell-rust`)
- theme bundle: `/nix/store/hklqzizmpawxdp044zm5rqa19xbq6pz7-handheld-theme-default-28ceaae7`
  (`.#handheld-theme-default`)
- icons: `/nix/store/in3nc21zx02xiz2rdp5bpq36719x3axd-handheld-theme-icons-25.10.3`
  (`.#handheld-theme-icons`)
- client: `/nix/store/qpjim9wgpwcwjnyvg6zn0qgyf5v9g746-card-composition-probe-client-riscv64-unknown-linux-gnu-0.1/bin/card-composition-probe-client`
  (`nix-store -qR` of `.#card-composition-probe`)

### 1. Task 3.2 end to end, real touch injection

```sh
python3 tests/rust_theme_chooser_qemu.py \
  --sway /nix/store/ajdxjvqp303gnbdqbm67jnfk9pw8nbn4-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --rust /nix/store/qdh605prj11a2kbwy3kq3gayk1x4fyjv-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust \
  --output /tmp/k230-is-2
```

`PASS`. The captured synthetic-command log (`/tmp/k230-is-2/theme-commands.jsonl`)
shows exactly the intended shape:

```
["list"]
["preview", "...06"]                                    <- warm-up while dragging settled on 6
["preview", "...07"]                                    <- warm-up while a side-tap settled on 7
["preview", "...07"]                                    <- the explicit confirm tap's own request
["preview", "...07", "--background", "dddd..."]         <- explicit background selection
["list"]                                                 <- after Cancel
["preview", "...00"]                                     <- re-confirm (post-cancel, centred on active)
["activate", "...00", "--expected-generation", "bbbb...", "--background", "cccc..."]
```

Two background warm-up `preview` calls landed during ordinary browsing
(drag, then a side-slice tap), each fired only after its own theme sat
centred and at rest past the 220 ms debounce, neither one visible to the
person (no navigation, no repaint beyond the carousel's own animation --
proven by this test's own screenshot diffs at each step) and neither one
able to activate or select a background (`browse_calls_are_safe`'s
assertion, updated in this change since it is the exact old "browsing must
never call preview" invariant this task deliberately changes). The
subsequent explicit confirm, Apply, Cancel, and re-confirm flows are
byte-for-byte the same as before this change.

### 2. Task 3.1b on the compositor: gradient prepare/adopt pixel proof

```sh
python3 tests/test_card_shell_appearance_runtime.py \
  --sway /nix/store/ajdxjvqp303gnbdqbm67jnfk9pw8nbn4-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --client /nix/store/qpjim9wgpwcwjnyvg6zn0qgyf5v9g746-card-composition-probe-client-riscv64-unknown-linux-gnu-0.1/bin/card-composition-probe-client \
  --output /tmp/k230-is-appr1
```

`result.json`: `"result": "PASS"`, with the canvas gradient's left edge
`(250,0,5)` and right edge `(4,0,251)` matching the authored `#ffff0000` ->
`#ff0000ff`, 90-degree stops exactly, and rollback restoring the pre-theme
backdrop `(30,30,46)` exactly. `sway.log` shows:

```
K230_CARD_SHELL appearance-canvas-gradient-adopted generation=222222222222222222222222
```

-- exactly once, never `-built`, proving the candidate's gradient was
built during `prepare` and *adopted* (not repainted) at `commit`, with
correct pixels.

### 3. Task 3.1b+3.2 on the real two-phase protocol under occlusion + throttle

Reused `tests/test_theme_commit_under_occlusion_runtime.py`'s own harness
shape (real `theme_catalog.py preview`/`activate` CLI calls, real
`sway`+`k230-shell-rust` under `qemu-riscv64-static`, the Rust process
throttled via `cpulimit`, an ordinary maximized opaque app already mapped):

```sh
python3 tests/test_theme_commit_under_occlusion_runtime.py \
  --sway /nix/store/ajdxjvqp303gnbdqbm67jnfk9pw8nbn4-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --rust /nix/store/qdh605prj11a2kbwy3kq3gayk1x4fyjv-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust \
  --client /nix/store/qpjim9wgpwcwjnyvg6zn0qgyf5v9g746-card-composition-probe-client-riscv64-unknown-linux-gnu-0.1/bin/card-composition-probe-client \
  --theme-bundle /nix/store/hklqzizmpawxdp044zm5rqa19xbq6pz7-handheld-theme-default-28ceaae7 \
  --icons /nix/store/in3nc21zx02xiz2rdp5bpq36719x3axd-handheld-theme-icons-25.10.3 \
  --tools nix/omarchy-theme-tools/upstream --throttle 60 --output /tmp/k230-is-occ3
```

`Scenario B (rollback to packaged default with previous=None) PASS` /
`Scenario A (commit under occlusion) PASS`. The default `--throttle 20`
timed out during Scenario B's own `prepare` exchange on this dev host --
**identically against an unmodified `master` build of the same test**, so
this is this host's known QEMU+`cpulimit` decode throughput limit at `-l
20` (already documented in
`docs/evidence/omarchy-themes/background-decode-cache-qemu/README.md`),
not a regression; `--throttle 60` clears it for both. `rust.log` shows the
two new stage markers landing:

```
rust-shell 2576ms appearance-prepare-accepted
rust-shell 2774ms wallpaper-commit
rust-shell 2774ms appearance-commit-accepted
rust-shell 3051ms appearance-prepare-accepted
rust-shell 3270ms appearance-prepare-accepted
rust-shell 3280ms wallpaper-commit
rust-shell 3280ms appearance-commit-accepted
```

### 4. Tap-to-visible, cold vs. warmed-ahead (`activate`'s own wall time only)

A small script (not committed -- see reproduction command below) reused the
same harness shape to isolate exactly the `activate` call's own wall time
in two cases: (A) cold, no browse-ahead (`preview` then `activate`
immediately -- what any theme not dwelled on still costs, even after this
change), and (B) `preview` (task 3.2's own warm-up call shape), a 400 ms
simulated dwell (past the 220 ms debounce), *then* only `activate` timed:

| | wall time |
| --- | ---: |
| A: cold `activate` (gruvbox, never prepared) | 223 ms |
| B: `activate` after a warm-up + dwell (nord, never prepared) | 236 ms |

Both already fast and nearly equal here: `rust.log` shows only a 13-15 ms
gap between `appearance-prepare-accepted` and `appearance-commit-accepted`
in *both* cases, meaning these particular bundled themes' backgrounds
decode fast enough on this host under QEMU that decode was never this
measurement's bottleneck -- the dominant, already-fixed cost this whole
change addresses is the ~1.2 s Python-interpreter import tax
`theme-helper.service` already removes (see
`docs/evidence/omarchy-themes/theme-swap-jank/README.md`'s own numbers),
not wallpaper decode for typical theme assets. What 3.1b's LRU specifically
prevents is a *regression* that would otherwise reappear once 3.2 lands:
without it, browsing a second/third candidate before Apply would evict a
single-slot cache's warm entry, turning a would-be buffer swap back into a
`background.cache` file read or a full decode; `multiple_recent_candidates_
stay_warm_without_evicting_each_other` (`background_decode_module.rs`) is
the correctness proof for that, in the absence of a wall-clock difference
large enough to be visible with these particular fixture assets.

Reproduce with the new `tools/theme-swap-jank-warm-ahead-demo.py` (same
store paths as above; `--theme-a`/`--theme-b` default to gruvbox/nord):

```sh
python3 tools/theme-swap-jank-warm-ahead-demo.py \
  --root "$(pwd)" \
  --sway /nix/store/ajdxjvqp303gnbdqbm67jnfk9pw8nbn4-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --rust /nix/store/qdh605prj11a2kbwy3kq3gayk1x4fyjv-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust \
  --client /nix/store/qpjim9wgpwcwjnyvg6zn0qgyf5v9g746-card-composition-probe-client-riscv64-unknown-linux-gnu-0.1/bin/card-composition-probe-client \
  --theme-bundle /nix/store/hklqzizmpawxdp044zm5rqa19xbq6pz7-handheld-theme-default-28ceaae7 \
  --icons /nix/store/in3nc21zx02xiz2rdp5bpq36719x3axd-handheld-theme-icons-25.10.3 \
  --tools nix/omarchy-theme-tools/upstream --throttle 60 --output /tmp/k230-is-warm-N
```

It is a thin wrapper around `test_theme_commit_under_occlusion_runtime.py`'s
own setup, timing only the `theme_catalog.py activate` subprocess call in
each scenario (not a proof tool with its own `--self-test`; it produces a
number, `tools/analyze-theme-swap-jank.py` and the two runtime tests above
are what assert pass/fail).

### 5. A test-suite invariant this change intentionally breaks (and how it was fixed forward)

`tests/rust_theme_chooser_qemu.py` previously asserted `calls() == [["list"]]`
after ordinary browsing (a drag, then a side-tap) -- literally "browsing
must never call preview". Task 3.2 makes that no longer true by design: a
theme dwelled on during browsing now *does* trigger a background `preview`
call. Confirmed by running the test unmodified first (it failed exactly
there: `AssertionError: a side-slice tap must only browse, never confirm`,
log showing `["preview","...06"]`/`["preview","...07"]` from the warm-up),
then updating the assertions to the real invariant that still must hold
("browsing must never select a background or activate", not "browsing must
never call preview at all") -- see `browse_calls_are_safe` in that file.
The updated test additionally *proves* 3.2 fires (`assert any(row[0] ==
"preview" ... for row in calls())`) rather than merely not-breaking.

### 6. A pre-existing, unrelated flake noted, not fixed

`tests/test_paired_theme_endpoints_runtime.py` timed out on this dev host
at `wait(expanded_app, 5)` (a card "back"-navigation animation settle,
nothing to do with appearance/theme code) under sustained high host load
(`uptime` showed `load average: 23-28` on a 32-core host, from concurrent
Nix builds run by other agents in this shared repository per
`tools/work-status.py`). Reproduced identically against an **unmodified
`master`** build of the same test (`.#card-shell`/`.#handheld-shell-rust`
built from `origin/master` `64c38998`), confirming this is host contention
on this dev machine, not a regression from this change. Not fixed here;
worth a retry on a quieter host or with a longer timeout if it recurs.

## Board commands for the coordinator (tasks 2.3 and 3.4, unchanged gate)

Unchanged from `docs/evidence/omarchy-themes/theme-swap-jank/README.md`'s
own "Board commands for the coordinator" section -- this change adds no
new board-only step, only more to look for once run:

```sh
./tools/console.py /dev/ttyACM0 --wait=3 \
  "python3 /path/to/tools/theme-swap-jank.py --theme-id catppuccin-latte --duration-after-s 3"
./tools/console.py /dev/ttyACM0 --wait=3 "cat /run/theme-swap-jank-<epoch>.json" > /tmp/after-3.1b-3.2.json
python3 tools/analyze-theme-swap-jank.py --input /tmp/after-3.1b-3.2.json --output /tmp/after-3.1b-3.2-report.json
```

In addition to the existing `tap_to_visible_ms`/gap-histogram checks, the
coordinator should now also see, in the board's own
`journalctl -u shell-ui -u shell -o json` output that
`tools/theme-swap-jank.py` already merges:
- `rust-shell <ms>ms appearance-prepare-accepted` and
  `appearance-commit-accepted` close together (a near-instant gap between
  them means the wallpaper decode was a cache hit, not a fresh decode);
- `K230_CARD_SHELL appearance-canvas-gradient-adopted` rather than `-built`,
  for any theme whose deck canvas is an authored gradient, if the person
  dwelled on it in the chooser before applying it;
- for a swap performed by tapping a theme that was *not* dwelled on first
  (a fast, deliberate double-tap), `-built`/a real decode gap is still
  expected and correct -- this change only removes the *repeated or
  avoidable* cost, never the first, unavoidable one for a theme nobody
  looked at first.

Neither this change's task 2.3 nor 3.4 board run has been executed by this
worktree; `/dev/ttyACM0` was not opened here.
