## Why

A handheld on its charger sits on a desk for hours. Today it dims after 30 s
and goes dark after 60 s (`the-display-dims-and-sleeps-when-idle`), so a person
who docks it beside the bed or the keyboard base has a black rectangle and
must touch it to learn the time. webOS answered this with Exhibition mode: a
docked, idle phone becomes a clock. The user asked for the same here, with
the text K230 played through terminal text effects as the signature.
Review gap 13 of `docs/design/shell-ux-review-webos-firefoxos-2026-10.md`
names it ("Charging Exhibition clock ... drifting a few pixels per minute
against burn-in ... wake on touch or key"). Nothing here changes battery
behaviour: on battery the display still dims and blanks as it does now.

## What Changes

- **An exhibition card.** While the charger is connected and the person has
  left "Idle on charger" at Clock, the 30 s idle step dims the panel as before
  and then opens a full-screen terminal card showing a large clock and the date
  on black. The 60 s step does not blank the display while the exhibition is up
  and the charger is still connected.
- **K230 in motion, sparingly.** About every five minutes the card plays one
  `ttfx` text effect over a committed K230 banner (a few seconds, capped frame
  rate), holds the banner briefly, and returns to the clock. In between, the
  card redraws once a minute and does nothing else.
- **Burn-in drift.** Each minute's redraw places the clock at a different
  offset within a small range, so no pixel keeps one colour for hours.
- **Leaving.** Any touch or key goes to the exhibition card itself, which
  closes; the app that was in front is neither touched nor typed into, and the
  display returns to the prior brightness and the prior card or Home. When the
  charger is unplugged, or after two hours up, the exhibition closes and the
  display goes off with the idle step's own command.
- **A Settings row.** "Idle on charger" chooses Clock (the default) or Sleep
  (dim and blank exactly as on battery). It is a one-word file beside the Do
  Not Disturb preference, read by the idle step each time it runs.
- **The effect renderer.** `ttfx` v0.5.1 (MIT, a Rust port of
  terminaltexteffects used by Omarchy) is packaged for riscv64, with its
  licence and notice installed, as `nix build .#ttfx`.

## Non-goals

- A screensaver on battery. A single online CPU and a battery argue against it
  (design.md, "On battery: no screensaver").
- A lock screen, a notification-count dot, weather or a photo slideshow on the
  card; a separate Exhibition brightness; an editable effect list or cap; any
  choice of text other than K230. Each is a follow-up task, not built here.
- Changing the idle timeouts, the power key, the touch wake gate, or the
  inhibitors for Timer and video.
- Suspend, or lowering the CPU clock.

## Capabilities

### Modified Capabilities

- `system/power`: the charging exhibition, its exit, and what the idle step
  does on the charger. Written as ADDED requirements because
  `the-display-dims-and-sleeps-when-idle` has not archived yet; archive that
  change first, then re-check these against the merged spec.
- `runtime/device-settings`: the "Idle on charger" row.

## Impact

New `nix/term-apps/k230_exhibition.py` (the card), `nix/exhibition/K230.txt`
(banner), `nix/ttfx.nix` and `nix/ttfx/` (pin, lock, licence), a flake package
`ttfx`. Changed: `nix/idle-dimmer/idle_dimmer.py` (decision and launch),
`nix/idle-dimmer.nix`, `nix/term-apps/default.nix`, `nix/shell.nix` (wiring),
`nix/rust-shell-client/src/{shell_prefs,service_ui,render,main}.rs`.

Host tests cover the decision logic, scheduling, drift and the Settings hit
regions. The board is needed for: whether the card takes touch and keys and
closes cleanly, what returns in front, charger detection, CPU cost, and the
look on glass. Host tests show none of those, and none is claimed here.
