## 1. Compositor

- [x] 1.1 Label, hit test and tap handling in `adapter.c`, with the drawer
  request deferred to the end of the Home settle. Proof: the landscape
  system build compiles the patched Sway (`nix build
  .#nixosConfigurations.k230-mainline-drm-shell-landscape-hdmi.config.system.build.toplevel`).

## 2. Board

- [x] 2.1 Test-activate the build. Open the overview with an app running,
  tap "All apps ›" (injected touch), and confirm the drawer opens.
  Proof: `docs/evidence/overview-all-apps/` with grim captures and the
  compositor log lines.
- [x] 2.2 The operator taps "All apps ›" on glass. Physical proof: a
  timestamped operator report tied to the installed build.
  *Operator at the glass, 2026-10-29 00:34 CDT, build `37g1magg…`: "all apps works" (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`).*
