# Optimistic Apply: show an already-prepared theme ahead of the durable commit

Implements OpenSpec task 7 from
`openspec/changes/the-shell-swaps-themes-without-a-python-stall/tasks.md`,
against the user's explicit approval (2026-09-25 coordinator message: "The
user has explicitly approved the optimistic theme apply") of the design the
change's `design.md` records in full. This is a **host-only** result: no
board, glass, or real-finger observation. Worktree
`perf/optimistic-theme-apply`, base `master` `600171bc`.

## Starting point

Board re-check after skipping the redundant prepare
(`docs/evidence/omarchy-themes/instant-theme-swap/board-chooser-2026-09-25.md`'s
own "Re-check after skip-redundant-prepare" section, system
`v84gna5s1qnabg5mqhwa55anml2q8amh...`, master `bc0cf82f`): tap Apply -> Rust
`appearance-commit-accepted` 397 ms, helper `parse=2.2ms prepare_entry=
63.0ms activate_generation=226.2ms`. Still short of the user's original
~100 ms target ("theme swaps should be instant"); the remaining cost is
`activate_generation`'s own durable pointer-swap/preference/app-sync work,
none of which can be skipped without risking the transaction's own
correctness.

## What changed

- `nix/rust-shell-client/src/main.rs`:
  - `should_apply_optimistically(request, prepared_generation)` -- pure:
    true only for an `Activate` request whose `expected_generation` exactly
    matches the local `AppearanceReceiver`'s own `prepared` snapshot.
  - `optimistic_apply_due(already_attempted_for, pending_id)` -- pure:
    true exactly once per fresh `pending_id`, so a still-pending Apply is
    never re-checked tick after tick and a rapid second Apply (its own
    fresh, higher id) is never suppressed by the first's bookkeeping.
  - `show_theme_optimistically` -- renders an already-prepared snapshot
    through the same `draw_wallpaper`/`draw`/flush calls the real commit
    path already uses, skipping only for a video-backed selection, an
    unrenderable snapshot (defensive), or an overlay not immediately ready
    for a new frame. Logs `rust-shell <ms>ms optimistic-apply shown
    ms=<tap-to-frame>`. Never touches `AppearanceReceiver`'s own
    `prepared`/`active` bookkeeping or the `Activate` request already
    dispatched to `ThemeWorker` -- both are left entirely to the real,
    unmodified `AppearancePhase::Commit`/`Rollback` handling to settle
    authoritatively (including reverting the display and surfacing an
    error via `ThemeView::accept`'s existing `Err` handling on failure).
  - `show_appearance_optimistically` -- a best-effort, fire-and-forget
    "show" message to the card-shell compositor's own appearance socket
    (`K230_CARD_APPEARANCE_SOCKET`, defaulting to `nix/shell.nix`'s
    existing `SWAY_K230_CARD_APPEARANCE_SOCKET` production path), sent
    *after* the local render/log so a slow or unreachable compositor never
    inflates the logged latency.
  - `ShellClient` gains `theme_apply_tapped_at`, `theme_optimistic_shown_
    for`, and `card_appearance_socket`; `submit_theme` records the tap
    instant and resets the per-Apply attempted-marker whenever a fresh
    `Activate` is submitted; `serve`'s own loop checks `optimistic_apply_
    due` once, right after Wayland event dispatch (the same tick a
    touch-up already ran `theme_action(ThemeIntent::Apply)` in).
- `nix/card-shell/appearance.c`: an additive `"show"` protocol phase.
  Renders `service.candidate` immediately when it is already `service.
  prepared` and matches the requested id/path, with the same best-effort
  restore-on-apply-failure as the existing `commit` branch, but never
  touches `service.prepared`/`service.candidate_path`/`service.current` --
  a subsequent real `commit` or `rollback` for the same candidate is
  unaffected by whether `show` was ever sent, was late, or was duplicated.

## Why this is safe (see `design.md`'s own "Optimistic Apply" section for the full reasoning)

A receiver only ever holds a `prepared` candidate after it has already
validated that candidate byte-for-byte via the same checks a real `prepare`
exchange runs. Rendering it early therefore risks nothing a real `prepare`
ack would not already have accepted. The optimistic render is *stateless*
with respect to the durable transaction -- it reads `prepared`, renders,
and is done -- so there is nothing to reconcile if the two ever disagree:
the real `commit`/`rollback` event, unaware optimism ever ran, always wins
and settles the receiver's actual state and the visible appearance
correctly, including on a durable failure.

## What was deliberately not done

- **The wire acknowledgement contract is unchanged.** No `prepare`/
  `commit`/`rollback` exchange's own success criteria, or the "ack only
  after a real, flushed frame" rule, changed in any way. `proposal.md`'s
  own "What This Does Not Do" section is revised to say this precisely
  (its earlier wording read as ruling this whole feature out permanently).
- **The compositor fanout is not wired into production here.** `theme-
  helper.service`'s `--rust-socket`/`--deck-socket` flags are not passed
  in `nix/shell.nix` on this branch's base (`master` `600171bc`) -- that is
  a separate, not-yet-landed integration (see this repository's own
  `impl/card-appearance-endpoint` worktree). The compositor's `show`
  phase and `main.rs`'s sender are therefore correct and tested in
  isolation, but dormant in production until that fanout lands; sending
  `show` to an unreachable/not-listening compositor is silently ignored,
  by design.
- **A genuine touch-driven QEMU proof was not built.** The existing
  `tests/rust_theme_chooser_qemu.py` harness stands in a synthetic
  `K230_THEME_COMMAND` script for `k230-theme`, which never runs the real
  two-phase protocol against the real `AppearanceReceiver` socket -- so
  `appearance.prepared()` is never populated there and this feature's own
  code is structurally unreachable in that harness (every Apply in it is
  effectively "cold" from the receiver's point of view, which is also
  why running it unmodified is still a valid regression check -- see
  below). A harness combining real touch injection with the real `theme-
  helper`/two-phase backend (closer to `tests/test_theme_commit_under_
  occlusion_runtime.py`'s own real-CLI approach) would be needed to
  exercise `should_apply_optimistically` end to end under QEMU, and was
  not built in this task given the time this stage already spent; this is
  named here as an explicit gap, not a claimed pass.

## Test-suite proof

- `cargo test --offline` (nix/rust-shell-client): 159+9+14+8+8+5 = 203
  cases, all passing. New: `route_tests::optimistic_apply_fires_only_for_
  an_activate_matching_the_prepared_generation` (warm/cold/mismatched/
  non-Activate-request cases for `should_apply_optimistically`),
  `route_tests::optimistic_apply_due_is_scoped_to_each_fresh_pending_id_
  for_a_rapid_double_apply` (the rapid-double-Apply scoping property),
  `theme_ui::tests::a_failed_activate_clears_pending_and_surfaces_a_
  visible_error` (the existing, unmodified `Err`-reply handling proven
  specifically for an Activate reply, not just Preview/background).
- `python3 -m unittest tests.test_card_shell_appearance`: 10 cases (7
  pre-existing + 3 new), all passing against the real, compiled
  `appearance.c` over a real Unix socket (built with `-Werror`, so the new
  C branch itself is warning-clean). New:
  `test_show_renders_a_prepared_candidate_without_disturbing_the_two_
  phase_state` (show renders, twice, then a real commit for the same
  candidate still succeeds -- proving `show` never cleared `prepared`),
  `test_show_is_rejected_for_a_generation_that_was_never_prepared`
  (cold and mismatched-id cases both rejected, connection never blocks),
  `test_show_never_blocks_a_later_rollback_from_restoring_the_previous_
  generation` (show, then a real rollback still restores the previous
  generation's own pixels/palette).
- `python3 tools/blob-scan.py`: exit 0 ("every binary is accounted for").
- `openspec validate the-shell-swaps-themes-without-a-python-stall
  --strict`: valid.
- `nix build --no-link --print-out-paths --max-jobs 1 --cores 6
  .#handheld-shell-rust .#card-shell .#handheld-theme-command
  .#handheld-theme-default .#card-composition-probe`: all five built
  cleanly for riscv64 (exit 0), including `card-shell`'s own build of
  `sway-unwrapped`/`sway` against the new `"show"` branch in
  `appearance.c` -- the real C cross-compile check for that change, not
  just the host `cc -Werror` build the unit tests above already ran.
  Output paths:
  `/nix/store/j8fnc6jr4hhsvp3hff9k2hjjy7k2d9il-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0`,
  `/nix/store/1va4angandva4xbm5i0v7367p0nd9jry-k230-card-shell`,
  `/nix/store/nh386rn5qkdbcl11lqyxx538s4mc2niv-handheld-theme-command-0.1`,
  `/nix/store/1dqfry706fj780v5byiklmaawakwphid-handheld-theme-default-28ceaae7`,
  `/nix/store/ih8mq5lq53w7p8mcv6aarz6z55il0f4s-k230-card-composition-probe`.
- `nix eval .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel.drvPath`:
  evaluates to
  `/nix/store/2j8yam3w04lhj3qhhssi0hyp8m1awip0-nixos-system-nixos-26.11.20260919.20b1ddd.drv`,
  no eval error.

## Board commands for the coordinator (task 7.4)

```sh
journalctl -u shell-ui -u shell -o json --since "-2min" \
  | grep -E "optimistic-apply|appearance-(prepare|commit)-accepted|appearance-commit-rejected"
```

Steps: Settings, Themes, dwell on (or swipe to a neighbour-warmed) a
non-active theme long enough for its own prepare-ahead to land, then tap
Apply. Expected on a warm Apply: an `optimistic-apply shown ms=<N>` line
appears before (or very close to) the durable `activate`'s own reply, and
`<N>` is the number to compare against the ~100 ms target. Expected on a
cold Apply (a theme the chooser never had time to prepare ahead): no
`optimistic-apply shown` line at all, and the pre-existing busy-state
behaviour. For the failure/rollback scenario, the coordinator's own
existing failure-injection approach (see
`docs/evidence/omarchy-themes/instant-theme-swap/board-diagnosis-2026-09-24.md`/
`tests/test_theme_commit_under_occlusion_runtime.py` for the shape of a
reproducible commit failure) should show a subsequent `appearance-commit-
rejected` and the wallpaper/chooser visibly reverting to the previous
theme with an error message, never settling on the optimistically-shown
one.
