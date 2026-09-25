## Layer

Userspace: `tools/` (Python theme coordinator) and `nix/shell.nix`
(systemd). No kernel, device tree, stage-1, or Rust/C shell change.

## Design

`tools/theme_catalog.py`'s CLI already had exactly the logic a persistent
helper needs to reuse: `build_parser()` (extracted from `main()`, no
behavior change) and `handle(args) -> (result, exit_code)` (also extracted,
same). `tools/theme_helperd.py` binds a private Unix socket
(`/run/shell/theme-helper.sock`, mode 0600, directory 0700, `SO_PEERCRED`
uid check -- the same posture as the existing appearance sockets) and, per
request, reconstructs an argv (its own fixed startup flags plus the
request's action-specific bits) and calls that exact parser/handler. This
means the daemon's behavior for any single request is provably identical to
running `theme_catalog.py` fresh with the same flags: there is no second,
hand-rolled protocol for `preview`/`activate` semantics to drift from the
one already reviewed and evidenced in `tests/test_theme_catalog.py`.

`tools/theme_client.py` is the only piece with a real design decision:
whether to import `theme_catalog` up front, for the sake of one shared
parser. Doing so would have re-imported `theme_activate`, which
board evidence already named as most of the cost this whole change exists
to remove. Instead `theme_client.py` carries a *second*, deliberately
minimal `argparse` parser (`build_light_parser()`) whose only job is to
recognise the request shape (action, id, `--background`,
`--expected-generation`) well enough to build a socket request; any flag it
does not confidently recognise, any parse failure, or a missing/refused/slow
socket sends the call to `fallback()`, which imports `theme_catalog` and
runs the exact original path. The two parsers can disagree at the margins
(e.g. the light parser does not itself enforce `--expected-generation`
being required) without being unsafe, because disagreement only ever
degrades to a slower or more verbosely-erroring identical answer, never a
different acceptance decision -- the *daemon's* copy of `theme_catalog`'s
real parser is what actually validates and acts on every request, whichever
path reached it.

## Optimistic Apply (2026-09-25, user-approved)

Board evidence after task 6.3's skip-redundant-prepare fix still showed
397 ms from Apply tap to the Rust shell's own commit-accepted marker --
short of the user's original ~100 ms target. The remaining cost lives
inside `activate_generation()`'s own durable work (the atomic pointer
swap, missing-public-link creation, `fsync`, the wallpaper preference
commit, and the app-sync round trip), none of which can be skipped or
reordered without risking exactly the correctness this protocol exists
for. Rather than continue trimming that durable path, the user approved
showing the new appearance immediately when it is already safe to do so.

**Why gating on "already prepared" is sufficient for correctness.** A
receiver only ever holds a `prepared` candidate after successfully
validating it byte-for-byte against the same `load()`/`load_snapshot()`
checks a real `prepare` exchange already runs (bounds, symlink rejection,
generation-identity match, palette/background integrity). Rendering that
already-validated candidate early therefore risks nothing a real `prepare`
ack would not already have accepted -- there is no new, less-trusted data
path. What optimism cannot know in advance is whether the *durable* commit
will actually land (a second receiver's commit can still fail, the app-sync
step can still fail); that is why the optimistic render never touches a
receiver's own `prepared`/`active` bookkeeping or the wire acknowledgement
contract at all (see `nix/rust-shell-client/src/main.rs`'s
`show_theme_optimistically` and `nix/card-shell/appearance.c`'s new `show`
phase, both pure rendering side effects). The real `commit`/`rollback`
event -- unmodified, still gated on a real flushed frame the same as
before this task -- is what settles the receiver's actual state
authoritatively; a failed durable commit's own existing rollback handling
is what makes the screen correct again, not new code this task adds.

**Why the client-side check, not a server-side flag.** `should_apply_
optimistically`/`optimistic_apply_due` (`main.rs`) are pure functions
comparing the just-submitted `Activate` request's own `expected_generation`
against the *local* receiver's own `prepared` snapshot -- no round trip,
no new IPC for the primary (Rust-surface) case, since the chooser and that
receiver are the same process. This is why the target generation must
already be prepared *in this same process*: nothing here can safely infer
that a remote receiver (the compositor) is also warm, which is exactly why
the compositor side is deliberately advisory/best-effort (see below)
rather than a precondition this feature waits on.

