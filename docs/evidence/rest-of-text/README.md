# The rest of the shell's text on the type roles

Change: `openspec/changes/the-rest-of-the-shell-text-takes-the-type-roles`.
Evidence class: host renders unless a section says otherwise.

- `host-home-widgets-steps.png`: `render_accessibility_scale_evidence`
  (`<step>-home-small-<size>.png`) over catppuccin generations, flattened
  onto a teal backdrop and cropped. Left column: 1232x568 at 100% (top) and
  200% (bottom). Right: 568x1232 at 100% and 200%. Battery and Weather
  2x2 cards, a folder and apps with stock names (tasks 1.1, 1.2).
- `host-banner-1232x568.png`, `host-banner-568x1232.png`: the top 140 px of
  `render_notification_banner_evidence`'s trusted-source banner at 100%
  (task 2.1).

Limits: no board captures yet (task 3.1). The volume HUD's expanded rows
are covered by unit tests only; they need streams playing on the board.
