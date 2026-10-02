# webOS references and current-shell comparison — 2026-10-01

The inspected sources are historical/design references, not requirements for
pixel or gesture compatibility. Accessed 2026-10-01.

| Source | Inspected material | Portable principle | Current K230 comparison and limit |
| --- | --- | --- | --- |
| Palm, *Palm webOS: The Essentials*, O’Reilly preview, [PDF](https://api.pageplace.de/preview/DT0400.9781449391997_A23800502/preview-9781449391997_A23800502.pdf), 2009, PDF pp. 30–36 (printed pp. 5–10) | Card view entry, selection, scrolling/reordering and flick-to-close; notification/dashboard roles. The preview was inspected directly; it contains no video timecodes. | Direct manipulation should communicate the object being moved; common actions and return routes should be discoverable. Keep event summaries distinct from task/window switching. | K230’s current source has Home/drawer and a separate window/card implementation. The newest ordinary-reboot image is Home only; the current integrated card deck appearance and finger-following trajectory remain `UNVERIFIED`. Historical gestures are not proof of the current candidate. |
| webOS Open Source Edition UI guide, [guide](https://www.webosose.org/docs/guides/getting-started/webos-ose-ui-guide/), guide version 2.19+, sections “App Bar,” “Status Bar,” “Launchpad” | App Bar quick access to favorites/running apps (guide lines 95–111); status-bar controls/notifications (129–151); installed apps/search/list in Launchpad (159–174). No time-based video was cited. | Keep high-frequency app entry visible; give discovery a clear installed-app/search model; expose system state separately from task content. | K230’s Home dock, persistent shell controls and drawer are different structures and are reviewed on their own terms. OSE guide context is TV/embedded; its layout is not a handheld target and establishes no K230 hardware behavior. |
| Palm Pre user guide, [Bell-hosted PDF](https://support.bell.ca/_web/guides/User-Guides/Mobile/PalmOne/Palm-EN/palm_pre_userguide_en%28en%29.pdf), inspected 2026-10-01, pp. 17–18, 24–27 | Gesture overview; card view, moving/closing cards, Quick Launch and app launcher. No video timecodes in the cited pages. | Make gesture outcomes visible and retain clear selection/escape routes. | K230 has an explicit user decision that long-press remains grab/drag; no touch menu gesture. Mouse secondary click is the app menu. This acceptance is a product constraint, not a webOS-derived rule. Current physical reacceptance is not implied. |

### Current comparison

The latest physical source identity and ordinary reboot are pinned in the
[baseline](baseline.md). The Home screenshot demonstrates a full native
568×1232 frame with app grid, time/date, page dots and dock. The authored dark
drawer host render shows a restrained search field and eight icon-led entries;
the prior recommendation for outlined full-width generic rows is obsolete.
The newest board Settings captures show the settled volume rows in dark and
light themes, so earlier “loading” and inconsistent-spacing critiques are
closed for those exact states. They also show the output picker floating over
Keyboard and Motion rows; physical finger impact is not established.

The keyboard image is a prior-source command-revealed native capture. There is
no current-source card deck image among the reviewed artifacts. Thus the
continuous card/deck relationship, current card identity, current touch
tracking, and current keyboard-visible reach are `UNVERIFIED`. A reference
video may inspire a question but cannot fill any of these evidence gaps.

Raw inputs consolidated rather than repeated: [webOS polish review](../../../design/webos-polish-review.md),
[September shell polish review](../../../design/shell-polish-review-2026-09.md),
[visual gap audit](../../../design/handheld-shell/visual-gap-audit.md), the
[first-round review](../evidence-review.md), and the [current flow matrix](../flow-matrix.md).
Older claims are retained only when they still match current-source evidence;
fixed or superseded claims are listed in [findings](findings.md).
