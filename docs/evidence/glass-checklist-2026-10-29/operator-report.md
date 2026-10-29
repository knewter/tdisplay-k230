# Glass checklist, 2026-10-29

Physical evidence: the operator at the glass, reporting by message. The
installed build was `/nix/store/37g1magg7c32k6a1nkssgp67dfcnr87l-nixos-system-nixos-26.11.20260919.20b1ddd`,
which was both running and the boot default. The checklist was sent in the
session, numbered 2–10. The reply arrived at 2026-10-29 00:34:26 CDT.

The reply, verbatim:

> text on files is mostly unreadable. all apps works. 4 works. 5 good. 6 quiet
> send a notification. 7 good. 8 good. all of the sudden gesdtures stopped
> working though i can't open the app drawer at all now

| Item | What the operator was asked to do | Reply | Change and task |
|---|---|---|---|
| 3 | With an app open, open the overview, tap "All apps ›" at the top right; the drawer opens | "all apps works" | `the-overview-opens-all-apps` 2.2 |
| 4 | LILYGO, `ti`, Enter opens Timer; LILYGO+Tab, Right, Enter switches cards; LILYGO+Tab, Esc returns; Terminal still types | "4 works" | `the-base-keys-launch-apps-and-drive-the-overview` 2.3 |
| 5 | Pull the shade: time and date lead, six tiles, sliders, notifications on the right, nothing cut off | "5 good" | `the-shade-leads-with-time-and-quick-tiles` 2.2 |
| 7 | Open Help, scroll to the end: readable and accurate | "7 good" | `the-help-page-lists-the-gestures-and-keys` 2.2 |
| 8 | Settings → About shows `37g1magg`; Date & time shows Chicago, synchronized, 24-hour | "8 good" | `settings-has-about-and-date-time-pages` 3.3 |

Not passed by this reply:

- Item 6 (Quiet): Quiet was turned on. The banner, thumb-reach and Timer
  breakthrough results are still owed.
- Item 10 and the Files part of item 2: "text on files is mostly
  unreadable". This is a defect report, not a pass.
- Item 9 (drawer search): passed in a later reply, below.
- The Net part of item 2: no reply yet.
- Gestures stopped working during the session. The cause and fix are in
  `docs/evidence/card-shell/leaked-touch-point/README.md`.

## Later reply, 2026-10-29 ~01:17 CDT

The build was still `37g1magg…` as the boot default, with `7w2fpx1f…`
test-activated at 00:50. That build changes only card-shell touch routing,
not the drawer search. The reply, verbatim:

> i saw the notification, it's all good, i didn't see the timer alert banner i
> wasn't looking. yeah increase files app text size [...] drawer search works

- Item 9: "drawer search works". This is in general terms. It does not
  report separately on the Settings result, the lower result and Enter.
  It closes `the-drawer-search-finds-settings-and-app-actions` 4.1.
- Item 6: the 10 s Timer breakthrough was not observed ("i wasn't
  looking"). The notification part is ambiguous: "i saw the notification"
  does not say whether a banner appeared while Quiet was on. That is the
  failure case. `do-not-disturb-quiets-banners-and-keeps-history` 3.5 stays
  open.
