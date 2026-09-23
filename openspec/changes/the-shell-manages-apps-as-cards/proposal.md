## Why

A person can launch and switch applications today, but cannot see or directly
manipulate their running work as a coherent handheld surface. The existing
metadata overview is deliberately text-only, so it cannot provide the live,
finger-following card interaction requested for the shell.

## What Changes

- Add a full visual app-card surface: an eligible running application shrinks
  into a live card, cards form a horizontal deck, follow a single finger, and a
  tap expands the chosen card.
- Let an upward throw request a graceful application close. A refusal, timeout,
  or close failure keeps or restores a usable card and exposes recovery rather
  than silently losing work.
- Keep the persistent Apps, Windows/Home, Keyboard, System, Help, terminal,
  monitor, and launcher routes available while the card surface is entered,
  used, dismissed, or fails.
- Define explicit handling for application surfaces that cannot safely be
  presented live, including unavailable, protected, or private content.
- Gate implementation and integration on the sibling
  `the-shell-has-a-card-composition-plan` architecture decision. That decision
  chooses the composition boundary; this proposal does not assume a client,
  compositor change, GPU path, or second core.
- Measure frame, input, and memory costs on the default Pixman path. An
  optional VGLite experiment remains independent and cannot become a hidden
  requirement for the basic experience.

**Non-goals:** boot work, a notification ecosystem, application search,
multitasking policy beyond this deck, global gesture policy, and animation
systems beyond direct shrink, drag, deck, expand, and throw-close behavior.

## Capabilities

### New Capabilities

- `runtime/card-shell`: live application-card presentation, manipulation,
  privacy/unavailability handling, and bounded recovery for the handheld.

### Modified Capabilities

- `runtime/shell`: preserve the existing persistent controls, keyboard route,
  launcher, and Home recovery while a card surface is active.

## Impact

The eventual implementation may affect userspace shell composition, Sway or a
new composition boundary selected by the sibling architecture change, launcher
integration, Nix packaging, tests, and board evidence. Host model tests and a
narrow derivation build can proceed before hardware, but live content, touch,
readability, frame cost, and recovery require physical-board evidence. No
kernel, boot, second-core, or GPU dependency is assumed by this proposal.
