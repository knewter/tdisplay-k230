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

## Both carousel working sets and movement (2026-09-26)

The user reports slow theme-picker swipes and apparently repeated loading on
source `926c7a61`. This report is not a measured diagnosis. Source review
finds that the merged one-page picker requests both thumbnail variants for
up to 17 themes and 17 backgrounds, while the shared FIFO cache holds only
36 entries. That bound was justified for one carousel, before both moved to
the same page. With 17 themes and just two backgrounds, stationary demand
already exceeds capacity. Eviction followed by unconditional requests can
repeat disk loading/hashing or decoding without any content change.

Keep the bounded cache; derive one working set for both carousels from
viewport-intersecting slices, with centered-first scheduling and controlled
admission. Use the same set for requests and pending-work decisions, and
protect its resident entries from obsolete in-flight replies. Retain the
existing 36-entry bound and add an explicit 24 MiB resident-pixel bound,
rather than making the cache arbitrarily large. This bounds ready thumbnail
surfaces, not total process RSS; the existing bounded worker queues and decode
cache remain separate. Offscreen layout and hit-testing remain unchanged. Also defer the
optional, synchronous candidate-overlay pre-render until neither carousel
is dragging, coasting, or settling. This changes speculative work scheduling,
not live rendering or the durable appearance protocol.

A host regression must begin with a two-carousel catalog whose old request
set exceeded 36 entries, then prove the new admitted set warms and reaches
quiescence (no continual requeues/evictions), stays bounded while moving, and
retains center priority. A motion-gate test must cover both carousels and
show pre-render becomes eligible again at rest. Physical responsiveness is
still UNVERIFIED: after the panel trial, compare cold/warm swipes, idle
loading activity, frame gaps and process CPU on the exact installed build.

## Preserve active bundled-theme lookup across store relocation (2026-09-27)

The second picker trial preserved the active generation but native capture
showed a permanent `Loading backgrounds` row; all four injected background
drags reached Rust yet produced no commits. Existing `selected()` compares
only the active report's source pathname with current catalog paths. A Rust
thumbnail-tool rebuild also rebuilds the bundled-theme derivation, changing
its store path even when theme files are identical. A missing active catalog
ID makes the chooser select index zero without requesting active backgrounds.
This precedes the thumbnail working-set change; that rebuild exposes it.

Keep exact-path matching first. For an unmatched source, recognize only a
unique built-in entry with the same bundled `/share/omarchy/themes/NAME`
location beneath a Nix store object and the exact source-content digest in
the active report. Do not match user themes by display name, guess between
multiple entries, or write the active pointer. Missing/changed content remains
unmatched. Host fixtures must prove relocation, exact-path priority, and
rejection of changed content, another origin, malformed identity and ambiguity.
A physical repeat must show the actual background row and unchanged durable
generation before using its swipe/memory measurements as comparable evidence.

## Measure remaining swipe cost and admit speculative work only at rest

The [paired browsing observation](../../../docs/evidence/theme-picker/working-set/README.md)
proved that speculative overlay completions during held touch fell from five
to zero, but did not prove smoother warm browsing: warm commit-gap median
was 125 ms before and 132 ms after, and maxima were 258/285 ms. Both idle
windows were quiet. The second run had no resolved background row, so its
lower final RSS and reopening cost cannot establish an equal-content win.
Task 12.2's relocation repair must first restore that row. Task 11.3 stays
open; these observations are neither physical-finger acceptance nor a cold
cache comparison.

Two remaining costs need separate attribution. `theme_dirty()` invalidates
`RendererCache`'s full cached scene whenever carousel position changes, so
live movement rebuilds the panel, including unchanged content. Meanwhile,
`poll_prepare_ahead()` can drain queued neighbor requests when `centered` is
`None`: movement suppresses dwell selection but not all speculative request
admission. Helper cgroup CPU overlapped several new warm swipe windows at
roughly 33–39%; a preparation included about 2.8 seconds of wallpaper-cache
work and 1.5 seconds of template rendering. These facts identify work to
measure, not proof that either cost alone explains each frame gap.

Add bounded, opt-in profiling that distinguishes the Rust main thread from
thumbnail workers, helper subprocesses from the daemon, and CPU time from
elapsed waiting. Record live rebuild count/time, thumbnail request/completion
and hash/read/decode phases, appearance-prepare handling, speculative
submission/completion, and overlay pre-render separately. Use monotonic phase
markers and aggregate counters or bounded buffers; avoid per-pixel logging or
unbounded journals. Default rendering stays uninstrumented. Collect native
media in a separate pass and compare instrumentation-on/off observer cost.

