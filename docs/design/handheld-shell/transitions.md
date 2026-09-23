# Proposed shell transition map

These are design routes, not a record of installed behavior. The SVG [surface sheet](surfaces.svg) shows five 568×1232 views at 50% scale.

| From | Intent | To | Focus and fallback |
| --- | --- | --- | --- |
| App | Windows control; app-to-deck gesture only after card proof | Windows | Card owner hands focus to deck; Home or Apps remains visible. |
| Windows | Tap eligible live card | App | Card owner expands and returns keyboard focus; unavailable/private card has an explicit focus route. |
| Windows | Apps control | Apps | Catalog opens over deck; Back returns to deck. |
| Apps | Desktop entry | App | On success, focus new/existing window; on failure, remain in Apps with Back/Retry. |
| Any shell view | System control | System hub | Back returns to the exact prior view and focus. |
| System hub | Settings entry | Settings | Back returns to System hub with prior focus. |
| System hub | Notifications entry | History | Back returns to System hub with prior focus. |
| App/overlay | New event | Preview and History | Ordinary/important preview does not take focus; timeout keeps History entry. |
| Preview | Open or dismiss | Target or prior view | Open validates target; dismissing the preview leaves the event in History. Failed action keeps the History entry. |
| Any view | Notifications count | History | Back restores prior surface; keyboard remains owned by its input. |
| Any transient | Back | Underlying view | Close topmost preview/history/dialog before underlying app/deck. |
| Any surface | Home | Apps | Idempotent final shell landing; Terminal is a separate named recovery action. Legacy Home→Terminal remains only until opt-in rollout and real-glass recovery pass. |

Gesture zones: the launcher owns horizontal paging only within its card content; the live deck owns card tracking only after its architecture gate; a touch bar target wins before a content gesture. No gesture starts over the keyboard. A touch cancelled by a second contact or system interruption leaves the previous state and focus intact. A notification never reinterprets a live card drag as a tap. Edge swipes have no special meaning in this proposal.

State variants for implementation review: Apps loading/empty/failed launch; deck loading/empty/unavailable/private/stale/close refused; Settings reading/unavailable/pending/failed/confirmed; notifications preview/history empty/action target gone/critical pending. Each variant needs text plus a visible next action. Physical scanout, reach, latency, and notification interruption are **UNVERIFIED**.
