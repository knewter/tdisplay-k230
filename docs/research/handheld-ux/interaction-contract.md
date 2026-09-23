# Portrait visual and interaction contract

This contract is a successor-facing constraint, not a claim that its proposed
pixels are shipped. Values are in logical panel pixels for the 568×1232
portrait mode. A native `grim` frame establishes composition; camera and
real-finger checks establish the separate optical and reachability gates.

## Visual tokens

| Token | Current evidence / proposed rule | Acceptance method | Evidence class | Citation | Open gate |
| --- | --- | --- | --- | --- | --- |
| Canvas | Dark, stable background behind launcher content; preserve the persistent 56px top bar. | Native frame is 568×1232 and bar remains visible with keyboard. | native | `docs/evidence/launcher-gestures/integrated-injected/keyboard-visible.png` | Panel scanout/optical contrast `UNVERIFIED`. |
| Title | One page title, 40–44px visual role; one short state line below it. | Title/state remain distinct at keyboard-visible height. | native | `docs/evidence/launcher-gestures/integrated-injected/keyboard-visible.png` | Physical readability `UNVERIFIED`. |
| Card | Card title 30–34px, hint 19–22px; content inset at least 24px; no essential text only in color. | Native screenshot plus text/focus state review. | native | `docs/evidence/offline-wifi-image/help.png` | Optical readability `UNVERIFIED`. |
| Spacing | 8px micro-gap, 16px control gap, 24px content inset; retain a clear gap between cards and footer. | Inspect native frame at full resolution. | native | `docs/evidence/launcher-gestures/integrated-injected/overview.png` | Future card layout must remeasure. |
| Targets | Primary controls are at least 56px tall; retain visible Previous, Back, Next and the persistent controls. | Host geometry review and finger capture. | native, real-finger | `docs/evidence/launcher-gestures/real-finger/README.md` | All-edge reachability `UNVERIFIED`. |
| State | Focus has a text/state cue; pressed, loading, empty, stale, failure, EOF, and cancelled states name a next action. | Successor fixture plus native capture for each new state. | injected | `docs/evidence/network-video/installed-controls/README.md` | Cross-surface state wording `UNVERIFIED`. |
| Keyboard viewport | Keep an explicit Back/fallback route above the shown keyboard; do not place essential controls in its reserved lower region. | Shown keyboard native frame and real-finger sequence. | native, real-finger | `docs/evidence/shell-real-touch-keyboard/README.md` | Exact physical reach envelope `UNVERIFIED`. |

## Navigation ownership

| Route | Primary owner | Visible fallback | Required states | Successor / dependency | Open gate |
| --- | --- | --- | --- | --- | --- |
| Apps | launcher/catalog | Back closes the overlay to current work | loading, empty catalog, launch failure | shell launcher/catalog | Physical catalog readability `UNVERIFIED`. |
| Windows / overview | touch-launcher-gestures-overview | Back/down returns to Apps; persistent Apps opens catalog | loading, empty, stale, helper failure | catalog helper; card architecture | Stale/empty board result `UNVERIFIED`. |
| Cards | the-shell-manages-apps-as-cards | Button entry plus Back/Home recovery | unavailable/private content, refusal to close | card composition decision | Entire live-card route `UNVERIFIED`. |
| Keyboard | shell keyboard | Keyboard control and Back/Home remain visible | shown, hidden, focused app exits | wvkbd and launcher viewport | Full drag/reach `UNVERIFIED`. |
| System | shell system controls | Cancel returns to shell | confirmation, denial/failure, reboot return | privileged action helper | Cold USB-powered recovery timing `UNVERIFIED`. |
| Stop / EOF | the-shell-plays-network-video | Home/Apps after cleanup | Stop, EOF, network failure | video session controller | Network failure treatment `UNVERIFIED`. |
| Help | launcher/catalog | Back returns to Apps | page bounds, empty catalog remains recoverable | launcher catalog | Focused real-finger Help test `UNVERIFIED`. |

## Motion and accessibility acceptance

| Interaction | Required behavior | Measured budget / proof | Reduced-motion behavior | Open gate |
| --- | --- | --- | --- | --- |
| Page release | A completed page or overview release settles in at most 200ms CPU-side release-to-final-submit; report wall and process-CPU measures separately. | Existing injected matrix: 41 settled transitions, max 163ms wall. | Settle immediately only after preserving the same page/card result and visible state. | Real-finger latency and scanout `UNVERIFIED`. |
| Card finger tracking | The future live card visibly follows the finger, with continuous tracking measured separately from release. | Card owner must record frame/input/memory evidence before acceptance. | Reduce decorative interpolation, never remove live visual, finger tracking, expand, close/refusal, or recovery. | `UNVERIFIED`. |
| Status and focus | Labels explain focused, loading, empty, stale, failed, cancelled, Stop and EOF states without color alone. | Fixture covers state transitions; native capture records visible text. | Same text and fallback stay present. | Cross-surface test/capture `UNVERIFIED`. |
| Reachability | Every gesture has a visible button, Back, or Home alternative. | Flow matrix routes every named control. | No gesture-only operation. | Physical all-edge review `UNVERIFIED`. |

## Review record

See [design-review.md](design-review.md) for the completed coordinator review
of the native captures and proposed layouts. That review does not substitute
for the physical readability and interaction gates listed above.

## Measurable review checks

| Check | Baseline / threshold | Host review method | Physical gate |
| --- | --- | --- | --- |
| Text contrast | Current source colors calculate to 16.96:1 title (`#f8fafc`/`#111827`), 11.95:1 secondary (`#cbd5e1`/`#111827`), 9.65:1 card-title (`#ffffff`/`#24495a`), 6.50:1 card-hint (`#cbd5e1`/`#24495a`), and 9.35:1 error (`#fca5a5`/`#111827`). Successors must retain at least 4.5:1 for text over its actual fill. | Compute sRGB relative luminance from the source colors and keep the calculation with the source test. | Camera/glass review checks glare does not make the measured design contrast unusable. |
| Focus | The selected window currently changes its card fill and adds the `focused` state text. A successor must use both a non-color state label and a visible shape/border/fill change. | State-machine fixture compares unfocused/focused render metadata and asserts the label/state change. | Real-finger selection capture. |
| Pressed | Pressing a card must show a bounded visual response before launch/focus; cancellation must restore the original card without launch. | Pointer/touch fixture checks press, moved-out cancel, and release-on-same-card transitions. | Real-finger tap/cancel capture. |
| Error and recovery | User-facing messages are short, avoid raw paths/GLib text, and name an available next action such as Back, Apps, Home, Retry, or Cancel. | Fixture asserts normalized state ID, copy key, and visible fallback for launch/helper/system/video states. | Integrated board state capture. |
| Reduced motion | With motion reduced, no decorative interpolation is required, but page/card result, finger tracking, expansion, close/refusal, focus, and all button fallbacks remain. | Card/gesture state-machine fixtures run with animation duration zero and assert identical end state and recovery controls. | Physical preference/flag exercise once implemented. |

The measurements above are source-color and host-state checks. They do not
measure panel luminance, scanout, or camera exposure.
