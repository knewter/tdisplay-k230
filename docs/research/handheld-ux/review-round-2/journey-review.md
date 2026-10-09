# Journey review — 2026-10-01

This is an evidence-led desk review, not a new operator session. “Reproducible”
below means the source report names a concrete action/state and artifact; it
does not mean the action was repeated against the integrated candidate today.
Current-source journeys not captured here remain `UNVERIFIED`.

| Journey/state | Action and evidence available | Review across discovery/focus/feedback/motion/recovery/accessibility | Status |
| --- | --- | --- | --- |
| Home → app discovery | Latest native Home in [ordinary reboot evidence](../../../evidence/boot-verification/coherent-ordinary-boot/README.md); host drawer frames in [shell-polish](../../../evidence/shell-polish/README.md). | Home hierarchy is calm and the dock/app grid separate pinned from installed apps. Drawer icons/labels are distinguishable in the dark host render. Actual physical discovery/search/overflow and touch reading were not performed in this review. | Current Home pixels observed; drawer board journey `UNVERIFIED`. |
| Home → Overview / Apps / Terminal | The exact system and Rust executable in [operator-navigation.json](../../../evidence/boot-verification/coherent-manual-candidate/operator-navigation.json) have operator real-finger acceptance for Home→All apps, bottom handle→Overview, and Terminal open/return. This followed the temporary matching-kernel boot; the later ordinary reboot retained the same source/system but did not repeat those actions. | Reuse these three unchanged accepted interactions. Keep distinct tap-handle and drag actions. The report does not accept every Home edit, drawer search/overflow, keyboard path, or app-menu path. Long-press remains grab/drag; app menu is mouse secondary click. | Three exact-candidate paths accepted by operator report; broader journeys remain `UNVERIFIED`. |
| Settings volume and output picker | Physical native dark/light frames and injected interaction in [Settings trial](../../../evidence/shell-polish/settings-volume-layout/board/README.md). The picker open action is injected at the documented coordinates. | Loaded Settings values and actual sink-level change/restoration are grounded. The picker overlay covers the Keyboard/Motion controls in the frame, and its single output item occupies a tall overlay. This is a concrete placement/density concern; finger reach and perceived obstruction remain unknown. | Native + injected observed; optical/finger usability `UNVERIFIED`. |
| Keyboard-visible terminal | Prior-source native frame and recovery record in [keyboard evidence](../../../evidence/keyboard-gestures/supervised-installed/README.md); keyboard was shown via command. | The 400px keyboard and handle visibly occupy the lower display. The frame alone does not establish gesture activation, typing focus, Home/Back reachability, directional movement, or optical legibility. Service restart proves process recovery only. | Native composition observed on older source; interactive journey `UNVERIFIED`. |
| Window overview/card selection | Earlier Overview/Home navigation report includes injected physical-board interactions; no latest-source deck capture accompanies ordinary boot. | Discovery/selection/focus and settled appearance on the current system cannot be judged from an earlier source image. Static older cards cannot prove finger-following motion, refusal, or recovery. | Current integrated journey `UNVERIFIED`. |
| Empty/loading/stale/error/denied recovery | Existing empty/stale launcher and card evidence is linked from [evidence review](../evidence-review.md) and the proposal’s owner changes. | Treat raw path/error text, missing states, and recovery routes as separate findings only where a current artifact supports them. This review did not re-run each state. Keyboard-visible versions are likewise unknown unless directly captured. | Per-state current-source recheck `UNVERIFIED`. |
| Shade, media, Help and System | Existing flow/evidence owners in the [flow matrix](../flow-matrix.md). | Prior audits contain useful comparisons, but the current baseline did not repeat those journeys. Do not infer a motion/focus result from screenshots or source alone. | New journey execution `UNVERIFIED`. |

No finding in this report claims that an unobserved route failed. A new
serialized candidate recheck must identify the running candidate, capture the
state natively, and use camera/finger evidence when the question concerns
reach, readability, or tracking. This review’s scoped host work cannot close
OpenSpec task 2.2’s current-journey execution requirement.


## Current candidate observation — 2026-10-09

See the [identified candidate](candidate-recheck.md). The operator explicitly
accepts Home fill and correct Home/All Apps/Settings target activation on the
normal `q2rxmp` HDMI arrangement. New native captures also show a 19-entry Apps
catalog, one-Terminal-card Overview and loaded Settings after an initial loading
state. Those route commands were injected and do not count as newly walked
physical journeys under the rubric.

| Current journey/state | Starting state and observed action/result | Evidence and remaining judgment |
| --- | --- | --- |
| Home and app discovery | Normal HDMI Home; operator confirms Home and All Apps icons activate the intended app. | Operator physical report plus matching native/configure identity. No discovery failure reported; optical label reading and overflow/search remain unverified. |
| Settings | Operator confirms intended row activation. Native route opens loading, then loaded device controls in the later capture. | Separate operator target report and injected/native states. Paint/hit-target acceptance is bounded; output-picker and acoustic behavior are not newly accepted. |
| Overview | Injected enter from Home produces the current one-Terminal-card image, then returns Home. | Current native visual evidence resolves the old image gap. The operator now confirms the requested two-app switch/Home functional journey; no multi-card motion measurement follows. |
| Keyboard and terminal | Keyboard controls are visible in current Settings; Terminal is present in Overview. | The operator now confirms the requested show/type/hide Terminal journey. No new keyboard-visible composition, reach or accessibility measurement follows. |
| Media | Video is in the current catalog. | The operator now confirms the requested play/stop/Home functional journey; the catalog image itself is not playback proof. |
| Help/System | No named Help or System app appears in the captured 19-entry catalog. Device controls are in Settings. | Older matrix routes are unobserved as separate apps; no new launch or recovery failure is inferred. |
| Startup, close/refusal, empty/stale/error/denied and accessibility | No focused new power cycle, close/refusal or complete exceptional-state sequence was performed. | Each stays UNVERIFIED with its runtime owner. These missing observations are not failures or completion of those owners’ gates. |

The [operator report](../../../evidence/ux-review-round-2/candidate-2026-10-09/operator-report.json)
records the exact response: “terminal keyboard works. switching apps works.
videos work”, answering the three requested sequences. Together with the
current Home/Apps/Settings report, this supplies the newly walked functional
routes rather than counting injected commands as finger actions. Functional
focus, keyboard activation and app/media recovery were reported working; no
functional defect was reported in those checks. Visual composition and
motion/readability judgments retain the evidence limits in the table.

Task 2.2 is complete as a review with explicit unknowns. The actual available
happy-path routes have operator observations, Help/System are unavailable or
unobserved as separate apps, and cold startup, exceptional states, close/refusal
and keyboard-visible accessibility remain UNVERIFIED with their existing
runtime owners. This closes the analysis coverage map, not those runtime gates.
Candidate identity and all four findings have been rechecked for 3.1/3.2.
