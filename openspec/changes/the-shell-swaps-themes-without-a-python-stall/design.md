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
