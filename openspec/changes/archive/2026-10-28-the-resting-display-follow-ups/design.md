## Context

Both parent changes are board-proved and archive alongside this one. The
idle path is swayidle (`shell-idle.service`), which calls
`k230-idle-dimmer dim|off|resume`. The dimmer owns the saved brightness in
`/run/k230-idle/idle-dimmer.json` (moved from `/run/shell`, which a shell
restart wipes; task 6.1) and, on the charger, starts the clock screen
(`k230-exhibition`, a Foot card running ttfx). Preferences live in
`/var/lib/k230-shell-prefs/`. All of it is userspace, plus Nix for the unit
arguments; no kernel, device-tree or stage-1 work is involved.

## Goals / Non-Goals

**Goals:** carry each follow-up with enough design that it can be taken
alone, and keep every item traceable to its source task.

**Non-Goals:** the same as the proposal's. This change does not reopen how
dim, off, wake or the clock screen already behave.

## Decisions

- **The timeout lives in a pref file read by `k230-swayidle` at start**, not
  in Nix. swayidle has no live reload, so changing the timeout restarts
  `shell-idle`. This is the same pattern as `idle-on-charger`. Rejected:
  making the dimmer track time itself, which duplicates swayidle's
  idle-notify handling.
- **The HDMI unplug reports activity to swayidle.** After
  `output * power on` it sends `seat * cursor move 0 0`, so swayidle's resume
  runs the dimmer, which owns the saved brightness, and the dimmer does the
  restore. This is the same activity signal the power key's wake uses.
  Rejected: running `k230-idle-dimmer wake` from the relay. The relay runs
  as root under `ProtectSystem=strict`, so the dimmer would have no write
  access to `/run/shell`, and any state file it did create would be owned by
  root and unwritable for the shell-user dimmer. Also rejected: a second
  copy of the restore logic in Rust.
- **The charging-defers-off and wallpaper-decode questions are decisions,
  not builds.** Record the answer and its evidence in this change first,
  then propose any build.
- **Pointer-only close uses the same consume-and-close path as touch.** The
  clock screen must hold pointer focus over the whole output.
- **The camera record is optional.** It waits for the webcam and gates
  nothing else here.

## Risks / Trade-offs

- A long timeout drains the battery faster. The default stays at 30 s / 60 s.
- Restarting swayidle on a settings change resets the idle timer. That is
  harmless, because the person has just touched Settings.
- A pointer that jitters on its own would keep closing the clock screen.
  Watch for it on the board.
