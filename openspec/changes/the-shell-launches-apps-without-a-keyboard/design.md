## Context

The existing Nix/userspace shell draws one 56-pixel swaybar row and routes its
click JSON into `nix/touch-menu.sh`. It already launches or focuses Terminal
and Monitor, pages real Sway windows, toggles wvkbd, and gates power actions.
Physical evidence shows the bar can be reached with injected input; real-glass
launcher use remains unverified.

## Goals / Non-Goals

**Goals:**

- Make Apps read as an application launcher rather than a utility submenu.
- Keep every target within the 568-pixel row, at least 56 pixels high, and
  usable with Pixman's small CPU budget.
- Retain all existing menu pages and their recovery/security behaviour.

**Non-Goals:**

- Generic `.desktop` discovery, a searchable launcher, icon themes, or a
  second GUI toolkit.
- Adding applications or changing the keyboard, window paging, or system
  authorization policy.
- Claiming real-glass verification from protocol tests or injected input.

## Decisions

**Use the existing i3bar state machine.** Four 128-pixel blocks total 512
pixels, leaving swaybar padding inside the 568-pixel display. The Apps page
therefore presents Terminal, Monitor, New terminal, and Back in one stable
row. Each app entry receives a restrained background colour and short label;
the same visual treatment distinguishes the home controls. This has no new
process, protocol, or dependency.

**Launch a fixed, known set.** Terminal and Monitor are explicitly supplied by
the shell Nix module and have tested app IDs/configuration. Desktop-file
scanning would make the launcher depend on uninstalled metadata and parse
arbitrary Exec lines; it would not discover the two terminal profiles in a
useful way. Windows remains the dynamic discovery page because Sway's tree is
the authoritative list of running windows.

**Make New terminal deliberate.** Terminal retains focus-or-start behavior for
recovery. A separate New terminal action avoids overloading it and creates a
second tabbed window for a task that needs one. It uses the same readable Foot
configuration as Terminal.

## Risks / Trade-offs

- [Colours differ between panels/themes] → Labels and target geometry carry the
  meaning; colours are supplementary and use high-contrast text.
- [The menu row is still not a full-screen grid] → It keeps 56-pixel targets
  that current swaybar touch handling already supports, without a toolkit or
  compositor change.
- [New terminal can create many windows] → Windows continues to enumerate and
  focus all actual Sway containers.

## Migration Plan

Deploy by rebuilding the existing shell configuration. Removing the launcher
entries reverts to the current Apps row; no persisted state, data, or system
privilege changes. The coordinator can verify on glass by filming Apps,
Terminal, Monitor, New terminal, and Back, recording whether the interaction
was real touch or injected.
