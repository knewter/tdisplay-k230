## Context

The existing shell owns a GLib desktop catalog and a native Wayland launcher. The
new capability adds userspace packages and launcher content in the Nix layer; it
does not change stage 1, the kernel, the device tree, or the compositor. The
display is 568x1232 portrait with Pixman rendering and a 1 GiB target, so every
candidate needs measured cross-build and runtime evidence.

## Goals / Non-Goals

**Goals:**

- Reuse the existing catalog, GLib launch path, Foot profile, and launcher
  paging rather than adding a second application model.
- Evaluate `nano` as the first editor candidate and compare `lf` (Go) with the lighter C-based `nnn` as a file
  browser candidate, with an already-present terminal utility as fallback when
  either candidate fails the riscv64 or closure checks.
- Generate simple visible desktop entries for selected terminal applications,
  using the existing terminal bridge and profile.
- Add a Help card whose content is static, concise, high contrast, and paginated
  using the same portrait interaction model.
- Measure package closure deltas, image startup, catalog discovery, injected
  touch navigation, and launch return paths before image integration.

**Non-Goals:**

- A network installer, package manager UI, software update flow, web browser,
  AtomVM/Dozer integration, or general desktop environment.
- A broad theme redesign. A small shared color/font constant may be reused only
  if it has no measurable closure or startup cost.
- Claiming physical finger accuracy, reboot persistence, or final glass
  readability from host builds or injected input.

## Decisions

**Keep selection bounded and evidence driven.** Start with `nano` as the editor
candidate; measure the Go closure of `lf` against the lighter C-based `nnn`
before selecting either file browser;
confirm their actual pinned riscv64 derivations and closure costs before choosing
them. If either fails, retain the existing shell and select only a package that
already satisfies the measured budget. This avoids committing to a Python or GUI
file manager solely because its desktop entry is attractive.

**Represent terminal tools as normal desktop entries.** The Nix layer owns
package inclusion and a minimal `.desktop` entry with `Terminal=true`; the
existing GLib launcher owns discovery, visibility rules, Exec expansion, and
terminal selection. Do not add raw command parsing or a second hardcoded app
catalog.

**Make Help launcher-owned.** Help is a built-in page/card, not a package or a
desktop entry. It uses the same SHM/Pango rendering and touch release handling
as the launcher, with Back and paging targets. This keeps Help available
offline even if application discovery is empty.

**Use a compact content contract.** Help text names each persistent control and
the launcher actions in short lines sized for portrait cards. It must explain
that Previous/Next paginate apps and that Back returns to the prior surface.
Avoid implementation terms, network instructions, and claims about unverified
hardware behavior.

**Validate at four boundaries.** Host checks cover evaluation, cross-build,
desktop file validation, and closure delta. Image checks cover startup and
catalog appearance. Injected board checks cover Help paging and candidate
launch/return. Physical finger, reboot, and panel legibility remain separate
evidence owned by the hardware integration work.

## Risks / Trade-offs

- [A candidate's transitive closure exceeds the image budget] → reject it using
  the recorded delta and leave the shell's existing tools intact.
- [A terminal desktop entry is filtered or launches with the wrong environment]
  → inspect the catalog ID and GLib launch result through the existing private
  PATH/Foot bridge before image integration.
- [Help content is clipped at 568x1232] → keep pages short and verify screenshots
  at the actual mode; do not rely on desktop dimensions.
- [A failed app launch leaves the user stranded] → preserve the existing
  in-surface error and Back path and test it with an unavailable candidate.
- [A shared theme change expands scope] → treat theme work as optional and omit
  it when it requires new assets, a toolkit, or a separate daemon.

## Migration Plan

Add the selected packages and Help card behind the existing shell image option.
Build and inspect the closure before flashing. If a candidate fails, remove its
package and desktop entry without changing the existing launcher contract. If
the Help card fails, revert only its built-in page and retain Apps, Terminal,
Monitor, and Back.

## Open Questions

None that change the bounded approach; candidate acceptance is determined by the
recorded checks in the task list.
