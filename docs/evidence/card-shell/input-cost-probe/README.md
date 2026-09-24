# Input CPU stage probe: host preparation

The paired scaled-cache board result at `../scaled-cache-board/README.md`
observed all 13 injected interaction checks in each arm but failed the same
CPU and tracking budgets with the cache both off and on. Its first one-card
frame still reached about 49–51 ms. The earlier fixture repeat at
`../throw-fixture-sync/board/profile.json` attributes its 49.23 ms first
one-card submitted frame to 33.47 ms of input handling and 15.54 ms of
rendering. Five accepted motion events share that frame; the old row cannot
identify which motion or handler stage incurred the input time.

This diagnostic records one `K230_CARD_SHELL input-cost` row for each accepted
input ID, splitting its already charged handler CPU into policy motion,
`sync_scene`, and `chrome` calls. The remainder includes other handler work and
clock overhead. It does not alter the accepted `K230_CARD_BENCH` rows,
`frame-cost` totals, workload, or declared budgets. The exporter allows only
the six fixed unsigned numeric fields. `analyze.py` requires complete input,
submission, frame and repaint correlation, checks that stage CPU fits inside
its input event and that summed event CPU fits inside the charged frame input
CPU. It reports the hottest events and their submitted frame IDs.

The source shows that motion handling calls the card policy and then
`handle_result`; redraw synchronizes the card scene and checks the cached chrome
tree. The scene walk updates mirror geometry and clipping for each redraw.
Whether the 33.47 ms first-frame input cost lies in policy, scene work,
chrome, or other handling is **unverified** until the actual compositor and
board run produce correlated rows. A one-card first-frame allocation or
multiple scene walks is a hypothesis, not a measured cause.

Narrow host check:

```sh
python3 -m unittest tests.test_card_shell_telemetry tests.test_card_shell_board_tools
```

Before physical collection, build `.#card-shell` in the reserved build slot,
run the native runtime checks, and stage the resulting package with the
matching session, acceptance, budget, and probe tools. Reuse the normal-board
bounded acceptance runner, unique protected runtime, independent watchdog,
and post-run restoration proof. The 24-drag workload, all 13 interaction
checks, and original budgets remain required. A host test or build is not
board performance evidence; task 4.2 stays open.
