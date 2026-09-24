# Proposed gesture and scene transition map

These routes describe the final gesture session, not the installed development bar. The [contact sheet](surfaces.svg) and [motion storyboard](motion-storyboard.svg) show proposed positions; [motion research](motion-research.md) separates Palm documentation from K230 parameters.

| From | Touch intent | Result and spatial motion | Owner / cancellation |
| --- | --- | --- | --- |
| App | Bottom-edge upward drag | The same eligible live app shrinks into a card in **Home**, the horizontal deck. Releasing before the Home threshold returns it to the app. | Sway card scene/seat owner; app scroll/keyboard conflict is physically gated. |
| Empty deck | Bottom drawer pull | Empty Home stays stable until pull passes threshold; the drawer rises with installed apps and Terminal recovery. | Shell scene; early release returns to empty deck. |
| Deck with cards | Bottom drawer pull | Drawer rises over cards; releasing early returns to same selected card. | Shell scene; cannot accidentally launch during the pull. |
| Deck | Horizontal card drag/flick | Live cards follow the finger, settle at a bounded adjacent slot; tap expands from its current position. | Card owner plus coordinated motion layer. |
| Deck | Upward card throw | Card follows finger; observed app exit removes it, refusal/timeout restores it with a status cue. | Sibling close lifecycle; motion retargets from current geometry. |
| Drawer | Vertical drag/flick, horizontal section swipe | Installed app rows track/coast within bounds; a new touch stops coast; section changes snap. | Launcher owns content, Sway coordinates overlay. |
| Drawer | Tap desktop-entry icon/label | App launches from selected row toward its window/card location; failure returns to that row with a clear retry. | Launcher requests, Sway focuses. |
| Card/drawer item | Long press | Hold cue and context sheet appear; moving away, contextual Back or focus loss cancels without tap. | Owner at touch-down retains stream. |
| App/deck/drawer | Top-edge downward pull | Notification shade descends over current scene without moving its app. | Sway stacking; app/keyboard focus preserved. |
| Shade | Tap Settings entry | Settings follows the shade's top-down path; inward Back returns to shade. | Shell overlay owner. |
| Settings/History | Vertical drag/flick | Rows follow finger; coast stays within bounds and stops on touch. | Current overlay owner. |
| History event | Sideways swipe | Dismiss cue appears; short/reversed swipe returns item, completed swipe dismisses only that event. | Notification owner; critical ongoing event retained. |
| Shade/Settings/drawer/context | Qualified side-edge inward Back | Topmost shell surface or keyboard closes and prior scene/focus returns. | Sway shell route; no synthetic Back key into arbitrary app. |
| Any non-deck surface | Bottom Home swipe | Scene settles in live-card deck; empty deck remains a stable landing. | Global shell route except keyboard-owned region; alternate tested escape required there. |
| Deck | Home again | Same deck remains; continued drawer pull is a separate progressive motion. | Shell scene; no second home grid. |

Touch ownership is selected at down: keyboard's reserved lower area, app content, bottom Home/drawer, top shade, side contextual Back, deck and overlays have disjoint tested hit regions or a deterministic priority. Direction/distance gates may reject a shell claim; the whole stream then remains with its original owner. A second contact, source loss, new gesture, or reversal retargets from current visible geometry. Edge regions stay disabled in the final candidate until real-finger conflict evidence exists; the rollback development session stays available, but never appears as final chrome.

Every accepted state gives visual response: press, hold progress/context, drag, snap, close request/refusal, loading, empty, stale, failed launch and cancellation. Reduced motion preserves direct tracking and route results while shortening decoration. Physical scanout, gesture conflicts, frame cadence and latency are **UNVERIFIED**.
