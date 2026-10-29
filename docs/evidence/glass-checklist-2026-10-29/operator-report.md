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

## Operator waiver of item 6, 2026-10-29

The build `2867v7pm…` (larger GTK app text) was test-activated, and then
promoted to the boot default with the charger online. The kernel, initrd and
dtbs are the same as `37g1magg…`. The operator declined to test the Quiet
banner again. Verbatim:

> i'm sure the banner situation was fine i don' twant to test that shit assume
> it's fine it looked fine

This is a waiver, not an observation. Nobody observed, on glass, that a text
produces no banner while Quiet is on, or that a 10 s Timer breaks through.
The operator said only that the result "looked fine". The injected-board
results in `docs/evidence/do-not-disturb/board/` are still the only recorded
evidence for those behaviours.

## Operator decisions, 2026-10-29T22:03Z

These are decisions, not observations. They were made in chat, by picking from
the options offered.

- Make `ql630glm…` (the banner fix) the boot default: "Promote it".
- `do-not-disturb-quiets-banners-and-keeps-history` 2.3, the tile words
  rendering at about 70% size at the 200% text step: "Accept the shrink".
- `settings-has-about-and-date-time-pages` 4.1 and 4.2: "Split them out",
  each into its own successor proposal, so the change can archive.
- `apps-and-timers-can-alert-the-user` 4.1–4.3: "Record and defer". 4.1
  keeps the monotonic clock because this image does not suspend. 4.2 and
  4.3 move to a successor proposal.

A note on the item 6 waiver above. Later the same day, the board showed that
no banner appeared once the shade had been opened, until the drawer was next
opened (`docs/evidence/apps-alert/README.md`, "Banners after the shade
closes"). The code was the same on `2867v7pm…`, so on that build a banner
could have failed to show for this reason rather than because of Quiet. The
bug is fixed in `ql630glm…`.

## Glass checks on `ql630glm…`, reported 2026-10-29T22:23Z

The build `/nix/store/ql630glmr9j0smkf5b0l14y0cxlmsjhg-nixos-system-nixos-26.11.20260919.20b1ddd`
was the boot default. The operator was given three checks:

1. Tap Net's menus and Files' header buttons. Are they easy to hit?
2. In Files, open `open-test.png` and `open-test.pdf`, then long-press one,
   choose Open With… and pick another app. Were the chooser rows comfortable?
3. Turn Quiet off, run a 10 s Timer with its card closed, and watch for
   "Timer finished". Then say when ready, for a probe notification.

The operator's reply, verbatim:

> it all worked

What this covers:

- Items 1 and 2 were performed on glass and worked. The reply does not
  separately say whether the chooser rows were comfortable, only that the
  step worked.
- Item 3: the board corroborates the Timer part. Quiet read `off`, and
  history held `Timer / Timer finished` at 22:22:34Z. The operator never
  said they were ready for the probe, so it was not sent and no app
  notification banner was seen on glass. `apps-and-timers-can-alert-the-user`
  3.6 ("both banners") stays open for that.