Make speculation eligibility explicit: while either carousel has a contact,
coast, or settle, admit no new dwell or neighbor preparation. Pause admission
without consuming the queued neighbor or expanding its bound, reset the
center dwell appropriately, and resume with the latest settled center before
optional neighbors. A request already executing may finish and consume CPU;
account for its full lifetime rather than treating the admission gate as
cancellation. Its completion cannot trigger another speculative request
while movement continues. Preserve foreground preview/activation priority,
request identity checks and the single prepared-slot transaction rules.
The existing overlay pre-render motion gate remains a separate protection.

Compare a baseline containing the relocation and thumbnail fixes with only
this admission change added, using the same visible catalog, selected theme,
background row, kernel, compositor, geometry and background playback state.
Record process/cache history explicitly. Per-thread/phase data decides the
next rendering change; a broad renderer rewrite, new toolkit, CPU affinity or
compositor replacement is outside this task group. If live repaint remains
dominant after speculation is bounded, retain that measured remainder here
instead of marking swipe acceptance complete.

## Direct manipulation follow-up (operator report, 2026-09-26)

`theme_carousel.rs::motion` divides finger displacement by collapsed-slice
pitch (49 pixels for themes, 43 for backgrounds). The focused card's center
travels 255 or 223.5 pixels in the corresponding first index transition.
The existing unit test asserts index displacement and therefore misses visible
amplification. Derive input mapping from the rendered layout and test actual
card-center displacement, including fractional positions and reversals; do
not relabel a slot-count assertion as screen-space tracking. Keep a stable
reference card during a contact and invert its piecewise center trajectory so
it follows displacement across transitions. Apply the matching local scale
to release velocity, and age that velocity explicitly when release follows
a hold. End-of-list clamping remains bounded.

For the Themes page only, defer touch-motion and frame-callback redraws to
the event loop after queued Wayland events have updated the latest position.
Respect buffer/frame readiness and preserve immediate tap feedback, foreground
activation, and other shell routes. A coalesced intermediate frame is useful;
rendering every obsolete sample is not. The board comparison must distinguish
mapping, input backlog and render cost. Real-finger acceptance remains open
until the operator actually tests the candidate; injected motion can prove
geometry and accounting but cannot substitute for that observation.

### Picker frame-stall attribution

Task 13.2's opt-in trace will give overlay commits monotonic frame IDs and
request Wayland presentation feedback for those exact commits. Keep callback,
commit, feedback-receive and compositor-provided presentation timestamps
separate, including clock ID, refresh period, sequence, flags and discarded
submissions. Only compare presentation timestamps with input/process clocks
when their clock domains match; absent feedback is unavailable evidence.
Record main-thread render/rebuild/copy and background work spans with both
wall time and thread CPU time, plus the latest picker input sequence. Buffer
only a bounded, numeric/allowlisted trace in memory and write it after the
capture interval. Trace mode is off by default; measure observer overhead.
A report ranks individual stalls within named swipe phases, excludes idle
intervals, and shows which spans overlap each stall without treating overlap
as proof of causation. Screenshots/camera captures run separately from timing.

### Correlated runtime tracing and CPU profiles

The same opt-in recorder will cover shell rendering and theme-helper work,
using a shared trace ID, process/thread identity, nested span IDs and remote
parent IDs on the existing helper socket. Fixed event names and numeric data
exclude theme names, paths, request bodies and credentials. Export uses
Perfetto-compatible trace events; this is a local diagnostic format, not an
OTLP collector or a claim of complete system coverage. Missing components,
dropped events, truncated spans and clock mismatches must remain visible.

CPU flamegraphs require sampled stacks, separately from nested span timelines.
Probe the running kernel and perf support before selecting a bounded sampling
command; keep raw stacks private until reviewed, retain build/symbol identities,
and report unsupported unwinding explicitly. Extend coverage to compositor
render/commit/presentation and kernel scheduling only with verified hooks and
clock alignment. Compare tracing disabled/enabled and sampling separately so
observer cost cannot masquerade as a regression. The picker is the first
workload; these formats and tooling should also support cards, launch, drawers
and theme activation without a new profiler for every feature.

### Background selection generation and feedback correction

A generation hashes the selected background as well as theme contents.
The current preview's generation therefore cannot authorize a different
background. A single background tap must chain a Preview for that exact
background into Activate with the returned generation. No second user tap
is required. Retain the current selected marker until acknowledged commit;
show Applying beside the background row, then Applied to Home or a visible
failure. The catalogue's current theme/generation follows acknowledged
activation so later taps do not mistake an old theme for the current one.
Physical background/Home agreement is recorded with injected touch and native
captures in `docs/evidence/theme-picker/background-selection/README.md`.
Real-finger acceptance remains UNVERIFIED for this correction.
