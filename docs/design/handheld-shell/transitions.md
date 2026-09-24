# Proposed gesture and scene transition map

These are design routes, not installed behavior. The [contact sheet](surfaces.svg) shows five 568×1232 views at 50% scale; [motion research](motion-research.md) separates historical source behavior from proposed K230 parameters. Finger movement is the primary route. Visible controls are accessible alternatives and recovery.

| From | Touch intent | Coordinated movement and settled result | Owner / interruption |
| --- | --- | --- | --- |
| App | Qualified upward edge drag, or Windows control | The live app shrinks from its current rectangle into the same card in the horizontal deck; adjacent card remains in place. | Opt-in Sway scene and card seat operation; edge enablement requires app-scroll/keyboard conflict proof. Back reverses from current position. |
| Windows deck | Horizontal finger drag/flick | Cards follow the finger, then coast only to a bounded adjacent card and snap; a new touch stops settling. | Card owner tracks live content; successor motion layer chooses/retargets settle. No Previous/Next tap is needed. |
| Windows deck | Tap selected card | That card expands from its visible slot into the same live app; focus returns at a valid destination. | Sway view/seat owner; app exit or another touch retargets without blank frame. |
| Windows deck | Upward card throw | Card tracks the finger; accepted close exits upward; refusal/timeout restores its slot with a labelled result. | Sibling card lifecycle decides close result; successor animates from current geometry. |
| Windows/Apps item | Deliberate long press | A hold cue appears, then a contextual action sheet; moving away, Back, focus loss or second touch cancels. | Surface under down owns sequence; release after hold never launches. |
| Apps | Vertical drag/flick, horizontal section swipe where sections exist | Content tracks finger, coasts to bounds; horizontal section travel shows adjacent section, then snaps. | Launcher owns content; compositor scene coordinates overlay entry/exit. A touch during coast stops it without activating a row. |
| Apps | Tap desktop entry | Press response appears; app opens from tapped item toward its window/card location. Failure returns to same item with Retry/Back. | Launcher requests launch; Sway owns new view geometry/focus. |
| Any shell view | System control | System hub moves in from its rail anchor; Settings or Notifications follows the same direction. | Shell overlay owner; Back reverses to prior focus. |
| Settings/History | Vertical drag/flick | Rows follow finger, coast within content bounds; controls keep their confirmed values. | Overlay owner; new touch stops coast. |
| History event | Sideways swipe | Item follows finger to reveal Dismiss; short/reversed drag returns it, committed swipe removes only that event. | Notification owner; critical ongoing event cannot be dismissed. |
| App/overlay | New event | Nonmodal preview enters near System without shifting active app; timeout retreats to System count/history. | Broker owns event, compositor owns stacking, app/keyboard keep focus. |
| Preview | Tap/open or dismiss preview | Open validates target; preview dismiss affects only preview and preserves History. Failed action keeps event. | Overlay owner; an active card drag/keyboard touch is never stolen. |
| Any surface | Home | Movement resolves into Apps, the idempotent safe landing. | Shell route; Terminal is a separately named recovery action. Legacy Home→Terminal is rollout-only. |

Hit regions arbitrate once on down: shell controls and keyboard own their actual targets; app scroll and selection remain in app content; deck owns only a qualified edge entry and its own card area; overlays own their visible content. No region silently changes owner mid-stream. A second contact, loss of live source, Back, or critical interruption cancels or retargets from current visual state. The candidate edge region is **not enabled by this design alone**. It must pass a real-finger conflict check; Windows remains the visible entry until then.

Every state needs a visible response: down/pressed, hold progress/context, drag, snap, close request/refusal, loading, empty, stale, failed launch, and cancelled. The visual response is complete without vibration. Reduced motion preserves tracking and the same routes while shortening decorative settling. Physical scanout, gesture conflicts, frame cadence, and latency are **UNVERIFIED**.
