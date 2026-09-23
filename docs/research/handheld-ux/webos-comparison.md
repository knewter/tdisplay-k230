# webOS comparison: principles, not imitation

The comparison uses the Palm webOS and webOS OSE references in
[references.md](references.md). It draws only three portable principles:
direct touch should have visible feedback; common commands should be visible;
and a task switcher must have a recoverable return route.

| Topic | Reference lens | Current K230 evidence | Deliberate difference / successor implication |
| --- | --- | --- | --- |
| Persistent entry | webOS OSE describes an app bar for quick access to favorite or running apps. | The K230 has a fixed 56px **top** bar for Apps, Windows, Keyboard, and System. | Treat top-versus-bottom placement as an evaluated future design choice. Preserve the invariant: common app/window/recovery entry stays visible and never becomes gesture-only. UX-02 asks that Home recovery be disclosed more clearly. |
| App discovery | webOS emphasizes common actions and minimal steps. | The catalog refreshes desktop entries and shows equal generic cards for Foot Client, Foot Server, and Htop. | Curate/action-label catalog entries rather than importing webOS's launcher model. UX-01/UX-03 are bounded discovery work. |
| Cards | Palm webOS cards convey task continuity. | The current production overview uses metadata cards; live content is only proposed. | The card-composition and app-card proposals decide surface/privacy/compositor boundaries. This audit does not claim a webOS card implementation. |
| Gestures | Palm webOS supports direct touch interaction. | K230 preserves Apps, Back, Home, and bar routes alongside gestures. | Retain visible non-gesture recovery for accessibility and for an unreliable/unknown touch path. |
| Transient states | The reference discourages needless blocking. | Launcher errors can display truncated raw GLib/helper text while other surfaces use separate state wording. | UX-05 proposes a short shared recovery-language contract, not a modal stack or dashboard/notification system. |

Explicitly excluded: webOS visual assets, dock/dashboard, notifications,
stacks, blur, thumbnails, global search, and any assumption that Linux/Sway
surfaces can be composed like a historical webOS implementation.
