# Tracking cadence: the render allowance is not a demonstrated fix

Five installed-board diagnostic arms ran from **2026-10-21 04:58:48Z to
05:00:41Z**, under the source3 exclusive board reservation, over protected SSH.
The runtime source is `d39abadfab3fb4e6c0d8d201d06d9a82a73d22ad`, with the
same installed compositor and persistent system as the [parent trial](../README.md).
This comparison keeps the original still background and landscape output;
it does not repeat the paired-video gate or establish real-finger acceptance.

The board's normal `max_render_time 8` setting was compared with a temporary
`max_render_time 12`, followed by a return to 8. A larger value starts rendering
earlier before the predicted refresh; it does not change the panel refresh rate.
There was no build, service restart, boot change, or persistent configuration edit.
The existing flicker fix was not disabled. A root systemd timer independently
restored 8 ms after 300 seconds if the controller failed; normal cleanup stopped
that timer after verifying restoration.

## Workload and results

Every arm used six alternating 250-pixel horizontal drags, each with 35 motion
steps over 700 ms, a 50 ms initial hold, and 800 ms between releases. Input is
one persistent uinput device with measured touch-controller axes. The three-card
arms added two temporary Foot clients to the normal startup terminal; the
one-card arms used only the startup terminal. These are native touch-route
injections, not IPC gesture substitution, human contact, or optical timing.

| Arm, in execution order | Cards | Render allowance | CPU update p95 | Correlated tracking p95 | All-present p95 during motion |
| --- | ---: | ---: | ---: | ---: | ---: |
| a8 | 3 | 8 ms | 7.369 ms | 38.310 ms | 38.309 ms |
| b12 | 3 | 12 ms | 7.473 ms | 38.311 ms | 38.309 ms |
| a8-return | 3 | 8 ms | 7.937 ms | 38.312 ms | 38.312 ms |
| a8-one | 1 | 8 ms | 4.482 ms | 19.186 ms | 19.161 ms |
| b12-one | 1 | 12 ms | 4.462 ms | 38.310 ms | 19.162 ms |

The frozen correlated tracking threshold remains **p95 33.334 ms**, maximum
100 ms. Every three-card arm fails that p95. The 8 ms one-card arm passes all
numeric metrics in this short run; it does not erase the earlier one-card
failures or close task 3.3. All-present intervals are a separate diagnostic,
not a substitute acceptance metric. The formal board parser still reports its
portrait-only geometry requirement because the operator selected landscape.

The 12 ms three-card arm also has maximum input-to-submit **138.937 ms** and
input-to-present **144.487 ms**, exceeding the unchanged 100/133.334 ms maxima.
Its input dispatch gap reaches **141.592 ms**, and the frozen analyzer excludes
three tracking intervals bridged by input pauses over 50 ms. Those pauses and
the raw long presentation gaps remain in the evidence; they are not hidden by
the p95 table. The comparison does not identify their cause or establish that
the render setting caused them.

## What this narrows

Most presentations still occur one refresh apart, about 19.16 ms. The p95
failure is a tail of longer gaps, rather than a fixed half-refresh-rate cap.
The frozen tracking metric includes presented frames associated with new motion
input, while an intermediate frame can present without such an association.
In the 12 ms one-card arm, **11 of 16** above-budget correlated intervals have an
intermediate actual presentation. By comparison, **none of the 34** slow
correlated intervals in the returned 8 ms three-card arm have one. Both input
representation and actual presentation gaps matter; neither observation alone
proves a kernel commit bottleneck.

The captured repaint CPU subdivision is small: three-card render p95
6.320–6.650 ms, scene-build p95 5.293–5.536 ms, commit CPU p95
0.291–0.296 ms. These are CPU charges, not elapsed render time or kernel
completion latency. Giving the compositor four additional milliseconds did
not demonstrate a gate-passing improvement, so **8 ms is restored**. This
does not justify retrying the older boot-panic-producing register-latch patch.
The next useful diagnostic is elapsed render/commit/scheduler correlation on
the current runtime, before proposing any kernel timing change.

## Reproduction and restoration

The exact installed-board driver is [run-board.py](run-board.py), using
[collect-board.py](collect-board.py), [cadence_audit.py](cadence_audit.py), and
the source revision's `tools/card-shell-board-session.py` normalizer. The
driver was staged as `/run/shell/source3-cadence-20261021/run.py` with its
collector named `collect.py`. With the board reservation and the protected
SSH configuration, the operator command was:

```sh
ssh -F /home/jadams/tmp/k230-coordination/ssh_config.private k230 \
  /nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3 \
  /run/shell/source3-cadence-20261021/run.py
```

The historical path is retained after the run, so the driver deliberately
refuses to reuse occupied result directories. A future run needs a fresh owned
staging directory and a corresponding unique restore unit. This is not an
invitation to run a competing board session.

Each arm retains raw fixed-grammar compositor telemetry, actual external
two-service cgroup samples, and input/setup metadata. The replay appends those
measured resource rows to a separate derived log; raw compositor logs remain
unchanged. No private journal text, screenshot, recovery data, or camera movie
is published by this diagnostic. Replay the unchanged budget parser and
diagnostic from the repository root:

```sh
python3 docs/evidence/omarchy-themes/background-video-board-2026-10-21/tracking-cadence/analyze.py
```

[budget-analysis.json](budget-analysis.json) retains the numerical failures and
geometry issue. [diagnostics.json](diagnostics.json) describes input intervals,
all-present intervals, intermediate presentations, and repaint CPU stages.
The diagnostic asserts that its correlated tracking sample count and p95 match
the frozen analyzer exactly; it changes no threshold or exclusion policy.

[result.json](result.json) records before/after identities and restoration.
[final-state.json](final-state.json) independently confirms the normal 8 ms
setting, unchanged boot/system/compositor, original still generation,
only the startup terminal, zero injected touch devices, all three normal
services active, and the restore timer inactive. The board lease was then
released. Tasks 3.3 and 4.2 remain unchecked. This diagnostic enables no default
video selection. No real-finger, flicker-free, or optical performance result is claimed.
