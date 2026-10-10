# Theme preparation admission closeout — 2026-10-10

Task 13.3's two named host commands pass: seven preparation cases and one
row-motion test covering held, coasting and settling states separately for each
of the two real production carousels. The host theme-UI compatibility suite
passes 28 tests and all 22 binary route tests pass. [Provenance](provenance.json)
records exact commands, source revision, log hashes and filesystem observation
timestamps. These are source/host and cross-build proofs, not board proof.

```sh
CARGO_TARGET_DIR=/home/jadams/tmp/k230-admission-host-target \
cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml --lib prepare_ahead
CARGO_TARGET_DIR=/home/jadams/tmp/k230-admission-host-target \
cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml \
  --bin k230-shell-rust speculative_theme_motion
```

[Preparation output](prepare-ahead-host.log), [row-motion output](speculative-motion-host.log),
[theme-UI compatibility](compatibility-theme-ui.log), [route compatibility](compatibility-routes.log).

## Existing implementation and remaining priority correction

Commit `f4bf213eccfe84102c584460f24a3a44cc494e95` already added
`poll_prepare_ahead_at_rest` and called it with the production both-row motion
decision. The September 28 audit predates that implementation; its assertion
that task 13.3 has no source or targets is historical, not the current state.

That implementation preserves the neighbor queue and running request ID during
motion, resets obsolete center dwell, blocks a successor even when a reply
finishes during motion, and preserves foreground-request protection. Existing
host cases verify those behaviors, no-center neighbor fallback and reply identity.
The binary regression now feeds the actual held/coasting/settling decision for
each row into the production admission API and proves eligibility resumes once
the motion finishes. The other row stays at rest in each of those six cases.

The old source could nevertheless admit a queued neighbor during a newly settled
center's dwell, delaying the center and using the single prepared slot first.
The new [test-only old-source control](old-center-control.patch) reproduces this:
[actual failure](old-center-control.log), [source/command identity](old-center-control.json).
The control uses unchanged base product logic with only the new regression test
added; it is not a frozen product build. The same test passes after the fix.

The free slot now waits through the latest valid center's dwell before optional
neighbors resume. An active or absent center still permits the established
neighbor fallback. No running warm-up is canceled, and explicit Preview/Activate
keeps priority. The regression preserves the two-item queue across 200 motion
polls and direction changes, verifies dwell restarts for a new settled center,
checks single-flight behavior, then permits a neighbor after the center reply.
No pointer publication, appearance acknowledgement or motion physics changed.

## Cross-build and retention

The guarded [component build](component-build.log) passes and produces:

`/nix/store/x69mg9sdfbk6m3m25gi80f2s083c7nwk-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0`

The copied source, Cargo manifest and lock match committed source:
[input comparison](input-comparison.json). This task changes neither the manifest
nor the lock. The initial plan requires 53 derivations: the Rust client, its
vendor aggregation and missing Cargo source-fetch/unpack outputs. It does not
rebuild the graphics stack, kernel or image. Nix's Rust package compiles its
locked Rust dependencies inside the changed package build.

The selected vendor output is identical to that used by the previous live-fixture
Rust package but was outside the prior 10,266-path retention farm. This proves a
coverage gap, not a particular historical GC deletion. The [verified receipt](retention.json)
extends the prior farm to 10,357 currently valid paths,
including the selected Rust vendor sources, package output and derivation inputs.
Actual root queries protect both the client and vendor output. The durable root
is `~/.local/state/tdisplay-k230/retained-builds/theme-admission-2026-10-10/build-closure`;
the separate `rust-client` root also retains the built package. Prior roots and
global GC policy are unchanged; unrealized outputs are not built for pinning.

## Ownership and remaining gates

Worktree `/home/jadams/tmp/k230-theme-admission-closeout-2026-10-10`, branch
`closeout/theme-admission-2026-10-10`, base `9c8f2321`, source `91943f89587da3f1869c905c25f2039b7c17d370`.
Owned paths: `nix/rust-shell-client/src/theme_ui.rs`, `src/main.rs` in that package,
this evidence directory, the theme-swap task record and its work-board override.
The temporary `/tmp/k230-nix-build.lock` build reservation is released.
No board or serial reservation was taken; the new package is not installed.

The theme-swap proposal is 65/81 complete and remains open. Task 13.3's source
scheduling gate is complete; the matched workload harness, cost attribution and
three-pair physical comparison remain tasks 13.1, 13.2 and 13.4. The latter's
planned operator command stays `python3 /run/theme-picker-profile.py capture
--plan /run/picker-plan.json --output /run/picker-profile.json` after that harness
exists, with a reserved board and exact baseline/candidate identities. That tool
is still a planned interface here. The source fix does not substitute for that
trial, install a new board package, quantify latency or claim real-finger feel.
Existing user acceptance is preserved separately; no repeat confirmation is asked.
