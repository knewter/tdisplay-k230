# Product card shell: injected board interaction acceptance

Completed 2026-09-23 at 16:07:09 UTC using tools `11ffecb` and the existing
product package `/nix/store/ii5g7635wldnk7jsrfp18ism634w5y70-k230-card-shell`,
source `935e02155cac7374de10b5db6e642d9479c500b3` (landed as `f514478`).
The deliberately unchanged package isolates the acceptance-tool correction
from the separate compositor telemetry fix. **Task 5.2 interaction evidence
passes; no cost, default-image or real-finger acceptance is claimed.**

## Method and provenance

Follow `docs/research/card-shell-board-tools.md`: a coordinator-reserved,
temporary non-root service includes the actual normal configuration, with
DSI-1 at 568x1232, scale one, Pixman RGB565. Native input-event packets go only
to the distinctly named, sysfs-verified virtual touchscreen. The compositor's
headless test-input hook is not used. Root recovery is armed before stopping
the normal shell, and all trial processes belong to bounded service cgroups.

Actual invocation after the owner declared the reservation active:

```sh
python3 /run/card-tools/card-shell-acceptance.py --execute \
  --provenance injected-touch --output /run/card-evidence/acceptance
```

The runner exits successfully with all thirteen checks `OBSERVED`. The raw
report deliberately remains `CAPTURED_REQUIRES_REVIEW`; this document records
the subsequent coordinator visual review rather than rewriting raw results.
The transfer was verified against the board archive's SHA256 over Wi-Fi after
a serial download failed gzip verification. No failed download was published.
The offline collector verified each retained screenshot against the report's
hash and exported only allowlisted telemetry and client records.

## Reviewed observations

| Interaction | Evidence and reviewed outcome |
| --- | --- |
| Native card entry | `one-live.png` shows the blue parent and orange child shrunken inside the selected card. Native renderer/format metadata matches the panel. |
| Two live apps and horizontal movement | `two-live.png` was captured while holding the injected drag halfway between cards. Both parents and children are visible; both clients' counters advance. The selected card moved from its centered position to the left, exposing its neighbor. |
| Tap expansion and Cards Back | `expanded.png` shows the purple app at normal size; `cards-back.png` shows the blue app restored after close handling. |
| Privacy and unavailable state | `private.png` and `unavailable.png` replace the selected app's pixels and title with the corresponding non-live placeholder. |
| Upward close and refusal | The native throw generates `close_requested` followed by the client's explicit `close_refused`. The client remains alive. |
| Timeout and accepted close | Fixed telemetry independently records the compositor timeout; `close-timeout.png` retains the app and explains recovery. The second client accepts Close and exits; `close-exit.png` shows the remaining card and source-gone feedback. |
| Apps and Help/Back | `apps.png`, `help.png` and `help-back.png` show the expected installed-app and help surfaces and return path. |
| Terminal and Monitor | `terminal.png` shows the usable terminal; `monitor.png` shows htop. IPC verifies the corresponding app focus. |
| Windows/Home | `windows.png` shows the Windows controls; `home.png` returns to Terminal with the normal bar. |
| Keyboard | `keyboard.png` visibly shows the keyboard, while workspace geometry confirms reserved content space. |
| System/Back | `system.png` shows System controls; `system-back.png` restores the main bar and Terminal. No reboot or power-off was invoked. |

The refusing synthetic floating client is terminated only after its protocol
test, with executable and owner verified, so it cannot obscure normal tiled
apps. All user interaction routes use native injected touches; marks used to
exercise privacy and fixture lifecycle setup use ordinary compositor IPC.
Synthetic titles label refusal behavior and do not correspond to app-ID order;
client identity in the logs is authoritative.

## Limits retained

`during-drag.png` caught a settled selected card, so its filename alone is not
movement evidence; the deliberately held `two-live.png` supplies that evidence.
`closing.png` was captured after the 1.5-second refusal timeout, not during the
short pending-close state. The client protocol log and separate timeout state
provide the refusal/timeout distinction. Neither capture establishes animation
smoothness, gesture latency, physical-glass behavior or optical presentation.

The old compositor's session-start timestamp still follows the first input.
The unchanged cost parser rejects this run with exit 2 (`benchmark-rejection.txt`).
The telemetry is retained unmodified; no passing cost report is fabricated.
Compositor-observed motion gaps have medians of 2.037 ms (one client) and
2.271 ms (two), but maxima of 67.489 ms and 62.903 ms. These bursty callbacks
are not proof of uniform 10 ms device delivery or a frame-budget pass. A repeat
with the corrected producer must evaluate all declared budgets independently.

The original failed run remains in `../board-first-trial/`; successful testing
with corrected instrumentation does not erase it. Product task 5.1 still needs
system-image integration and its QEMU proof. Task 5.3 still needs a focused
real-finger trial. The current card appearance is functional and remains part
of the planned UX refinement, not a claim of finished webOS-like polish.

## Normal-shell recovery

`restoration.json` records the independent 16:07:47 UTC injected regression:
normal shell/seat/network services active, Apps Next/Previous, keyboard toggle
retaining Apps, Terminal, and Apps Back all passed. The product service was
inactive. The installed image stayed
`/nix/store/nz82q373yj1hp2k4qm85xa3c328jli8j-nixos-system-nixos-26.11.20260919.20b1ddd`,
with unchanged boot ID `9407bae0-fe1a-4a05-8062-edbe8a110859`. No flash or reboot
was required, and no Wi-Fi credentials or private addresses are included.
