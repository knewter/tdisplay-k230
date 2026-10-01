# the-shell-behaves-as-one-coherent-system: operator acceptance

Recorded 2026-10-01 from the project operator's conversation. This is a
physical operator report about the installed device, not an agent-run test,
new camera capture, injected-event trial or quantitative measurement.

> **Render-ahead / bottom flicker** <-- this is done it's been fixed for ages. **App drawer redesign** <-- this seems fine idk why we would focus on perf for it right now versus find slow sutff to spend energy on when it arises. **Keyboard gestures** <-- these seem fine to me. **Coherent shell behavior** <-- this seems fine just close them out ask me for any details you need but trust me and no need for captures if they're hard at all

The operator explicitly requests closeout, trusts their reports and waives
additional difficult captures/retesting. Existing source, host/QEMU and board
evidence remains unchanged and retains its original provenance. No new
firmware, kernel, userspace deployment or board action was performed here.

Closeout worktree: `/mnt/MediaVolume/home/jadams/src/gitlab.daringbit.com/josh/tdisplay-k230/.scratch/coordinated-work/accepted-coherent-closeout`; branch `closeout/accepted-coherent-shell`; base `8e88892472b4ede7c528560ada5e3dde25a433e0`.
Owned paths: this change and its archive, its affected capability specs,
this evidence report and this card's entry in `docs/work-board-status.json`.
No board/serial reservation. The coherent closure build was serialized under
`/tmp/k230-nix-build.lock`; other closeouts need no build reservation.

## Disposition

- **A.4:** Record the operator's 2026-10-01 acceptance that coherent shell behavior seems fine and should close. Retain earlier fan-switcher source/QEMU evidence. The user waives further camera capture; do not claim a newly recorded per-case legibility/momentum trial.
- **E.4:** Record the same physical operator acceptance for coherent shell behavior, retaining overlay-bottom-escape source/QEMU evidence. Additional Settings-subpage gesture captures are waived; no fresh per-subpage latency trial is claimed.
- **D.2:** Run `nix build .#nixosConfigurations.k230.config.system.build.toplevel --no-link --print-out-paths --max-jobs 2 --cores 8`: passed, producing `/nix/store/p0gzcaa6bfqblzzqdcfpqznmq8x2wd28-nixos-system-nixos-26.11.20260919.20b1ddd`. Cross-build only, not deployment or boot proof. Source base `ea40ee5d` contains the accepted implementation.
- **D.3:** Close A/E using the committed operator acceptance and capture waiver. Preserve the previously authorized B/C successor `the-shell-offers-quick-toggles-and-vision-options`; this archive makes no claim that its quick-toggle/accessibility work is finished.

## Required host build

```sh
nix build .#nixosConfigurations.k230.config.system.build.toplevel --no-link --print-out-paths --max-jobs 2 --cores 8
```

Passed (exit 0), source `ea40ee5d5128bb77dac3a5736baf793d74d50295`:

```text
/nix/store/p0gzcaa6bfqblzzqdcfpqznmq8x2wd28-nixos-system-nixos-26.11.20260919.20b1ddd
```

This is cross-build proof only. The closure was not installed or booted for this closeout. Later planning-only commits do not change its source implementation.

## Prior committed evidence

- `docs/evidence/coherent-shell/overlay-bottom-escape-qemu/README.md`

## Superseded verification protocol

The following are historical requests, not tests performed on 2026-10-01.
Their disposition above replaces capture-only acceptance barriers or transfers
unperformed measurements, rather than falsely checking a test as executed.

```text
A.4 On a reserved board, confirm the webOS-fan overview (2-3 cards,
  real icons/names, scroll momentum, close, open) is actually legible and
  usable at arm's length with a real theme and real running apps, and that
  the direct bottom-edge app-switch gesture's feel is unchanged. Host/QEMU
  evidence exists (`docs/evidence/card-shell/webos-fan-switcher/`: dark +
  light headless-QEMU captures of the overview, a scroll, a close and an
  open, driven through the real `card_shell test-touch` input path) but is
  explicitly not a substitute — see that evidence's own README for what it
  does and does not show. Operator command: `python3
  tools/capture-feature.py webos-fan-switcher --provenance real-touch
  --duration 30 --description 'webOS-fan card overview: icons, names,
  scroll, close, open' --output-dir
  docs/evidence/card-shell/webos-fan-switcher`. Keep this task open until
  that capture is committed; a host/QEMU render alone does not complete it.
```

```text
E.4 On a reserved board, confirm the bottom-edge escape from Settings
  (including the theme chooser and Wi-Fi/password-entry sub-pages) and the
  unified dismiss direction feel right from a real finger: no perceptible
  stall or visual glitch during the overlay's asynchronous dismiss, correct
  destination every time, and the Close/Back controls remain reachable.
  Operator command: `python3 tools/capture-feature.py
  overlay-bottom-escape --provenance real-touch --duration 30 --description
  'Bottom-edge overlay escape and dismiss-direction consistency on glass'
  --output-dir docs/evidence/coherent-shell/overlay-bottom-escape`. Keep
  open until that capture is committed; E.1-E.3's host/QEMU proof does not
  complete this task.
```

```text
D.2 After A's host tasks land (done) and B/C land in their successor,
  evaluate the integrated closure:
  `nix build .#nixosConfigurations.k230.config.system.build.toplevel`
  (cross-build proof only, not board proof). Slice E's own toplevel
  evaluation was run separately at implementation time (see
  `docs/evidence/coherent-shell/overlay-bottom-escape-qemu/README.md`).
  B/C's own toplevel evaluation now belongs to the successor's own task D.2;
  this task is scoped to A/E, both already evidenced.
```

```text
D.3 Do not archive this change until each remaining slice's board task
  (A.4, E.4) is committed. **Scope split authorized by the user on
  2026-09-28 ("yes a-d and f")**: every slice B/C requirement and task (plus
  the new task B.5 for the shade tap-target requirement, which had no task)
  is carried forward into `the-shell-offers-quick-toggles-and-vision-options`,
  and slices B/C and their `notification-center`/`device-settings`
  requirements are removed from this change in the same commit. A.4 and E.4
  are this change's only remaining gates.
```