**The compositor's `show` phase.** A new, additive protocol-1 phase in
`nix/card-shell/appearance.c`'s `request()`: renders `service.candidate`
immediately when it is already `prepared` and matches the requested
id/path, exactly like the existing `commit` branch's own render call, but
never touches `service.prepared`/`service.candidate_path`/`service.
current` -- so a subsequent real `commit` or `rollback` for the same
candidate behaves identically to a world where `show` was never sent.
Sent best-effort, fire-and-forget, from the Rust chooser directly to the
compositor's own socket (`K230_CARD_APPEARANCE_SOCKET`, defaulting to
`nix/shell.nix`'s existing `SWAY_K230_CARD_APPEARANCE_SOCKET` production
path) with a short write deadline and no reply read; any failure (socket
missing, refused, a rejected mismatch) is silently ignored. This channel
is presently reachable only once the two-phase transaction's own
`--rust-socket`/`--deck-socket` fanout is wired into `theme-helper.service`
(tracked separately, not by this task); until then it is dormant, correct,
and tested in isolation, not a regression risk.

**Rejected: relaxing the wire acknowledgement contract itself** (e.g.
having a receiver ack `prepare` early, or ack `commit` before its own
frame is flushed). Rejected because that contract is what task 1's own
instrumentation and every existing transaction test assume; loosening it
would have widened this task far past "show something already known-good
early" into "change what every receiver promises," for a benefit this
narrower design already captures.

**Rejected: an optimistic-shown flag inside `ThemeView`/the durable
transaction, coordinated across processes.** Would need new state
(un)winding on every possible interleaving (rapid double Apply, a
receiver restart mid-flight, a stale prepared-state assumption already
handled defensively in task 6.3). The chosen design needs none of that:
the optimistic render is *stateless* with respect to the durable
transaction (it reads `prepared`, renders, and is done), so there is
nothing to reconcile if the two ever disagree -- the real commit/rollback
event, unaware optimism ever ran, always wins.

## Rejected alternatives

- **Rewrite `k230-theme` as a long-running client that keeps a persistent
  connection open.** The chooser already treats each `preview`/`activate`
  as a discrete, synchronous call with its own timeout and error handling
  (`tools/theme_transaction.py`); keeping a stateful connection open across
  taps would have added reconnect/staleness handling for no benefit a
  request-per-connection socket does not already give.
- **Move `discover()`'s theme-source walk into a file-watch cache instead
  of a daemon.** Would only address the discovery/list cost, not the
  import cost itself (which dominates per the board's own
  `PYTHONPROFILEIMPORTTIME` breakdown), and adds a staleness class (a
  theme added on disk after the cache was built) this change's approach
  does not have, since the daemon simply calls the unchanged, always-fresh
  `discover()` per request.
- **Trim `theme_activate.py`'s own imports (e.g. defer `dataclasses`).**
  A real, smaller, complementary win left as a follow-up; it reduces the
  daemon's own one-time start-up cost, not the per-call cost this change
  targets, since the daemon already pays that import cost exactly once.

## Verification

`tests/test_theme_helper_daemon.py` proves: byte-identical `list`/`preview`
output through the daemon versus the direct path; a real `preview`+
`activate` reaching `theme_transaction.activate_generation`'s actual
prepare/commit exchange (not a stub) with the daemon in the loop; a
malformed request never wedging the daemon for the next real one; the
client falling back correctly when no daemon is listening; and, via a real
subprocess with `python3 -X importtime`, that `theme_catalog`/
`theme_activate`/`theme_transaction`/`theme_preferences`/
`keyboard_appearance` are never imported by the client process on the
daemon-reachable path. `nix build .#handheld-theme-command` builds the
real riscv64 package; running its `k230-theme-helperd`/`k230-theme` under
`qemu-riscv64-static` on this host measured 5 sequential `list` calls at
1.148 s/call with no daemon versus 0.785 s/call with one running (about a
32% reduction) -- directional only, since qemu-user translation overhead,
not the K230's in-order core, dominates this host's absolute numbers.
