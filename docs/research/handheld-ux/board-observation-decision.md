# Board observation decision

Existing accepted evidence means this audit does **not** request a repeat of the
keyboard show/hide or confirmed Home trial. New board observations are needed
only when their owner is ready to close the named remaining gates:

| Finding | Needed observation | Owner | Command / procedure | Unknown retained |
| --- | --- | --- | --- | --- |
| UX-01 | A focused real-finger optical/readability capture without glare obscuring the lower content. | future visual/state consistency successor | `python3 tools/capture-feature.py ux-review --provenance real-touch --duration 30 --description 'Observed handheld flow for UX review' --output-dir /tmp/k230-ux-capture` | Uniform sharpness and all-edge reachability. |
| UX-02 | Deliberate full-panel directional drag while keyboard is visible, including Back/Home recovery. | touch-launcher-gestures-overview | Its committed gesture procedure with real person input; preserve no injected event provenance. | Drag interpretation and reach envelope. |
| UX-03/04 | Live card entry, tracking, expansion, refusal/close, and recovery after the architecture/lifecycle implementation exists. | card-composition and app-card owners | The exact future `capture-feature.py card-shell` procedure from that proposal. | All live-card behavior. |
| UX-06 | Cold USB-powered boot to usable shell. | selected boot/onboarding owner | `flock /tmp/k230-board.lock python3 tools/capture-boot.py --dev /dev/ttyACM0 --out /tmp/k230-ux-boot.txt --seconds 120` | Cold USB-powered startup timing. |

No board was reserved or used for this planning change.
