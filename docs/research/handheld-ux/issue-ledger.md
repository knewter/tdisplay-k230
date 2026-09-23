# UX issue ledger

Severity represents user impact from the cited observation; it does not turn an
unknown into a defect. “Existing owner” means a proposal already owns the
implementation boundary. No new P0/P1 successor is created by this audit while
those boundaries remain active.

| ID | Finding | Severity | Owner | Dependency | Evidence class | Citation | Acceptance | Open gate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| UX-01 | Camera evidence shows physical Apps hierarchy but not uniform lower-screen sharpness under glare. | P1 | visual/state consistency successor: `UNVERIFIED` | Coordinator review of this contract | camera, real-finger | `docs/evidence/shell-real-touch-apps/video-audit.md` | A new successor must name capture geometry and a real-finger optical command before implementation. | Scope/owner has not been selected; `UNVERIFIED`. |
| UX-02 | Keyboard-visible launcher composition has native and finger evidence, but no deliberate full-panel directional drag. | P1 | touch-launcher-gestures-overview | keyboard-visible gesture procedure | real-finger, native | `docs/evidence/shell-real-touch-keyboard/README.md` | Focused physical capture distinguishes drag from taps and preserves Back/Home recovery. | `UNVERIFIED` physical drag. |
| UX-03 | Empty, stale, loading, and failure states need one shared visible-state contract across catalog, cards, and video. | P0 | the-shell-has-a-card-composition-plan; the-shell-manages-apps-as-cards; the-shell-plays-network-video | architecture state/ownership decision | injected, host | `docs/evidence/network-video/installed-controls/README.md` | Every state names status, fallback, owner, and no-wrong-focus behavior in its successor tests. | Cross-surface integration remains `UNVERIFIED`. |
| UX-04 | The real-finger card flow has accepted footage, but live app card composition is proposed rather than shipped. | P1 | the-shell-has-a-card-composition-plan; the-shell-manages-apps-as-cards | app-content/security and compositor boundary | real-finger, injected | `docs/evidence/launcher-gestures/real-finger/README.md` | Card source must satisfy its own live-content, recovery, and physical acceptance gates. | `UNVERIFIED`. |
| UX-05 | Rotation, blur, thumbnails, and advanced GPU effects lack source/board evidence. | Deferred | future visual effects decision | measured renderer budget | UNVERIFIED | UNVERIFIED | A later owner records source support, cost, and a rollback path before proposing them. | `UNVERIFIED`; explicitly deferred. |
| UX-06 | Cold battery-only boot and unattended recovery have no accepted evidence. | P1 | boot/onboarding successor: `UNVERIFIED` | coordinator selects existing splash owner or new narrow successor | camera, serial | `docs/evidence/shell-real-touch-system/README.md` | Named operator run records cold start through usable shell without USB power. | `UNVERIFIED`. |

## Routing decision

The P0 state-contract gap is already split across the card composition,
app-card lifecycle, and network-video owners; creating another renderer or
lifecycle proposal here would duplicate them. UX-01 and UX-06 need coordinator
scope selection before a new proposal is appropriate. This audit supplies the
shared acceptance language and keeps those owners visible. Tasks that require
merging/pushing successor changes remain open for the coordinator.
